"""Owner-only profile controls for the existing Agent and Employee records."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

from app.application.services.corporation import CorporationApplicationService
from .app import get_application_service
from .security import require_permission


router = APIRouter(prefix="/api/agents", tags=["agent-profiles"])
status_router = APIRouter(prefix="/api/local/agents", tags=["agent-profiles"])


class AgentProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: StrictStr = Field(min_length=1, max_length=128)
    role: StrictStr = Field(min_length=1, max_length=256)
    system_prompt: StrictStr = Field(max_length=2000)
    brain_scopes: list[StrictStr] = Field(max_length=8)
    allowed_tools: list[StrictStr] = Field(max_length=12)
    permissions: list[StrictStr] = Field(max_length=12)


class AgentPauseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paused: StrictBool


class AgentDuplicateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_id: StrictStr = Field(min_length=8, max_length=64, pattern="^custom_[a-zA-Z0-9_-]+$")
    name: StrictStr = Field(min_length=1, max_length=128)


def _csrf(request: Request) -> None:
    backend = getattr(request.app.state, "authentication_backend", None)
    check = getattr(backend, "require_csrf", None)
    if not callable(check):
        raise HTTPException(403, "Owner request verification is unavailable")
    check(request)


def _summary(summary) -> dict:
    return {
        "id": summary.id, "name": summary.name, "role": summary.role,
        "provider": summary.provider, "model": summary.model,
        "capabilities": list(summary.capabilities), "system_prompt": summary.system_prompt,
        "brain_scopes": list(summary.brain_scopes), "allowed_tools": list(summary.allowed_tools),
        "permissions": list(summary.permissions), "builtin_key": summary.builtin_key,
        "paused": summary.paused, "model_route_preference": summary.model_route_preference,
    }


@router.get("/{agent_id}/profile", dependencies=[Depends(require_permission("agent:manage"))])
def get_profile(agent_id: str, application: CorporationApplicationService = Depends(get_application_service)):
    try:
        return _summary(application.get_agent_profile(agent_id))
    except ValueError:
        raise HTTPException(404, "Agent not found") from None


@status_router.get("/status", dependencies=[Depends(require_permission("agent:read"))])
def agent_statuses(application: CorporationApplicationService = Depends(get_application_service)):
    return {"items": list(application.agent_runtime_statuses())}


@router.put("/{agent_id}/profile", dependencies=[Depends(require_permission("agent:manage"))])
def update_profile(agent_id: str, body: AgentProfileUpdate, request: Request,
                   application: CorporationApplicationService = Depends(get_application_service)):
    _csrf(request)
    try:
        return _summary(application.update_agent_profile(agent_id, **body.model_dump()))
    except ValueError as error:
        raise HTTPException(409, str(error)) from None


@router.put("/{agent_id}/pause", dependencies=[Depends(require_permission("agent:manage"))])
def pause_agent(agent_id: str, body: AgentPauseUpdate, request: Request,
                application: CorporationApplicationService = Depends(get_application_service)):
    _csrf(request)
    try:
        return _summary(application.set_agent_paused(agent_id, body.paused))
    except ValueError as error:
        raise HTTPException(409, str(error)) from None


@router.post("/{agent_id}/reset", dependencies=[Depends(require_permission("agent:manage"))])
def reset_agent(agent_id: str, request: Request,
                application: CorporationApplicationService = Depends(get_application_service)):
    _csrf(request)
    try:
        return _summary(application.reset_builtin_agent(agent_id))
    except ValueError as error:
        raise HTTPException(409, str(error)) from None


@router.post("/{agent_id}/duplicate", dependencies=[Depends(require_permission("agent:manage"))])
def duplicate_agent(agent_id: str, body: AgentDuplicateRequest, request: Request,
                    application: CorporationApplicationService = Depends(get_application_service)):
    _csrf(request)
    try:
        return _summary(application.duplicate_agent(agent_id, body.new_id, body.name))
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
