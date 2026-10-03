from datetime import datetime, timezone

from .models import ApprovalRequest, ApprovalStatus


class ApprovalRegistry:
    """
    Registry for managing human approval requests.
    """

    def __init__(self):
        self._requests: dict[str, ApprovalRequest] = {}

    def register(self, request: ApprovalRequest) -> None:
        """Registers a new approval request."""
        if not isinstance(request, ApprovalRequest):
            raise TypeError("Only ApprovalRequest instances can be registered")

        if request.id in self._requests:
            raise ValueError(f"Approval request already registered: {request.id}")

        self._requests[request.id] = request

    def get(self, request_id: str) -> ApprovalRequest:
        """Retrieves an approval request by its ID."""
        try:
            return self._requests[request_id]
        except KeyError:
            raise ValueError(
                f"Approval request not found: {request_id}"
            ) from None

    def exists(self, request_id: str) -> bool:
        """Checks if an approval request exists."""
        return request_id in self._requests

    def all(self) -> list[ApprovalRequest]:
        """Returns all approval requests."""
        return list(self._requests.values())

    def approve(self, request_id: str, *, decided_by: str | None = None) -> None:
        """Approves a pending request."""
        request = self.get(request_id)
        if request.status != ApprovalStatus.PENDING:
            raise RuntimeError(
                f"Cannot approve request in status {request.status}. Must be pending."
            )
        _validate_decision_identity(decided_by)
        request.status = ApprovalStatus.APPROVED
        request.decided_by = decided_by
        request.decided_at = datetime.now(timezone.utc)

    def reject(self, request_id: str, *, decided_by: str | None = None) -> None:
        """Rejects a pending request."""
        request = self.get(request_id)
        if request.status != ApprovalStatus.PENDING:
            raise RuntimeError(
                f"Cannot reject request in status {request.status}. Must be pending."
            )
        _validate_decision_identity(decided_by)
        request.status = ApprovalStatus.REJECTED
        request.decided_by = decided_by
        request.decided_at = datetime.now(timezone.utc)


def _validate_decision_identity(decided_by: str | None) -> None:
    if decided_by is not None and (
        not isinstance(decided_by, str) or not decided_by.strip()
    ):
        raise ValueError("Decision identity cannot be empty")
