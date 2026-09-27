from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.approval import ApprovalRequest, ApprovalStatus


class IntegrationStatus(str, Enum):
    DISCOVERED = "discovered"
    ANALYZING = "analyzing"
    EVALUATING = "evaluating"
    PROPOSED = "proposed"
    SANDBOXED = "sandboxed"
    TESTED = "tested"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    INTEGRATED = "integrated"
    REJECTED = "rejected"
    FAILED = "failed"


class IntegrationCapability(str, Enum):
    READ_SOURCE = "read_source"
    ANALYZE_SOURCE = "analyze_source"
    RUN_SANDBOX = "run_sandbox"
    WRITE_PROJECT = "write_project"
    RUN_TESTS = "run_tests"
    REQUEST_APPROVAL = "request_approval"
    INTEGRATE = "integrate"


class IntegrationExecutionStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class IntegrationSource:
    source_type: str
    location: str
    project_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_type, str) or not self.source_type.strip():
            raise ValueError("Integration source type cannot be empty")
        if not isinstance(self.location, str) or not self.location.strip():
            raise ValueError("Integration source location cannot be empty")
        if self.project_name is not None and not self.project_name.strip():
            raise ValueError("Integration source project name cannot be empty")


_PROPOSAL_TRANSITIONS: dict[IntegrationStatus, set[IntegrationStatus]] = {
    IntegrationStatus.DISCOVERED: {
        IntegrationStatus.ANALYZING,
        IntegrationStatus.REJECTED,
        IntegrationStatus.FAILED,
    },
    IntegrationStatus.ANALYZING: {
        IntegrationStatus.EVALUATING,
        IntegrationStatus.REJECTED,
        IntegrationStatus.FAILED,
    },
    IntegrationStatus.EVALUATING: {
        IntegrationStatus.PROPOSED,
        IntegrationStatus.REJECTED,
        IntegrationStatus.FAILED,
    },
    IntegrationStatus.PROPOSED: {
        IntegrationStatus.SANDBOXED,
        IntegrationStatus.REJECTED,
        IntegrationStatus.FAILED,
    },
    IntegrationStatus.SANDBOXED: {
        IntegrationStatus.TESTED,
        IntegrationStatus.REJECTED,
        IntegrationStatus.FAILED,
    },
    IntegrationStatus.TESTED: {
        IntegrationStatus.REVIEW_REQUIRED,
        IntegrationStatus.REJECTED,
        IntegrationStatus.FAILED,
    },
    IntegrationStatus.REVIEW_REQUIRED: {
        IntegrationStatus.APPROVED,
        IntegrationStatus.REJECTED,
        IntegrationStatus.FAILED,
    },
    IntegrationStatus.APPROVED: {
        IntegrationStatus.INTEGRATED,
        IntegrationStatus.FAILED,
    },
    IntegrationStatus.INTEGRATED: set(),
    IntegrationStatus.REJECTED: set(),
    IntegrationStatus.FAILED: set(),
}


