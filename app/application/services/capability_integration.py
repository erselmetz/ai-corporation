"""Caller-driven capability change-control workflow records."""

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from uuid import uuid4

from app.approval import ApprovalStatus
from app.capability_discovery import CapabilityCandidate
from app.capability_evaluation import CapabilityEvaluationReport
from .code_review import CodeReviewFinding, CodeReviewReport, CodeReviewService
from .diagnostics import DiagnosticEvidence, _evidence_digest
from .git_checkpoints import GitCheckpointNotFoundError, GitCheckpointService
from .maintenance_approvals import (
    MaintenanceApprovalNotFoundError,
    MaintenanceApprovalService,
)
from .maintenance_sandbox import MaintenanceSandboxReport, MaintenanceSandboxStatus
from .patch_development import PatchDevelopmentService, PatchWorkspace
from .testing_workflow import RunStatus, TestRunReport

MAX_CAPABILITY_INTEGRATION_WORKFLOWS = 100
MAX_CAPABILITY_INTEGRATION_EVENTS = 6


class CapabilityIntegrationStatus(str, Enum):
    ACTIVE = "active"
    READY_FOR_APPROVAL = "ready_for_approval"
    AWAITING_APPROVAL = "awaiting_approval"
    PATCH_APPROVED = "patch_approved"
    PATCH_REJECTED = "patch_rejected"
    CHECKPOINTED = "checkpointed"
    TEST_FAILED = "test_failed"


class CapabilityIntegrationStage(str, Enum):
    CANDIDATE_LINKED = "candidate_linked"
    TESTED = "tested"
    TEST_FAILED = "test_failed"
    REVIEWED = "reviewed"
    APPROVAL_PENDING = "approval_pending"
    PATCH_APPROVED = "patch_approved"
    PATCH_REJECTED = "patch_rejected"
    CHECKPOINTED = "checkpointed"


@dataclass(frozen=True, slots=True)
class CapabilityIntegrationEvent:
    sequence: int
    stage: CapabilityIntegrationStage
    artifact_id: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.sequence, int)
            or isinstance(self.sequence, bool)
            or not 1 <= self.sequence <= MAX_CAPABILITY_INTEGRATION_EVENTS
        ):
            raise ValueError("event sequence is invalid")
        if not isinstance(self.stage, CapabilityIntegrationStage):
            raise TypeError("stage must be a CapabilityIntegrationStage")
        _validate_text(self.artifact_id, "artifact_id", 256)
        _validate_time(self.occurred_at, "occurred_at")


