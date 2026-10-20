"""Explicit local-owner emergency stop and activity status."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, StrictBool

from app.api.security import AuthenticatedPrincipal, require_permission


class ResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: StrictBool


def create_emergency_stop_router():
    router = APIRouter(prefix="/api/local/emergency-stop", tags=["emergency-stop"])

    @router.get("")
    def status(request: Request,
               principal: AuthenticatedPrincipal = Depends(require_permission("capability-emergency:read"))):
        stop = request.app.state.emergency_stop_service.snapshot()
        local_output = getattr(request.app.state, "local_speech_output", None)
        grants = request.app.state.capability_grant_service
        active = () if principal.session_id is None else grants.list_for_session(
            grantor=principal.identity, session_id=principal.session_id)
        return {**stop,
                "active_capabilities": sorted(principal.permissions),
                "session_grants": [grants.snapshot(item) for item in active],
                "local_speech_output": local_output.snapshot() if local_output is not None else {"state": "unavailable", "active": False},
                "capture": {"microphone": "page-reported", "screen": "page-reported",
                            "camera": "page-reported", "local_playback": "page-reported"}}

    @router.post("/stop")
    def stop(request: Request,
             _principal: AuthenticatedPrincipal = Depends(require_permission("capability-emergency:manage"))):
        output = getattr(request.app.state, "local_speech_output", None)
        if output is not None:
            output.stop()
        return request.app.state.emergency_stop_service.stop()

    @router.post("/resume")
    def resume(body: ResumeRequest, request: Request,
               _principal: AuthenticatedPrincipal = Depends(require_permission("capability-emergency:manage"))):
        if request.app.state.emergency_stop_service.stopped and not body.confirmed:
            raise HTTPException(409, "Explicit owner confirmation is required to resume protected actions")
        return request.app.state.emergency_stop_service.resume()

    return router
