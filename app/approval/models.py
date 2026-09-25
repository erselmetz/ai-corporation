from dataclasses import dataclass, field
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

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("Approval request id cannot be empty")
        if not self.action:
            raise ValueError("Action cannot be empty")
        if not self.context:
            raise ValueError("Context cannot be empty")