@dataclass(frozen=True, slots=True)
class CapabilityIntegrationSnapshot:
    workflow_id: str
    candidate: CapabilityCandidate
    evaluation: CapabilityEvaluationReport
    proposal_id: str
    workspace_id: str
    patch_sha256: str
    source_sha256: str
    status: CapabilityIntegrationStatus
    stage: CapabilityIntegrationStage
    created_at: datetime
    updated_at: datetime
    events: tuple[CapabilityIntegrationEvent, ...]
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
    limitations: tuple[str, ...] = (
        "The candidate-to-workspace association is caller-supplied and is not semantically verified.",
        "Human approval applies to the exact maintenance patch and source hashes, not capability adoption or activation.",
        "This workflow records existing artifacts; it does not invoke tests, reviews, approvals, checkpoints, or integration.",
        "Workflow state is in-memory and is not durable audit history.",
    )

    def __post_init__(self) -> None:
        _validate_text(self.workflow_id, "workflow_id", 128)
        if not isinstance(self.candidate, CapabilityCandidate):
            raise TypeError("candidate must be a CapabilityCandidate")
        if not isinstance(self.evaluation, CapabilityEvaluationReport):
            raise TypeError("evaluation must be a CapabilityEvaluationReport")
        if self.evaluation.candidate_id != self.candidate.candidate_id:
            raise ValueError("evaluation does not match the capability candidate")
        _validate_text(self.proposal_id, "proposal_id", 256)
        _validate_text(self.workspace_id, "workspace_id", 256)
        _validate_hash(self.patch_sha256, "patch_sha256")
        _validate_hash(self.source_sha256, "source_sha256")
        if not isinstance(self.status, CapabilityIntegrationStatus):
            raise TypeError("status must be a CapabilityIntegrationStatus")
        if not isinstance(self.stage, CapabilityIntegrationStage):
            raise TypeError("stage must be a CapabilityIntegrationStage")
        _validate_time(self.created_at, "created_at")
        _validate_time(self.updated_at, "updated_at")
        if not isinstance(self.events, tuple) or not self.events or not all(
            isinstance(event, CapabilityIntegrationEvent) for event in self.events
        ):
            raise TypeError("events must be a non-empty immutable tuple")
        if len(self.events) > MAX_CAPABILITY_INTEGRATION_EVENTS:
            raise ValueError("workflow event count exceeds its limit")
        if tuple(event.sequence for event in self.events) != tuple(
            range(1, len(self.events) + 1)
        ):
            raise ValueError("workflow event sequence is invalid")
        if self.events[-1].stage is not self.stage:
            raise ValueError("workflow stage must match its latest event")
        if self.approval_status is not None and not isinstance(
            self.approval_status, ApprovalStatus
        ):
            raise TypeError("approval_status must be an ApprovalStatus")
        _validate_optional_text(
            self.approval_request_id,
            "approval_request_id",
            256,
        )
        _validate_optional_text(self.decision_by, "decision_by", 256)
        _validate_optional_time(self.decision_at, "decision_at")
        _validate_optional_text(self.test_run_id, "test_run_id", 256)
        _validate_optional_text(self.test_status, "test_status", 64)
        _validate_optional_text(self.review_agent_id, "review_agent_id", 256)
        _validate_optional_text(self.review_evidence_sha256, "review_evidence_sha256", 64)
        _validate_optional_text(self.checkpoint_id, "checkpoint_id", 256)
        _validate_optional_text(self.checkpoint_branch, "checkpoint_branch", 256)
        _validate_optional_text(self.checkpoint_commit_sha, "checkpoint_commit_sha", 64)
        _validate_optional_text(self.checkpoint_created_by, "checkpoint_created_by", 256)
        if self.review_finding_count is not None and (
            not isinstance(self.review_finding_count, int)
            or isinstance(self.review_finding_count, bool)
            or not 0 <= self.review_finding_count <= CodeReviewService.MAX_FINDINGS
        ):
            raise ValueError("review_finding_count is invalid")
        if not isinstance(self.limitations, tuple):
            raise TypeError("limitations must be a bounded immutable tuple of text")
        if len(self.limitations) > 8:
            raise ValueError("limitation count exceeds its limit")
        for limitation in self.limitations:
            _validate_text(limitation, "limitation", 512)


class CapabilityArtifactCheckStatus(str, Enum):
    CONSISTENT = "consistent"
    INCONSISTENT = "inconsistent"
    MISSING = "missing"
    UNVERIFIABLE = "unverifiable"


class CapabilityArtifactConsistency(str, Enum):
    CONSISTENT = "consistent"
    INCONSISTENT = "inconsistent"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True, slots=True)
class CapabilityArtifactCheck:
    artifact_kind: str
    artifact_id: str
    status: CapabilityArtifactCheckStatus

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_kind, str) or self.artifact_kind not in {
            "candidate_evaluation",
            "workspace",
            "test_result",
            "review_evidence",
            "approval",
            "checkpoint",
        }:
            raise ValueError("artifact_kind is unsupported")
        _validate_text(self.artifact_id, "artifact_id", 256)
        if not isinstance(self.status, CapabilityArtifactCheckStatus):
            raise TypeError("status must be a CapabilityArtifactCheckStatus")


