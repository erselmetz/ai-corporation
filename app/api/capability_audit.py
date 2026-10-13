"""Owner-scoped inspection for bounded capability metadata events."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.application.services.capability_audit import CapabilityAuditError, CapabilityAuditService
from .security import AuthenticatedPrincipal, require_permission

router = APIRouter(prefix="/api/capabilities/audit", tags=["capability-audit"])


@router.get("")
def list_audit_events(
    request: Request,
    limit: int = Query(default=100, ge=1, le=CapabilityAuditService.MAX_INSPECTION_LIMIT),
    principal: AuthenticatedPrincipal = Depends(require_permission("capability-audit:read")),
):
    audit = request.app.state.capability_audit_service
    try:
        return {"items": list(audit.list_events(limit=limit))}
    except (CapabilityAuditError, OSError):
        raise HTTPException(503, "Capability audit history is unavailable") from None