@dataclass
class IntegrationProposal:
    id: str
    source: IntegrationSource
    requested_purpose: str
    project_name: str | None = None
    evaluation_information: str | None = None
    proposed_approach: str | None = None
    risk_information: str | None = None
    source_discovery_id: str | None = field(default=None, kw_only=True)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _status: IntegrationStatus = field(
        default=IntegrationStatus.DISCOVERED,
        init=False,
        repr=False,
    )
    _approval_request: ApprovalRequest | None = field(
        default=None,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Integration proposal id cannot be empty")
        if not isinstance(self.source, IntegrationSource):
            raise TypeError("Integration proposal source must be an IntegrationSource")
        if (
            not isinstance(self.requested_purpose, str)
            or not self.requested_purpose.strip()
        ):
            raise ValueError("Integration proposal purpose cannot be empty")
        if (
            self.source_discovery_id is not None
            and not self.source_discovery_id.strip()
        ):
            raise ValueError("Source discovery id cannot be empty")
        if self.project_name is not None and not self.project_name.strip():
            raise ValueError("Integration proposal project name cannot be empty")

    @property
    def status(self) -> IntegrationStatus:
        return self._status

    @property
    def approval_request_id(self) -> str | None:
        if self._approval_request is None:
            return None
        return self._approval_request.id

    @property
    def approval_status(self) -> ApprovalStatus | None:
        if self._approval_request is None:
            return None
        return self._approval_request.status

    @property
    def approval_action(self) -> str:
        return f"integration_proposal:{self.id}"

    def attach_approval_request(self, request: ApprovalRequest) -> None:
        if self.status != IntegrationStatus.REVIEW_REQUIRED:
            raise ValueError("Approval can only be requested during review")
        if request.action != self.approval_action:
            raise ValueError("Approval request does not identify this proposal")
        if request.status != ApprovalStatus.PENDING:
            raise ValueError("Approval request must be pending")
        if self._approval_request is not None:
            raise ValueError("An approval request is already attached")
        self._approval_request = request
        self.updated_at = datetime.now(timezone.utc)

    def transition(
        self,
        target: IntegrationStatus,
        *,
        execution: IntegrationExecutionRecord | None = None,
    ) -> None:
        if not isinstance(target, IntegrationStatus):
            raise TypeError("Target must be an IntegrationStatus")
        if target not in _PROPOSAL_TRANSITIONS[self.status]:
            raise ValueError(
                f"Invalid integration proposal transition: "
                f"{self.status.value} -> {target.value}"
            )
        if target == IntegrationStatus.APPROVED:
            if self.approval_status != ApprovalStatus.APPROVED:
                raise PermissionError(
                    "An approved human ApprovalRequest is required"
                )
        elif target == IntegrationStatus.REJECTED:
            if (
                self.status == IntegrationStatus.REVIEW_REQUIRED
                and self._approval_request is not None
                and self.approval_status != ApprovalStatus.REJECTED
            ):
                raise PermissionError(
                    "The attached ApprovalRequest must be rejected first"
                )
        elif target == IntegrationStatus.INTEGRATED:
            if (
                execution is None
                or execution.proposal_id != self.id
                or execution.status != IntegrationExecutionStatus.COMPLETED
            ):
                raise PermissionError(
                    "A completed execution record for this proposal is required"
                )
        self._status = target
        self.updated_at = datetime.now(timezone.utc)


@dataclass
class IntegrationExecutionRecord:
    """Tracks a future integration attempt; it performs no external actions."""

    id: str
    proposal: IntegrationProposal = field(repr=False)
    requested_capabilities: frozenset[IntegrationCapability] = field(
        default_factory=frozenset
    )
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    _status: IntegrationExecutionStatus = field(
        default=IntegrationExecutionStatus.PLANNED,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Integration execution id cannot be empty")
        if not isinstance(self.proposal, IntegrationProposal):
            raise TypeError("Integration execution requires an IntegrationProposal")
        if self.proposal.status != IntegrationStatus.APPROVED:
            raise PermissionError(
                "An approved proposal is required before creating an execution record"
            )
        if not all(
            isinstance(capability, IntegrationCapability)
            for capability in self.requested_capabilities
        ):
            raise TypeError(
                "Requested capabilities must be IntegrationCapability values"
            )

    @property
    def proposal_id(self) -> str:
        return self.proposal.id

    @classmethod
    def for_approved_proposal(
        cls,
        execution_id: str,
        proposal: IntegrationProposal,
        requested_capabilities: frozenset[IntegrationCapability] = frozenset(),
    ) -> IntegrationExecutionRecord:
        if proposal.status != IntegrationStatus.APPROVED:
            raise PermissionError(
                "An approved proposal is required before creating an execution record"
            )
        return cls(
            id=execution_id,
            proposal=proposal,
            requested_capabilities=requested_capabilities,
        )

    @property
    def status(self) -> IntegrationExecutionStatus:
        return self._status

    def transition(self, target: IntegrationExecutionStatus) -> None:
        allowed = {
            IntegrationExecutionStatus.PLANNED: {
                IntegrationExecutionStatus.RUNNING,
                IntegrationExecutionStatus.FAILED,
            },
            IntegrationExecutionStatus.RUNNING: {
                IntegrationExecutionStatus.COMPLETED,
                IntegrationExecutionStatus.FAILED,
            },
            IntegrationExecutionStatus.COMPLETED: set(),
            IntegrationExecutionStatus.FAILED: set(),
        }
        if not isinstance(target, IntegrationExecutionStatus):
            raise TypeError("Target must be an IntegrationExecutionStatus")
        if target not in allowed[self.status]:
            raise ValueError(
                f"Invalid integration execution transition: "
                f"{self.status.value} -> {target.value}"
            )
        now = datetime.now(timezone.utc)
        self._status = target
        if target == IntegrationExecutionStatus.RUNNING:
            self.started_at = now
        elif target in {
            IntegrationExecutionStatus.COMPLETED,
            IntegrationExecutionStatus.FAILED,
        }:
            self.finished_at = now