@dataclass(frozen=True, slots=True)
class CapabilityIntegrationWorkflowAssessment:
    workflow: CapabilityIntegrationSnapshot
    artifact_consistency: CapabilityArtifactConsistency
    checks: tuple[CapabilityArtifactCheck, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.workflow, CapabilityIntegrationSnapshot):
            raise TypeError("workflow must be a CapabilityIntegrationSnapshot")
        if not isinstance(self.artifact_consistency, CapabilityArtifactConsistency):
            raise TypeError(
                "artifact_consistency must be a CapabilityArtifactConsistency"
            )
        if not isinstance(self.checks, tuple) or not 1 <= len(self.checks) <= 6:
            raise ValueError("checks must contain 1 to 6 immutable artifact checks")
        if not all(isinstance(check, CapabilityArtifactCheck) for check in self.checks):
            raise TypeError("checks must contain CapabilityArtifactCheck values")
        if len({check.artifact_kind for check in self.checks}) != len(self.checks):
            raise ValueError("artifact check kinds must be unique")
        if self.artifact_consistency is not _artifact_consistency(self.checks):
            raise ValueError("artifact_consistency does not match the artifact checks")


@dataclass(frozen=True, slots=True)
class CapabilityIntegrationPipelineReview:
    reviewed_at: datetime
    workflows: tuple[CapabilityIntegrationWorkflowAssessment, ...]
    limitations: tuple[str, ...] = (
        "Workflow progress is reported as recorded; it is not a recommendation to advance.",
        "Test reports and review evidence are not retained for independent revalidation.",
        "Caller-supplied candidate/workspace links are not semantically validated.",
        "Checkpointed means the exact patch was checkpointed, not that a capability was adopted or activated.",
        "Cross-service records are read sequentially and do not form an atomic snapshot.",
        "The review performs no Provider calls, Task execution, workflow transitions, or assignment changes.",
    )

    def __post_init__(self) -> None:
        _validate_time(self.reviewed_at, "reviewed_at")
        if not isinstance(self.workflows, tuple) or len(self.workflows) > MAX_CAPABILITY_INTEGRATION_WORKFLOWS:
            raise ValueError("workflows must be an immutable tuple within the workflow limit")
        if not all(
            isinstance(workflow, CapabilityIntegrationWorkflowAssessment)
            for workflow in self.workflows
        ):
            raise TypeError("workflows must contain CapabilityIntegrationWorkflowAssessment values")
        workflow_ids = tuple(item.workflow.workflow_id for item in self.workflows)
        if len(set(workflow_ids)) != len(workflow_ids):
            raise ValueError("workflow IDs must be unique")
        if not isinstance(self.limitations, tuple) or len(self.limitations) > 8:
            raise ValueError("limitations must be a bounded immutable tuple")
        for limitation in self.limitations:
            _validate_text(limitation, "limitation", 512)


