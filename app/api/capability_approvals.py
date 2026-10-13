"""Owner review routes for trusted code-created protected-action approvals."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.application.services.capability_approvals import (
    APPROVAL_MANAGEMENT_PERMISSION,
    CapabilityApprovalError,
    CapabilityApprovalNotFound,
    CapabilityApprovalService,
)
from .security import AuthenticatedPrincipal, require_permission


router = APIRouter(prefix="/api/capabilities/approvals")
ApprovalId = Annotated[str, Path(min_length=1, max_length=64)]


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed_digest: StrictStr = Field(min_length=64, max_length=64,
                                        pattern="^[0-9a-f]{64}$")


def service(request: Request) -> CapabilityApprovalService:
    candidate = getattr(request.app.state, "capability_approval_service", None)
    if not isinstance(candidate, CapabilityApprovalService):
        raise HTTPException(503, "Capability approval service unavailable")
    return candidate


def require_local_session(principal: AuthenticatedPrincipal) -> None:
    if principal.session_id is None:
        raise HTTPException(403, "Owner session required for approval review")


@router.get("")
def list_approvals(principal: AuthenticatedPrincipal = Depends(
        require_permission(APPROVAL_MANAGEMENT_PERMISSION)),
        approvals: CapabilityApprovalService = Depends(service)):
    return {"items": [approvals.snapshot(item)
                      for item in approvals.list_for_actor(principal.identity)]}


@router.get("/{approval_id}")
def get_approval(approval_id: ApprovalId,
                 principal: AuthenticatedPrincipal = Depends(
                     require_permission(APPROVAL_MANAGEMENT_PERMISSION)),
                 approvals: CapabilityApprovalService = Depends(service)):
    try:
        record = approvals.get(approval_id)
    except CapabilityApprovalNotFound:
        raise HTTPException(404, "Approval request unavailable") from None
    if record.actor_id != principal.identity:
        raise HTTPException(404, "Approval request unavailable")
    return approvals.snapshot(record)


@router.post("/{approval_id}/approve")
def approve(approval_id: ApprovalId, body: ApprovalDecision, request: Request,
            principal: AuthenticatedPrincipal = Depends(
                require_permission(APPROVAL_MANAGEMENT_PERMISSION)),
            approvals: CapabilityApprovalService = Depends(service)):
    require_local_session(principal)
    csrf = getattr(request.app.state.authentication_backend, "require_csrf", None)
    if not callable(csrf):
        raise HTTPException(403, "Owner request verification unavailable")
    csrf(request)
    try:
        record = approvals.approve(approval_id, approver_id=principal.identity,
                                   permissions=principal.permissions,
                                   confirmed_digest=body.confirmed_digest)
    except CapabilityApprovalNotFound:
        raise HTTPException(404, "Approval request unavailable") from None
    except CapabilityApprovalError as error:
        raise HTTPException(409, str(error)) from None
    except PermissionError:
        raise HTTPException(403, "Capability authorization is no longer valid") from None
    return approvals.snapshot(record)
