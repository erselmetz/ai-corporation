"""In-memory human approvals for exact maintenance patch workspaces."""

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from uuid import uuid4

from app.approval import ApprovalRegistry, ApprovalRequest, ApprovalStatus
from .patch_development import PatchDevelopmentService, PatchWorkspace


class MaintenanceApprovalNotFoundError(LookupError):
    pass


class MaintenanceApprovalCapacityError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MaintenanceApprovalSummary:
    request_id: str
    workspace_id: str
    proposal_id: str
    patch_sha256: str
    source_sha256: str
    changed_files: tuple[str, ...]
    status: ApprovalStatus
    requested_at: datetime
    decided_by: str | None
    decided_at: datetime | None


@dataclass(frozen=True, slots=True)
class MaintenanceApprovalReview(MaintenanceApprovalSummary):
    unified_diff: str


@dataclass(frozen=True, slots=True)
class _ApprovalRecord:
    request: ApprovalRequest
    workspace: PatchWorkspace


class MaintenanceApprovalService:
    MAX_REQUESTS = 100

    def __init__(self, workspaces: PatchDevelopmentService):
        if not isinstance(workspaces, PatchDevelopmentService):
            raise TypeError("workspaces must be a PatchDevelopmentService")
        self._workspaces = workspaces
        self._registry = ApprovalRegistry()
        self._records: dict[str, _ApprovalRecord] = {}
        self._lock = RLock()

    def request_review(self, workspace_id: str) -> MaintenanceApprovalReview:
        try:
            workspace = self._workspaces.get(workspace_id)
        except ValueError:
            raise MaintenanceApprovalNotFoundError(
                "Maintenance workspace was not found"
            ) from None
        if not workspace.unified_diff:
            raise ValueError("Maintenance workspace has no reviewable patch")

        with self._lock:
            self._validate_current_workspace(workspace)
            if len(self._records) >= self.MAX_REQUESTS:
                raise MaintenanceApprovalCapacityError(
                    "Maintenance approval request limit reached"
                )
            request_id = uuid4().hex
            request = ApprovalRequest(
                id=request_id,
                action=f"maintenance_workspace:{workspace.workspace_id}",
                context=(
                    f"proposal_id={workspace.proposal_id}; "
                    f"workspace_id={workspace.workspace_id}; "
                    f"patch_sha256={workspace.patch_sha256}; "
                    f"source_sha256={workspace.source_sha256}"
                ),
            )
            self._registry.register(request)
            self._records[request_id] = _ApprovalRecord(request, workspace)
            return _to_review(request, workspace)

    def list_pending(self) -> tuple[MaintenanceApprovalSummary, ...]:
        with self._lock:
            pending = sorted(
                (
                    record
                    for record in self._records.values()
                    if record.request.status is ApprovalStatus.PENDING
                ),
                key=lambda record: record.request.requested_at,
            )
            return tuple(
                _to_summary(record.request, record.workspace)
                for record in pending
            )

    def get_review(self, request_id: str) -> MaintenanceApprovalReview:
        with self._lock:
            record = self._get_record(request_id)
            return _to_review(record.request, record.workspace)

    def approve(
        self,
        request_id: str,
        *,
        approver_id: str,
        patch_sha256: str,
        source_sha256: str,
    ) -> MaintenanceApprovalReview:
        return self._decide(
            request_id,
            approver_id=approver_id,
            patch_sha256=patch_sha256,
            source_sha256=source_sha256,
            approve=True,
        )

    def reject(
        self,
        request_id: str,
        *,
        approver_id: str,
        patch_sha256: str,
        source_sha256: str,
    ) -> MaintenanceApprovalReview:
        return self._decide(
            request_id,
            approver_id=approver_id,
            patch_sha256=patch_sha256,
            source_sha256=source_sha256,
            approve=False,
        )

    def require_approved(self, workspace_id: str) -> MaintenanceApprovalReview:
        try:
            workspace = self._workspaces.get(workspace_id)
        except ValueError:
            raise MaintenanceApprovalNotFoundError(
                "Maintenance workspace was not found"
            ) from None
        with self._lock:
            matching = (
                record
                for record in self._records.values()
                if _same_workspace(record.workspace, workspace)
                and record.request.status is ApprovalStatus.APPROVED
                and record.request.decided_by is not None
                and record.request.decided_at is not None
            )
            record = next(matching, None)
            if record is None:
                raise PermissionError(
                    "An approved human review is required for this exact workspace"
                )
            return _to_review(record.request, record.workspace)

    def _decide(
        self,
        request_id: str,
        *,
        approver_id: str,
        patch_sha256: str,
        source_sha256: str,
        approve: bool,
    ) -> MaintenanceApprovalReview:
        _validate_approver_id(approver_id)
        _validate_hashes(patch_sha256, source_sha256)
        with self._lock:
            record = self._get_record(request_id)
            if (
                patch_sha256 != record.workspace.patch_sha256
                or source_sha256 != record.workspace.source_sha256
            ):
                raise PermissionError(
                    "Decision hashes do not match the reviewed workspace"
                )
            self._validate_current_workspace(record.workspace)
            if approve:
                self._registry.approve(request_id, decided_by=approver_id)
            else:
                self._registry.reject(request_id, decided_by=approver_id)
            return _to_review(record.request, record.workspace)

    def _get_record(self, request_id: str) -> _ApprovalRecord:
        if not isinstance(request_id, str) or not request_id:
            raise MaintenanceApprovalNotFoundError(
                "Maintenance approval request was not found"
            )
        try:
            return self._records[request_id]
        except KeyError:
            raise MaintenanceApprovalNotFoundError(
                "Maintenance approval request was not found"
            ) from None

    def _validate_current_workspace(self, expected: PatchWorkspace) -> None:
        try:
            current = self._workspaces.get(expected.workspace_id)
        except ValueError:
            raise PermissionError(
                "The maintenance workspace is unavailable or has changed"
            ) from None
        if not _same_workspace(current, expected):
            raise PermissionError(
                "The maintenance workspace is unavailable or has changed"
            )


