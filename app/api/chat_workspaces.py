"""Authenticated workspace registration; selection never changes Agent assignments."""
from dataclasses import asdict
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from .chat import bounded_body, get_application_service, parse
from .security import require_permission

router = APIRouter(prefix="/api/chat/workspaces")


@router.get("/models")
def workspace_models(principal=Depends(require_permission("chat:read")), application=Depends(get_application_service)):
    routes = {(agent.provider, agent.model) for agent in application.list_agents() if agent.model}
    for provider in application.list_providers():
        if not application.provider_is_local(provider.id):
            continue  # Never contact an online provider for this catalog.
        try:
            inventory = application.local_model_inventory(provider.id)
            if inventory.state == "available":
                routes.update((provider.id, model) for model in inventory.models)
        except (ValueError, RuntimeError):
            continue
    return {"items": [{"provider_id": provider, "model_id": model} for provider, model in sorted(routes)]}


class WorkspaceSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=80)
    agent_id: str = Field(min_length=1, max_length=256)
    provider_id: str = Field(default="", max_length=256)
    model_id: str = Field(default="", max_length=256)
    project_id: str = Field(default="", max_length=256)


class ProjectBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=1, max_length=256)
    brief: str = Field(max_length=2000)


@router.post("/project-brief")
def save_project_brief(request: Request, payload=Depends(bounded_body),
                       principal=Depends(require_permission("chat:send")), application=Depends(get_application_service)):
    require_permission("project:read")(request, principal)
    body = parse(ProjectBrief, payload)
    try:
        return application.chat_workspaces().save_brief(principal.identity, body.project_id, body.brief)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


@router.post("")
def open_workspace(request: Request, payload=Depends(bounded_body), principal=Depends(require_permission("chat:start")),
                   application=Depends(get_application_service)):
    body = parse(WorkspaceSelection, payload)
    if body.project_id:
        require_permission("project:read")(request, principal)
    try:
        return asdict(application.chat_workspaces().open(
            principal.identity, body.id, agent_id=body.agent_id, provider_id=body.provider_id,
            model_id=body.model_id, project_id=body.project_id))
    except PermissionError:
        raise HTTPException(404, "Workspace unavailable") from None
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
