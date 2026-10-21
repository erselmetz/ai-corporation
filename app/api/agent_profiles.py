"""Owner-only profile controls for the existing Agent and Employee records."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

from app.application.services.corporation import CorporationApplicationService
from .app import get_application_service
from .security import AuthenticatedPrincipal, require_permission
from app.application.services.owned_chat import ChatConflict, ChatNotFound


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


@status_router.get("/sage-core", dependencies=[Depends(require_permission("chat:read"))])
def sage_core_snapshot(principal: AuthenticatedPrincipal = Depends(require_permission("agent:read")),
                       application: CorporationApplicationService = Depends(get_application_service)):
    """Return a bounded Agent-state and trace-link snapshot without conversation content."""
    agents = application.list_agents()[:100]
    statuses = {item["agent_id"]: item for item in application.agent_runtime_statuses()}
    nodes = [{
        "id": agent.id, "name": agent.name, "role": agent.role,
        "provider": agent.provider, "model": agent.model,
        "built_in": bool(agent.builtin),
        "built_in_key": application.get_agent_profile(agent.id).builtin_key,
        "state": statuses.get(agent.id, {}).get("status", "unknown"),
        "reason": statuses.get(agent.id, {}).get("reason"),
        "last_active": statuses.get(agent.id, {}).get("last_active"),
    } for agent in agents]
    node_ids = {agent.id for agent in agents}
    handoffs, source_links = [], []
    now = datetime.now(timezone.utc)
    conversations = application.owned_chat().list(principal.identity)[-20:]
    for conversation in reversed(conversations):
        try:
            traces = application.chat_knowledge().traces(principal.identity, conversation["id"], now)
        except (ChatConflict, ChatNotFound, PermissionError, ValueError):
            continue
        for reply_id, trace in traces.items():
            if not isinstance(trace, dict):
                continue
            retrieved_at = trace.get("retrieved_at")
            handoff = trace.get("handoff")
            if isinstance(handoff, dict) and handoff.get("status") in {"completed", "failed"}:
                coordinator = handoff.get("coordinator")
                responder = handoff.get("agent")
                from_id = coordinator.get("id") if isinstance(coordinator, dict) else None
                to_id = responder.get("id") if isinstance(responder, dict) else None
                if from_id in node_ids and to_id in node_ids and len(handoffs) < 60:
                    handoffs.append({"id": f"{conversation['id']}:{reply_id}", "from": from_id,
                                     "to": to_id, "state": handoff["status"],
                                     "recorded_at": retrieved_at})
            route = trace.get("route") if isinstance(trace.get("route"), dict) else {}
            agent_id = route.get("responder_agent_id") or route.get("agent_id")
            if agent_id not in node_ids:
                continue
            for source in trace.get("sources", [])[:5] if isinstance(trace.get("sources"), list) else []:
                if (not isinstance(source, dict) or source.get("freshness") != "current"
                        or not isinstance(source.get("memory_id"), str)):
                    continue
                if len(source_links) >= 100:
                    break
                source_links.append({
                    "id": f"{conversation['id']}:{reply_id}:{source['memory_id']}",
                    "agent_id": agent_id, "source_id": source["memory_id"],
                    "label": str(source.get("source") or source.get("origin_reference") or "Brain source")[:128],
                    "recorded_at": retrieved_at,
                })
    return {"nodes": nodes, "handoffs": handoffs, "source_links": source_links,
            "observed_at": now.isoformat(), "limits": {"agents": 100, "conversations": 20,
                                                            "handoffs": 60, "source_links": 100}}


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
