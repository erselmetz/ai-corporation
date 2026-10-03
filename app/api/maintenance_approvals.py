"""Authenticated review and decision routes for maintenance patch workspaces."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, Field

from app.application.services.maintenance_approvals import (
    MaintenanceApprovalCapacityError,
    MaintenanceApprovalNotFoundError,
    MaintenanceApprovalReview,
    MaintenanceApprovalSummary,
)
from app.approval import ApprovalStatus
from .security import AuthenticatedPrincipal, require_permission


router = APIRouter(prefix="/api/maintenance/approvals")
require_maintenance_approval = require_permission("maintenance:approve")
RequestIdentifier = Annotated[str, Path(min_length=1, max_length=64)]


class MaintenanceApprovalRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str = Field(min_length=1, max_length=128)


class MaintenanceApprovalDecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approved", "rejected"]
    patch_sha256: str = Field(min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    source_sha256: str = Field(min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")


class MaintenanceApprovalSummaryResponse(BaseModel):
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


class MaintenanceApprovalReviewResponse(MaintenanceApprovalSummaryResponse):
    unified_diff: str


class MaintenanceApprovalListResponse(BaseModel):
    items: tuple[MaintenanceApprovalSummaryResponse, ...]


def service(request: Request):
    return request.app.state.application_service


def _summary_response(
    summary: MaintenanceApprovalSummary,
) -> MaintenanceApprovalSummaryResponse:
    return MaintenanceApprovalSummaryResponse(
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
    )


def _review_response(
    review: MaintenanceApprovalReview,
) -> MaintenanceApprovalReviewResponse:
    return MaintenanceApprovalReviewResponse(
        request_id=review.request_id,
        workspace_id=review.workspace_id,
        proposal_id=review.proposal_id,
        patch_sha256=review.patch_sha256,
        source_sha256=review.source_sha256,
        changed_files=review.changed_files,
        status=review.status,
        requested_at=review.requested_at,
        decided_by=review.decided_by,
        decided_at=review.decided_at,
        unified_diff=review.unified_diff,
    )


def _raise_api_error(error: Exception) -> None:
    if isinstance(error, MaintenanceApprovalNotFoundError):
        raise HTTPException(
            404, "Maintenance approval or workspace not found"
        ) from None
    if isinstance(error, MaintenanceApprovalCapacityError):
        raise HTTPException(409, "Maintenance approval request limit reached") from None
    if isinstance(error, PermissionError):
        raise HTTPException(
            409, "Maintenance workspace is unavailable or has changed"
        ) from None
    if isinstance(error, RuntimeError):
        raise HTTPException(409, "Maintenance approval request is no longer pending") from None
    if isinstance(error, ValueError):
        raise HTTPException(422, "Maintenance approval request is invalid") from None
    raise error


@router.post(
    "",
    response_model=MaintenanceApprovalReviewResponse,
    status_code=201,
    dependencies=[Depends(require_maintenance_approval)],
)
def request_maintenance_approval(
    body: MaintenanceApprovalRequestBody,
    request: Request,
):
    try:
        review = service(request).request_maintenance_approval(body.workspace_id)
    except (
        MaintenanceApprovalNotFoundError,
        MaintenanceApprovalCapacityError,
        PermissionError,
        RuntimeError,
        ValueError,
    ) as error:
        _raise_api_error(error)
    return _review_response(review)


@router.get(
    "",
    response_model=MaintenanceApprovalListResponse,
    dependencies=[Depends(require_maintenance_approval)],
)
def list_pending_maintenance_approvals(request: Request):
    summaries = service(request).list_pending_maintenance_approvals()
    return MaintenanceApprovalListResponse(
        items=tuple(_summary_response(summary) for summary in summaries)
    )


@router.get(
    "/{request_id}",
    response_model=MaintenanceApprovalReviewResponse,
    dependencies=[Depends(require_maintenance_approval)],
)
def get_maintenance_approval(request_id: RequestIdentifier, request: Request):
    try:
        review = service(request).get_maintenance_approval(request_id)
    except MaintenanceApprovalNotFoundError as error:
        _raise_api_error(error)
    return _review_response(review)


@router.post(
    "/{request_id}/decision",
    response_model=MaintenanceApprovalReviewResponse,
)
def decide_maintenance_approval(
    request_id: RequestIdentifier,
    body: MaintenanceApprovalDecisionBody,
    request: Request,
    approver: AuthenticatedPrincipal = Depends(require_maintenance_approval),
):
    try:
        if body.decision == ApprovalStatus.APPROVED.value:
            review = service(request).approve_maintenance_workspace(
                request_id,
                approver_id=approver.identity,
                patch_sha256=body.patch_sha256,
                source_sha256=body.source_sha256,
            )
        else:
            review = service(request).reject_maintenance_workspace(
                request_id,
                approver_id=approver.identity,
                patch_sha256=body.patch_sha256,
                source_sha256=body.source_sha256,
            )
    except (
        MaintenanceApprovalNotFoundError,
        MaintenanceApprovalCapacityError,
        PermissionError,
        RuntimeError,
        ValueError,
    ) as error:
        _raise_api_error(error)
    return _review_response(review)
