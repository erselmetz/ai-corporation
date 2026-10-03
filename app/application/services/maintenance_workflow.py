"""Bounded, caller-driven maintenance workflow records and audit events."""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import json
from threading import RLock
from uuid import uuid4

from app.approval import ApprovalStatus
from app.database import TaskLogger
from app.orchestrator import TaskFailureCategory, TaskStatus
from app.orchestrator.task_registry import TaskRegistry
from .code_review import CodeReviewReport, CodeReviewService
from .diagnostics import (
    DiagnosticEvidence,
    DiagnosticReport,
    _evidence_digest,
)
from .failure_detection import DetectedFailure
from .git_checkpoints import GitCheckpointService
from .maintenance_approvals import MaintenanceApprovalService
from .maintenance_proposals import MaintenanceProposalService
from .maintenance_sandbox import MaintenanceSandboxReport, MaintenanceSandboxStatus
from .patch_development import PatchDevelopmentService
from .testing_workflow import RunStatus, TestRunReport


class MaintenanceWorkflowStatus(str, Enum):
    ACTIVE = "active"
    READY_FOR_APPROVAL = "ready_for_approval"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHECKPOINTED = "checkpointed"
    FAILED = "failed"


class MaintenanceWorkflowStage(str, Enum):
    FAILURE_RECORDED = "failure_recorded"
    DIAGNOSED = "diagnosed"
    PROPOSED = "proposed"
    PATCHED = "patched"
    TESTED = "tested"
    TEST_FAILED = "test_failed"
    REVIEWED = "reviewed"
    APPROVAL_PENDING = "approval_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHECKPOINTED = "checkpointed"


@dataclass(frozen=True, slots=True)
class MaintenanceWorkflowEvent:
    sequence: int
    stage: MaintenanceWorkflowStage
    outcome: str
    artifact_id: str | None
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class MaintenanceWorkflowSnapshot:
    workflow_id: str
    task_id: str
    failure: DetectedFailure
    status: MaintenanceWorkflowStatus
    stage: MaintenanceWorkflowStage
    created_at: datetime
    updated_at: datetime
    events: tuple[MaintenanceWorkflowEvent, ...]
    diagnostic: DiagnosticReport | None = None
    proposal_id: str | None = None
    workspace_id: str | None = None
    patch_sha256: str | None = None
    source_sha256: str | None = None
    test_run_id: str | None = None
    test_status: str | None = None
    review_agent_id: str | None = None
    review_finding_count: int | None = None
    review_evidence_sha256: str | None = None
    approval_request_id: str | None = None
    approval_status: ApprovalStatus | None = None
    decision_by: str | None = None
    decision_at: datetime | None = None
    checkpoint_id: str | None = None
    checkpoint_branch: str | None = None
    checkpoint_commit_sha: str | None = None
    checkpoint_created_by: str | None = None


