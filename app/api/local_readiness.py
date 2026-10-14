"""Owner-only readout of current process, model conditions, and restart evidence."""
from fastapi import APIRouter, Depends, HTTPException, Request

from app.application.services.readiness_evidence import readiness_snapshot
from .security import require_permission

router = APIRouter(prefix="/api/local/readiness", tags=["local-readiness"])


@router.get("", dependencies=[Depends(require_permission("system:read"))])
def readiness(request: Request):
    try:
        return readiness_snapshot(
            application_service=request.app.state.application_service,
            app_started_at=request.app.state.local_app_started_at,
            startup_setup_ms=request.app.state.local_startup_setup_ms,
        )
    except (RuntimeError, TypeError, ValueError):
        raise HTTPException(503, "Local readiness evidence is unavailable") from None