def _validate_approver_id(approver_id: str) -> None:
    if not isinstance(approver_id, str) or not approver_id.strip():
        raise ValueError("Approver identity must be nonempty and bounded")
    try:
        identity_size = len(approver_id.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError(
            "Approver identity must be nonempty and bounded"
        ) from exc
    if identity_size > 256:
        raise ValueError("Approver identity must be nonempty and bounded")


def _validate_hashes(patch_sha256: str, source_sha256: str) -> None:
    if any(
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        for value in (patch_sha256, source_sha256)
    ):
        raise ValueError("Decision hashes must be lowercase SHA-256 values")


def _same_workspace(left: PatchWorkspace, right: PatchWorkspace) -> bool:
    return (
        left.workspace_id == right.workspace_id
        and left.proposal_id == right.proposal_id
        and left.patch_sha256 == right.patch_sha256
        and left.source_sha256 == right.source_sha256
        and left.unified_diff == right.unified_diff
    )


def _to_summary(
    request: ApprovalRequest,
    workspace: PatchWorkspace,
) -> MaintenanceApprovalSummary:
    return MaintenanceApprovalSummary(
        request_id=request.id,
        workspace_id=workspace.workspace_id,
        proposal_id=workspace.proposal_id,
        patch_sha256=workspace.patch_sha256,
        source_sha256=workspace.source_sha256,
        changed_files=workspace.changed_files,
        status=request.status,
        requested_at=request.requested_at,
        decided_by=request.decided_by,
        decided_at=request.decided_at,
    )


def _to_review(
    request: ApprovalRequest,
    workspace: PatchWorkspace,
) -> MaintenanceApprovalReview:
    summary = _to_summary(request, workspace)
    return MaintenanceApprovalReview(
        request_id=summary.request_id,
        workspace_id=summary.workspace_id,
        proposal_id=summary.proposal_id,
        patch_sha256=summary.patch_sha256,
        source_sha256=summary.source_sha256,
        changed_files=summary.changed_files,
        status=summary.status,
        requested_at=summary.requested_at,
        decided_by=summary.decided_by,
        decided_at=summary.decided_at,
        unified_diff=workspace.unified_diff,
    )
