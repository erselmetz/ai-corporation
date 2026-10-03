from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ApprovalRequest:
    """
    Represents a request for human approval for a specific action.
    """
    id: str
    action: str
    context: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    decided_by: str | None = None
    decided_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Approval request id cannot be empty")
        if not self.action:
            raise ValueError("Action cannot be empty")
        if not self.context:
            raise ValueError("Context cannot be empty")
        if self.decided_by is not None and (
            not isinstance(self.decided_by, str) or not self.decided_by.strip()
        ):
            raise ValueError("Decision identity cannot be empty")
