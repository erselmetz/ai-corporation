"""Authorized creation and review of local approved maintenance checkpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, Field

from app.application.services.git_checkpoints import (
    GitCheckpoint,
    GitCheckpointBlockedError,
    GitCheckpointCapacityError,
    GitCheckpointError,
    GitCheckpointNotFoundError,
)
from app.application.services.maintenance_approvals import (
    MaintenanceApprovalNotFoundError,
)
from .security import AuthenticatedPrincipal, require_permission


router = APIRouter(prefix="/api/maintenance/checkpoints")
require_maintenance_checkpoint = require_permission("maintenance:checkpoint")
CheckpointIdentifier = Annotated[str, Path(min_length=1, max_length=64)]


class MaintenanceCheckpointRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str = Field(min_length=1, max_length=128)


class MaintenanceCheckpointSummaryResponse(BaseModel):
    checkpoint_id: str
    workspace_id: str
    proposal_id: str
    approval_request_id: str
    branch_name: str
    commit_sha: str
    parent_sha: str
    patch_sha256: str
    source_sha256: str
    changed_files: tuple[str, ...]
    created_by: str
    created_at: datetime


class MaintenanceCheckpointResponse(MaintenanceCheckpointSummaryResponse):
    unified_diff: str


class MaintenanceCheckpointListResponse(BaseModel):
    items: tuple[MaintenanceCheckpointSummaryResponse, ...]


def service(request: Request):
    return request.app.state.application_service


def _summary_response(
    checkpoint: GitCheckpoint,
) -> MaintenanceCheckpointSummaryResponse:
    return MaintenanceCheckpointSummaryResponse(
        checkpoint_id=checkpoint.checkpoint_id,
        workspace_id=checkpoint.workspace_id,
        proposal_id=checkpoint.proposal_id,
        approval_request_id=checkpoint.approval_request_id,
        branch_name=checkpoint.branch_name,
        commit_sha=checkpoint.commit_sha,
        parent_sha=checkpoint.parent_sha,
        patch_sha256=checkpoint.patch_sha256,
        source_sha256=checkpoint.source_sha256,
        changed_files=checkpoint.changed_files,
        created_by=checkpoint.created_by,
        created_at=checkpoint.created_at,
    )


def _checkpoint_response(
    checkpoint: GitCheckpoint,
) -> MaintenanceCheckpointResponse:
    summary = _summary_response(checkpoint)
    return MaintenanceCheckpointResponse(
        **summary.model_dump(),
        unified_diff=checkpoint.unified_diff,
    )


def _raise_api_error(error: Exception) -> None:
    if isinstance(error, (GitCheckpointNotFoundError, MaintenanceApprovalNotFoundError)):
        raise HTTPException(404, "Maintenance workspace or checkpoint not found") from None
    if isinstance(error, PermissionError):
        raise HTTPException(
            409, "An approved human review is required for this workspace"
        ) from None
    if isinstance(error, GitCheckpointBlockedError):
        raise HTTPException(
            409, "Checkpoint creation is blocked by repository state or policy"
        ) from None
    if isinstance(error, GitCheckpointCapacityError):
        raise HTTPException(409, "Maintenance checkpoint record limit reached") from None
    if isinstance(error, GitCheckpointError):
        raise HTTPException(
            503, "Git checkpoint service could not complete the operation"
        ) from None
    if isinstance(error, ValueError):
        raise HTTPException(422, "Maintenance checkpoint request is invalid") from None
    raise error


@router.post(
    "",
    response_model=MaintenanceCheckpointResponse,
    status_code=201,
)
def create_maintenance_checkpoint(
    body: MaintenanceCheckpointRequestBody,
    request: Request,
    principal: AuthenticatedPrincipal = Depends(require_maintenance_checkpoint),
):
    try:
        checkpoint = service(request).create_maintenance_checkpoint(
            body.workspace_id,
            created_by=principal.identity,
        )
    except (
        GitCheckpointError,
        GitCheckpointNotFoundError,
        MaintenanceApprovalNotFoundError,
        PermissionError,
        ValueError,
    ) as error:
        _raise_api_error(error)
    return _checkpoint_response(checkpoint)


@router.get(
    "",
    response_model=MaintenanceCheckpointListResponse,
    dependencies=[Depends(require_maintenance_checkpoint)],
)
def list_maintenance_checkpoints(request: Request):
    checkpoints = service(request).list_maintenance_checkpoints()
    return MaintenanceCheckpointListResponse(
        items=tuple(_summary_response(checkpoint) for checkpoint in checkpoints)
    )


@router.get(
    "/{checkpoint_id}",
    response_model=MaintenanceCheckpointResponse,
    dependencies=[Depends(require_maintenance_checkpoint)],
)
def get_maintenance_checkpoint(
    checkpoint_id: CheckpointIdentifier,
    request: Request,
):
    try:
        checkpoint = service(request).get_maintenance_checkpoint(checkpoint_id)
    except GitCheckpointNotFoundError as error:
        _raise_api_error(error)
    return _checkpoint_response(checkpoint)