class CapabilityIntegrationWorkflowService:
    """Record Task 93–94 candidates through separate change-control artifacts."""

    MAX_WORKFLOWS = MAX_CAPABILITY_INTEGRATION_WORKFLOWS
    MAX_EVENTS = MAX_CAPABILITY_INTEGRATION_EVENTS

    def __init__(
        self,
        *,
        workspaces: PatchDevelopmentService,
        approvals: MaintenanceApprovalService,
        checkpoints: GitCheckpointService,
    ) -> None:
        if not isinstance(workspaces, PatchDevelopmentService):
            raise TypeError("workspaces must be a PatchDevelopmentService")
        if not isinstance(approvals, MaintenanceApprovalService):
            raise TypeError("approvals must be a MaintenanceApprovalService")
        if not isinstance(checkpoints, GitCheckpointService):
            raise TypeError("checkpoints must be a GitCheckpointService")
        self._workspaces = workspaces
        self._approvals = approvals
        self._checkpoints = checkpoints
        self._records: dict[str, CapabilityIntegrationSnapshot] = {}
        self._lock = RLock()

    def start(
        self,
        candidate: CapabilityCandidate,
        evaluation: CapabilityEvaluationReport,
        workspace_id: str,
    ) -> CapabilityIntegrationSnapshot:
        if not isinstance(candidate, CapabilityCandidate):
            raise TypeError("candidate must be a CapabilityCandidate")
        if not isinstance(evaluation, CapabilityEvaluationReport):
            raise TypeError("evaluation must be a CapabilityEvaluationReport")
        if evaluation.candidate_id != candidate.candidate_id:
            raise ValueError("evaluation does not match the capability candidate")
        _validate_text(workspace_id, "workspace_id", 256)
        workspace = self._workspaces.get(workspace_id)
        if not workspace.unified_diff:
            raise ValueError("Capability change-control workspace has no patch")
        now = datetime.now(timezone.utc)
        event = CapabilityIntegrationEvent(
            sequence=1,
            stage=CapabilityIntegrationStage.CANDIDATE_LINKED,
            artifact_id=workspace.workspace_id,
            occurred_at=now,
        )
        snapshot = CapabilityIntegrationSnapshot(
            workflow_id=uuid4().hex,
            candidate=candidate,
            evaluation=evaluation,
            proposal_id=workspace.proposal_id,
            workspace_id=workspace.workspace_id,
            patch_sha256=workspace.patch_sha256,
            source_sha256=workspace.source_sha256,
            status=CapabilityIntegrationStatus.ACTIVE,
            stage=event.stage,
            created_at=now,
            updated_at=now,
            events=(event,),
        )
        with self._lock:
            if len(self._records) >= self.MAX_WORKFLOWS:
                raise ValueError("Capability integration workflow limit reached")
            self._records[snapshot.workflow_id] = snapshot
            return snapshot

    def record_test_result(
        self,
        workflow_id: str,
        report: TestRunReport | MaintenanceSandboxReport,
    ) -> CapabilityIntegrationSnapshot:
        if not isinstance(report, (TestRunReport, MaintenanceSandboxReport)):
            raise TypeError("Expected Task 80 or Task 82 test report")
        expected_status_type = (
            RunStatus if isinstance(report, TestRunReport) else MaintenanceSandboxStatus
        )
        if not isinstance(report.status, expected_status_type):
            raise TypeError("Test report has an invalid status")
        _validate_text(report.run_id, "run_id", 256)
        _validate_text(report.proposal_id, "proposal_id", 256)
        _validate_text(report.workspace_id, "workspace_id", 256)
        with self._lock:
            current = self._require_active_stage(
                workflow_id,
                CapabilityIntegrationStage.CANDIDATE_LINKED,
            )
            self._require_current_workspace(current)
            if (
                report.proposal_id != current.proposal_id
                or report.workspace_id != current.workspace_id
            ):
                raise ValueError("Test report does not match this capability workspace")
            passed = (
                report.status is RunStatus.PASSED
                if isinstance(report, TestRunReport)
                else report.status is MaintenanceSandboxStatus.PASSED
            )
            return self._append(
                current,
                (
                    CapabilityIntegrationStage.TESTED
                    if passed
                    else CapabilityIntegrationStage.TEST_FAILED
                ),
                artifact_id=report.run_id,
                status=(
                    CapabilityIntegrationStatus.ACTIVE
                    if passed
                    else CapabilityIntegrationStatus.TEST_FAILED
                ),
                test_run_id=report.run_id,
                test_status=report.status.value,
            )

    def record_review(
        self,
        workflow_id: str,
        report: CodeReviewReport,
        evidence: tuple[DiagnosticEvidence, ...],
    ) -> CapabilityIntegrationSnapshot:
        if not isinstance(report, CodeReviewReport):
            raise TypeError("Expected CodeReviewReport")
        _validate_text(report.agent_id, "agent_id", 256)
        if (
            not isinstance(report.findings, tuple)
            or len(report.findings) > CodeReviewService.MAX_FINDINGS
            or not all(
                isinstance(finding, CodeReviewFinding)
                for finding in report.findings
            )
        ):
            raise ValueError("Code review findings are invalid or exceed their limit")
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
            current = self._require_active_stage(
                workflow_id,
                CapabilityIntegrationStage.TESTED,
            )
            workspace = self._require_current_workspace(current)
            if sum(item.content == workspace.unified_diff for item in evidence) != 1:
                raise ValueError("Code review evidence must contain the exact patch")
            return self._append(
                current,
                CapabilityIntegrationStage.REVIEWED,
                artifact_id=report.agent_id,
                status=CapabilityIntegrationStatus.READY_FOR_APPROVAL,
                review_agent_id=report.agent_id,
                review_finding_count=len(report.findings),
                review_evidence_sha256=report.evidence_sha256,
            )

    def record_approval(
        self,
        workflow_id: str,
        request_id: str,
    ) -> CapabilityIntegrationSnapshot:
        _validate_text(request_id, "request_id", 256)
        with self._lock:
            current = self._get(workflow_id)
            if current.status not in (
                CapabilityIntegrationStatus.READY_FOR_APPROVAL,
                CapabilityIntegrationStatus.AWAITING_APPROVAL,
            ):
                raise ValueError("Workflow is not eligible to record patch approval")
            workspace = self._require_current_workspace(current)
            approval = self._approvals.get_review(request_id)
            if (
                approval.workspace_id != workspace.workspace_id
                or approval.patch_sha256 != current.patch_sha256
                or approval.source_sha256 != current.source_sha256
            ):
                raise ValueError("Approval does not match this capability workspace")
            if current.approval_request_id is not None and (
                current.approval_request_id != request_id
            ):
                raise ValueError("Workflow is already linked to another approval")
            if approval.status is ApprovalStatus.PENDING:
                if current.status is CapabilityIntegrationStatus.AWAITING_APPROVAL:
                    return current
                return self._append(
                    current,
                    CapabilityIntegrationStage.APPROVAL_PENDING,
                    artifact_id=approval.request_id,
                    status=CapabilityIntegrationStatus.AWAITING_APPROVAL,
                    approval_request_id=approval.request_id,
                    approval_status=approval.status,
                )
            if approval.status not in (
                ApprovalStatus.APPROVED,
                ApprovalStatus.REJECTED,
            ):
                raise ValueError("Approval has an unsupported status")
            if current.status is not CapabilityIntegrationStatus.AWAITING_APPROVAL:
                raise ValueError("Approval decision must follow its pending record")
            if approval.decided_by is None or approval.decided_at is None:
                raise ValueError("Approval decision is missing its reviewer record")
            approved = approval.status is ApprovalStatus.APPROVED
            return self._append(
                current,
                (
                    CapabilityIntegrationStage.PATCH_APPROVED
                    if approved
                    else CapabilityIntegrationStage.PATCH_REJECTED
                ),
                artifact_id=approval.request_id,
                status=(
                    CapabilityIntegrationStatus.PATCH_APPROVED
                    if approved
                    else CapabilityIntegrationStatus.PATCH_REJECTED
                ),
                approval_request_id=approval.request_id,
                approval_status=approval.status,
                decision_by=approval.decided_by,
                decision_at=approval.decided_at,
            )

    def record_checkpoint(
        self,
        workflow_id: str,
        checkpoint_id: str,
    ) -> CapabilityIntegrationSnapshot:
        _validate_text(checkpoint_id, "checkpoint_id", 256)
        with self._lock:
            current = self._require_status(
                workflow_id,
                CapabilityIntegrationStatus.PATCH_APPROVED,
            )
            self._require_current_workspace(current)
            checkpoint = self._checkpoints.get(checkpoint_id)
            if (
                checkpoint.workspace_id != current.workspace_id
                or checkpoint.approval_request_id != current.approval_request_id
                or checkpoint.patch_sha256 != current.patch_sha256
                or checkpoint.source_sha256 != current.source_sha256
            ):
                raise ValueError("Checkpoint does not match this approved patch")
            return self._append(
                current,
                CapabilityIntegrationStage.CHECKPOINTED,
                artifact_id=checkpoint.checkpoint_id,
                status=CapabilityIntegrationStatus.CHECKPOINTED,
                checkpoint_id=checkpoint.checkpoint_id,
                checkpoint_branch=checkpoint.branch_name,
                checkpoint_commit_sha=checkpoint.commit_sha,
                checkpoint_created_by=checkpoint.created_by,
            )

    def get(self, workflow_id: str) -> CapabilityIntegrationSnapshot:
        with self._lock:
            return self._get(workflow_id)

    def list(self) -> tuple[CapabilityIntegrationSnapshot, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._records.values(),
                    key=lambda record: record.created_at,
                    reverse=True,
                )
            )

    def review_pipeline(self) -> CapabilityIntegrationPipelineReview:
        workflows = self.list()
        assessments = tuple(self._assess_workflow(workflow) for workflow in workflows)
        return CapabilityIntegrationPipelineReview(
            datetime.now(timezone.utc),
            assessments,
        )

    def _assess_workflow(
        self,
        workflow: CapabilityIntegrationSnapshot,
    ) -> CapabilityIntegrationWorkflowAssessment:
        checks = [
            CapabilityArtifactCheck(
                "candidate_evaluation",
                workflow.candidate.candidate_id,
                (
                    CapabilityArtifactCheckStatus.CONSISTENT
                    if workflow.evaluation.candidate_id == workflow.candidate.candidate_id
                    else CapabilityArtifactCheckStatus.INCONSISTENT
                ),
            ),
        ]

        try:
            workspace = self._workspaces.get(workflow.workspace_id)
        except ValueError:
            checks.append(
                CapabilityArtifactCheck(
                    "workspace",
                    workflow.workspace_id,
                    CapabilityArtifactCheckStatus.MISSING,
                )
            )
        else:
            workspace_matches = (
                workspace.workspace_id == workflow.workspace_id
                and workspace.proposal_id == workflow.proposal_id
                and workspace.patch_sha256 == workflow.patch_sha256
                and workspace.source_sha256 == workflow.source_sha256
                and bool(workspace.unified_diff)
            )
            checks.append(
                CapabilityArtifactCheck(
                    "workspace",
                    workflow.workspace_id,
                    (
                        CapabilityArtifactCheckStatus.CONSISTENT
                        if workspace_matches
                        else CapabilityArtifactCheckStatus.INCONSISTENT
                    ),
                )
            )

        if workflow.test_run_id is not None:
            checks.append(
                CapabilityArtifactCheck(
                    "test_result",
                    workflow.test_run_id,
                    CapabilityArtifactCheckStatus.UNVERIFIABLE,
                )
            )
        if workflow.review_agent_id is not None:
            checks.append(
                CapabilityArtifactCheck(
                    "review_evidence",
                    workflow.review_agent_id,
                    CapabilityArtifactCheckStatus.UNVERIFIABLE,
                )
            )
        if workflow.approval_request_id is not None:
            try:
                approval = self._approvals.get_review(workflow.approval_request_id)
            except MaintenanceApprovalNotFoundError:
                approval_matches = False
                approval_missing = True
            else:
                approval_missing = False
                approval_matches = (
                    approval.request_id == workflow.approval_request_id
                    and approval.workspace_id == workflow.workspace_id
                    and approval.proposal_id == workflow.proposal_id
                    and approval.patch_sha256 == workflow.patch_sha256
                    and approval.source_sha256 == workflow.source_sha256
                    and approval.status is workflow.approval_status
                    and approval.decided_by == workflow.decision_by
                    and approval.decided_at == workflow.decision_at
                )
            checks.append(
                CapabilityArtifactCheck(
                    "approval",
                    workflow.approval_request_id,
                    (
                        CapabilityArtifactCheckStatus.MISSING
                        if approval_missing
                        else CapabilityArtifactCheckStatus.CONSISTENT
                        if approval_matches
                        else CapabilityArtifactCheckStatus.INCONSISTENT
                    ),
                )
            )
        if workflow.checkpoint_id is not None:
            try:
                checkpoint = self._checkpoints.get(workflow.checkpoint_id)
            except GitCheckpointNotFoundError:
                checkpoint_matches = False
                checkpoint_missing = True
            else:
                checkpoint_missing = False
                checkpoint_matches = (
                    checkpoint.checkpoint_id == workflow.checkpoint_id
                    and checkpoint.workspace_id == workflow.workspace_id
                    and checkpoint.proposal_id == workflow.proposal_id
                    and checkpoint.approval_request_id == workflow.approval_request_id
                    and checkpoint.patch_sha256 == workflow.patch_sha256
                    and checkpoint.source_sha256 == workflow.source_sha256
                    and checkpoint.branch_name == workflow.checkpoint_branch
                    and checkpoint.commit_sha == workflow.checkpoint_commit_sha
                    and checkpoint.created_by == workflow.checkpoint_created_by
                )
            checks.append(
                CapabilityArtifactCheck(
                    "checkpoint",
                    workflow.checkpoint_id,
                    (
                        CapabilityArtifactCheckStatus.MISSING
                        if checkpoint_missing
                        else CapabilityArtifactCheckStatus.CONSISTENT
                        if checkpoint_matches
                        else CapabilityArtifactCheckStatus.INCONSISTENT
                    ),
                )
            )

        artifact_checks = tuple(checks)
        return CapabilityIntegrationWorkflowAssessment(
            workflow,
            _artifact_consistency(artifact_checks),
            artifact_checks,
        )

    def _require_current_workspace(
        self,
        current: CapabilityIntegrationSnapshot,
    ) -> PatchWorkspace:
        workspace = self._workspaces.get(current.workspace_id)
        if (
            workspace.proposal_id != current.proposal_id
            or workspace.patch_sha256 != current.patch_sha256
            or workspace.source_sha256 != current.source_sha256
            or not workspace.unified_diff
        ):
            raise ValueError("Capability workspace no longer matches this workflow")
        return workspace

    def _require_active_stage(
        self,
        workflow_id: str,
        stage: CapabilityIntegrationStage,
    ) -> CapabilityIntegrationSnapshot:
        current = self._get(workflow_id)
        if (
            current.status is not CapabilityIntegrationStatus.ACTIVE
            or current.stage is not stage
        ):
            raise ValueError("Workflow stage is out of order or terminal")
        return current

    def _require_status(
        self,
        workflow_id: str,
        status: CapabilityIntegrationStatus,
    ) -> CapabilityIntegrationSnapshot:
        current = self._get(workflow_id)
        if current.status is not status:
            raise ValueError("Workflow is not in the required state")
        return current

    def _get(self, workflow_id: str) -> CapabilityIntegrationSnapshot:
        if not isinstance(workflow_id, str) or not workflow_id:
            raise ValueError("Capability integration workflow was not found")
        try:
            return self._records[workflow_id]
        except KeyError:
            raise ValueError("Capability integration workflow was not found") from None

    def _append(
        self,
        current: CapabilityIntegrationSnapshot,
        stage: CapabilityIntegrationStage,
        *,
        artifact_id: str,
        status: CapabilityIntegrationStatus,
        **changes,
    ) -> CapabilityIntegrationSnapshot:
        if len(current.events) >= self.MAX_EVENTS:
            raise ValueError("Capability integration workflow event limit reached")
        now = datetime.now(timezone.utc)
        event = CapabilityIntegrationEvent(
            sequence=len(current.events) + 1,
            stage=stage,
            artifact_id=artifact_id,
            occurred_at=now,
        )
        updated = replace(
            current,
            stage=stage,
            status=status,
            updated_at=now,
            events=(*current.events, event),
            **changes,
        )
        self._records[current.workflow_id] = updated
        return updated