class MaintenanceWorkflowService:
    MAX_WORKFLOWS = 100
    MAX_EVENTS = 9

    def __init__(
        self,
        *,
        tasks: TaskRegistry,
        proposals: MaintenanceProposalService,
        workspaces: PatchDevelopmentService,
        approvals: MaintenanceApprovalService,
        checkpoints: GitCheckpointService,
        logger: TaskLogger,
    ):
        if not isinstance(tasks, TaskRegistry):
            raise TypeError("tasks must be a TaskRegistry")
        if not isinstance(proposals, MaintenanceProposalService):
            raise TypeError("proposals must be a MaintenanceProposalService")
        if not isinstance(workspaces, PatchDevelopmentService):
            raise TypeError("workspaces must be a PatchDevelopmentService")
        if not isinstance(approvals, MaintenanceApprovalService):
            raise TypeError("approvals must be a MaintenanceApprovalService")
        if not isinstance(checkpoints, GitCheckpointService):
            raise TypeError("checkpoints must be a GitCheckpointService")
        if not isinstance(logger, TaskLogger):
            raise TypeError("logger must be a TaskLogger")
        self._tasks = tasks
        self._proposals = proposals
        self._workspaces = workspaces
        self._approvals = approvals
        self._checkpoints = checkpoints
        self._logger = logger
        self._records: dict[str, MaintenanceWorkflowSnapshot] = {}
        self._lock = RLock()

    def start(self, failure: DetectedFailure) -> MaintenanceWorkflowSnapshot:
        if not isinstance(failure, DetectedFailure):
            raise TypeError("Expected DetectedFailure")
        self._require_current_failure(failure)
        now = datetime.now(timezone.utc)
        workflow_id = uuid4().hex
        event = MaintenanceWorkflowEvent(
            sequence=1,
            stage=MaintenanceWorkflowStage.FAILURE_RECORDED,
            outcome="recorded",
            artifact_id=failure.task_id,
            occurred_at=now,
        )
        snapshot = MaintenanceWorkflowSnapshot(
            workflow_id=workflow_id,
            task_id=failure.task_id,
            failure=failure,
            status=MaintenanceWorkflowStatus.ACTIVE,
            stage=event.stage,
            created_at=now,
            updated_at=now,
            events=(event,),
        )
        with self._lock:
            if len(self._records) >= self.MAX_WORKFLOWS:
                raise ValueError("Maintenance workflow limit reached")
            self._audit(snapshot, event)
            self._records[workflow_id] = snapshot
            return snapshot

    def record_diagnostic(
        self,
        workflow_id: str,
        report: DiagnosticReport,
    ) -> MaintenanceWorkflowSnapshot:
        if not isinstance(report, DiagnosticReport):
            raise TypeError("Expected DiagnosticReport")
        with self._lock:
            current = self._require_stage(
                workflow_id,
                stage=MaintenanceWorkflowStage.FAILURE_RECORDED,
            )
            self._require_current_failure(current.failure)
            if report.failure != current.failure:
                raise ValueError("Diagnostic does not match the recorded failure")
            return self._append(
                current,
                MaintenanceWorkflowStage.DIAGNOSED,
                outcome="recorded",
                artifact_id=report.agent_id,
                diagnostic=report,
            )

    def record_proposal(
        self,
        workflow_id: str,
        proposal_id: str,
    ) -> MaintenanceWorkflowSnapshot:
        with self._lock:
            current = self._require_stage(
                workflow_id,
                stage=MaintenanceWorkflowStage.DIAGNOSED,
            )
            self._require_current_failure(current.failure)
            proposal = self._proposals.get(proposal_id)
            if proposal.diagnostic != current.diagnostic:
                raise ValueError("Proposal is not linked to this workflow diagnostic")
            return self._append(
                current,
                MaintenanceWorkflowStage.PROPOSED,
                outcome="recorded",
                artifact_id=proposal.proposal_id,
                proposal_id=proposal.proposal_id,
            )

    def record_patch(
        self,
        workflow_id: str,
        workspace_id: str,
    ) -> MaintenanceWorkflowSnapshot:
        with self._lock:
            current = self._require_stage(
                workflow_id,
                stage=MaintenanceWorkflowStage.PROPOSED,
            )
            self._require_current_failure(current.failure)
            workspace = self._workspaces.get(workspace_id)
            if workspace.proposal_id != current.proposal_id:
                raise ValueError("Patch workspace is not linked to this proposal")
            if not workspace.unified_diff:
                raise ValueError("Patch workspace has no reviewable changes")
            return self._append(
                current,
                MaintenanceWorkflowStage.PATCHED,
                outcome="recorded",
                artifact_id=workspace.workspace_id,
                workspace_id=workspace.workspace_id,
                patch_sha256=workspace.patch_sha256,
                source_sha256=workspace.source_sha256,
            )

    def record_test_result(
        self,
        workflow_id: str,
        report: TestRunReport | MaintenanceSandboxReport,
    ) -> MaintenanceWorkflowSnapshot:
        if not isinstance(report, (TestRunReport, MaintenanceSandboxReport)):
            raise TypeError("Expected Task 80 or Task 82 test report")
        with self._lock:
            current = self._require_stage(
                workflow_id,
                stage=MaintenanceWorkflowStage.PATCHED,
            )
            self._require_current_failure(current.failure)
            if (
                report.proposal_id != current.proposal_id
                or report.workspace_id != current.workspace_id
            ):
                raise ValueError("Test report does not match this patch workspace")
            passed = (
                report.status is RunStatus.PASSED
                if isinstance(report, TestRunReport)
                else report.status is MaintenanceSandboxStatus.PASSED
            )
            stage = (
                MaintenanceWorkflowStage.TESTED
                if passed
                else MaintenanceWorkflowStage.TEST_FAILED
            )
            return self._append(
                current,
                stage,
                outcome=report.status.value,
                artifact_id=report.run_id,
                status=(
                    MaintenanceWorkflowStatus.ACTIVE
                    if passed
                    else MaintenanceWorkflowStatus.FAILED
                ),
                test_run_id=report.run_id,
                test_status=report.status.value,
            )

    def record_review(
        self,
        workflow_id: str,
        report: CodeReviewReport,
        evidence: tuple[DiagnosticEvidence, ...],
    ) -> MaintenanceWorkflowSnapshot:
        if not isinstance(report, CodeReviewReport):
            raise TypeError("Expected CodeReviewReport")
        if (
            not isinstance(evidence, tuple)
            or not 1 <= len(evidence) <= CodeReviewService.MAX_EVIDENCE_ITEMS
            or not all(isinstance(item, DiagnosticEvidence) for item in evidence)
        ):
            raise ValueError("Supply the bounded evidence submitted for code review")
        references = tuple(item.reference_id for item in evidence)
        if len(set(references)) != len(references):
            raise ValueError("Code review evidence references must be unique")
        if sum(len(item.content.encode("utf-8")) for item in evidence) > (
            CodeReviewService.MAX_EVIDENCE_BYTES
        ):
            raise ValueError("Code review evidence exceeds the total byte limit")
        if report.evidence_sha256 != _evidence_digest(evidence):
            raise ValueError("Code review report does not match the supplied evidence")
        if any(
            not set(finding.evidence_refs).issubset(references)
            for finding in report.findings
        ):
            raise ValueError("Code review report cites evidence not supplied")

        with self._lock:
            current = self._require_stage(
                workflow_id,
                stage=MaintenanceWorkflowStage.TESTED,
            )
            self._require_current_failure(current.failure)
            workspace = self._workspaces.get(current.workspace_id)
            if sum(item.content == workspace.unified_diff for item in evidence) != 1:
                raise ValueError("Code review evidence must contain the exact patch")
            return self._append(
                current,
                MaintenanceWorkflowStage.REVIEWED,
                outcome="recorded",
                artifact_id=report.agent_id,
                status=MaintenanceWorkflowStatus.READY_FOR_APPROVAL,
                review_agent_id=report.agent_id,
                review_finding_count=len(report.findings),
                review_evidence_sha256=report.evidence_sha256,
            )

    def record_approval(
        self,
        workflow_id: str,
        request_id: str,
    ) -> MaintenanceWorkflowSnapshot:
        with self._lock:
            current = self._get(workflow_id)
            if current.status not in (
                MaintenanceWorkflowStatus.READY_FOR_APPROVAL,
                MaintenanceWorkflowStatus.AWAITING_APPROVAL,
            ):
                raise ValueError("Workflow is not eligible to record approval")
            self._require_current_failure(current.failure)
            review = self._approvals.get_review(request_id)
            workspace = self._workspaces.get(current.workspace_id)
            if (
                review.workspace_id != workspace.workspace_id
                or review.patch_sha256 != current.patch_sha256
                or review.source_sha256 != current.source_sha256
            ):
                raise ValueError("Approval does not match this workflow patch")
            if current.approval_request_id is not None and (
                request_id != current.approval_request_id
            ):
                raise ValueError("Workflow is already linked to another approval")
            if review.status is ApprovalStatus.PENDING:
                if current.status is MaintenanceWorkflowStatus.AWAITING_APPROVAL:
                    return current
                return self._append(
                    current,
                    MaintenanceWorkflowStage.APPROVAL_PENDING,
                    outcome=review.status.value,
                    artifact_id=review.request_id,
                    status=MaintenanceWorkflowStatus.AWAITING_APPROVAL,
                    approval_request_id=review.request_id,
                    approval_status=review.status,
                )
            if review.status not in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED):
                raise ValueError("Approval has an unsupported status")
            if current.status is MaintenanceWorkflowStatus.READY_FOR_APPROVAL:
                raise ValueError("Approval request must be recorded before its decision")
            if review.decided_by is None or review.decided_at is None:
                raise ValueError("Approval decision is missing its reviewer record")
            approved = review.status is ApprovalStatus.APPROVED
            return self._append(
                current,
                (
                    MaintenanceWorkflowStage.APPROVED
                    if approved
                    else MaintenanceWorkflowStage.REJECTED
                ),
                outcome=review.status.value,
                artifact_id=review.request_id,
                status=(
                    MaintenanceWorkflowStatus.APPROVED
                    if approved
                    else MaintenanceWorkflowStatus.REJECTED
                ),
                approval_request_id=review.request_id,
                approval_status=review.status,
                decision_by=review.decided_by,
                decision_at=review.decided_at,
            )

    def record_checkpoint(
        self,
        workflow_id: str,
        checkpoint_id: str,
    ) -> MaintenanceWorkflowSnapshot:
        with self._lock:
            current = self._require_status(
                workflow_id,
                MaintenanceWorkflowStatus.APPROVED,
            )
            self._require_current_failure(current.failure)
            checkpoint = self._checkpoints.get(checkpoint_id)
            if (
                checkpoint.workspace_id != current.workspace_id
                or checkpoint.approval_request_id != current.approval_request_id
                or checkpoint.patch_sha256 != current.patch_sha256
                or checkpoint.source_sha256 != current.source_sha256
            ):
                raise ValueError("Checkpoint does not match this approved workflow")
            return self._append(
                current,
                MaintenanceWorkflowStage.CHECKPOINTED,
                outcome="created",
                artifact_id=checkpoint.checkpoint_id,
                status=MaintenanceWorkflowStatus.CHECKPOINTED,
                checkpoint_id=checkpoint.checkpoint_id,
                checkpoint_branch=checkpoint.branch_name,
                checkpoint_commit_sha=checkpoint.commit_sha,
                checkpoint_created_by=checkpoint.created_by,
            )

    def get(self, workflow_id: str) -> MaintenanceWorkflowSnapshot:
        with self._lock:
            return self._get(workflow_id)

    def list(self) -> tuple[MaintenanceWorkflowSnapshot, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._records.values(),
                    key=lambda record: record.created_at,
                    reverse=True,
                )
            )

    def _require_current_failure(self, failure: DetectedFailure) -> None:
        task = self._tasks.get(failure.task_id)
        category = task.failure_category or TaskFailureCategory.UNKNOWN
        if task.status is not TaskStatus.FAILED or category is not failure.category:
            raise ValueError("Failure is no longer current")

    def _require_stage(
        self,
        workflow_id: str,
        *,
        stage: MaintenanceWorkflowStage,
    ) -> MaintenanceWorkflowSnapshot:
        current = self._get(workflow_id)
        if current.status is not MaintenanceWorkflowStatus.ACTIVE or (
            current.stage is not stage
        ):
            raise ValueError("Workflow stage is out of order or terminal")
        return current

    def _require_status(
        self,
        workflow_id: str,
        status: MaintenanceWorkflowStatus,
    ) -> MaintenanceWorkflowSnapshot:
        current = self._get(workflow_id)
        if current.status is not status:
            raise ValueError("Workflow is not in the required state")
        return current

    def _get(self, workflow_id: str) -> MaintenanceWorkflowSnapshot:
        if not isinstance(workflow_id, str) or not workflow_id:
            raise ValueError("Maintenance workflow was not found")
        try:
            return self._records[workflow_id]
        except KeyError:
            raise ValueError("Maintenance workflow was not found") from None

    def _append(
        self,
        current: MaintenanceWorkflowSnapshot,
        stage: MaintenanceWorkflowStage,
        *,
        outcome: str,
        artifact_id: str | None,
        **changes,
    ) -> MaintenanceWorkflowSnapshot:
        if len(current.events) >= self.MAX_EVENTS:
            raise ValueError("Maintenance workflow event limit reached")
        now = datetime.now(timezone.utc)
        event = MaintenanceWorkflowEvent(
            sequence=len(current.events) + 1,
            stage=stage,
            outcome=outcome,
            artifact_id=artifact_id,
            occurred_at=now,
        )
        updated = replace(
            current,
            stage=stage,
            updated_at=now,
            events=(*current.events, event),
            **changes,
        )
        self._audit(updated, event)
        self._records[current.workflow_id] = updated
        return updated

    def _audit(
        self,
        snapshot: MaintenanceWorkflowSnapshot,
        event: MaintenanceWorkflowEvent,
    ) -> None:
        self._logger.log(
            snapshot.task_id,
            f"MAINTENANCE_WORKFLOW_{event.stage.value.upper()}",
            json.dumps(
                {
                    "workflow_id": snapshot.workflow_id,
                    "stage": event.stage.value,
                    "outcome": event.outcome,
                    "artifact_id": event.artifact_id,
                    "patch_sha256": snapshot.patch_sha256,
                    "source_sha256": snapshot.source_sha256,
                    "review_evidence_sha256": snapshot.review_evidence_sha256,
                    "review_finding_count": snapshot.review_finding_count,
                    "approval_request_id": snapshot.approval_request_id,
                    "decision_by": snapshot.decision_by,
                    "checkpoint_id": snapshot.checkpoint_id,
                    "checkpoint_branch": snapshot.checkpoint_branch,
                    "checkpoint_commit_sha": snapshot.checkpoint_commit_sha,
                    "checkpoint_created_by": snapshot.checkpoint_created_by,
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
        )