def _validate_text(value: str, field_name: str, maximum_bytes: int) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text")
    try:
        encoded_size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError(f"{field_name} must contain valid Unicode text") from exc
    if encoded_size > maximum_bytes or any(ord(character) < 32 for character in value):
        raise ValueError(f"{field_name} is invalid or exceeds its byte limit")


def _artifact_consistency(
    checks: tuple[CapabilityArtifactCheck, ...],
) -> CapabilityArtifactConsistency:
    statuses = {check.status for check in checks}
    if statuses.intersection(
        {
            CapabilityArtifactCheckStatus.INCONSISTENT,
            CapabilityArtifactCheckStatus.MISSING,
        }
    ):
        return CapabilityArtifactConsistency.INCONSISTENT
    if CapabilityArtifactCheckStatus.UNVERIFIABLE in statuses:
        return CapabilityArtifactConsistency.UNVERIFIABLE
    return CapabilityArtifactConsistency.CONSISTENT


def _validate_optional_text(
    value: str | None,
    field_name: str,
    maximum_bytes: int,
) -> None:
    if value is not None:
        _validate_text(value, field_name, maximum_bytes)


def _validate_time(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _validate_optional_time(value: datetime | None, field_name: str) -> None:
    if value is not None:
        _validate_time(value, field_name)


def _validate_hash(value: str, field_name: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{field_name} must be a SHA-256 digest")
