"""Local-owner workflow lifecycle, review and owner approval routes."""

from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from app.application.services.workflow_review import WorkflowConflict, WorkflowNotFound
from app.application.services.workflow_map import build_workflow_map
from .chat import get_application_service
from .security import require_permission


router = APIRouter(prefix="/api/local/workflows")
_READ = [Depends(require_permission("workflow:read"))]
_MANAGE = Depends(require_permission("workflow:manage"))


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DestinationRequest(_Strict):
    id: str = Field(min_length=1, max_length=64)
    kind: str = Field(pattern="^(local|online)$")
    provider_id: str = Field(min_length=1, max_length=256)
    model_id: str = Field(min_length=1, max_length=256)
    agent_id: str = Field(min_length=1, max_length=256)
    request_cost_cents: StrictInt | None = Field(default=None, ge=0, le=1_000_000)
    fallback_authorized: StrictBool = False


class WorkflowCreateRequest(_Strict):
    title: str = Field(min_length=1, max_length=256)
    task_id: str | None = Field(default=None, min_length=1, max_length=256)
    destinations: list[DestinationRequest] = Field(min_length=1, max_length=16)
    preference: str = Field(default="local_first", pattern="^(local_first|online_first)$")
    max_depth: StrictInt = Field(default=3, ge=1, le=3)
    max_children: StrictInt = Field(default=10, ge=0, le=10)
    spend_ceiling_cents: StrictInt | None = Field(default=None, ge=0, le=1_000_000)
    fallback_enabled: StrictBool = False


class WorkItemRequest(_Strict):
    role: str = Field(pattern="^(planner|worker|reviewer)$")
    agent_id: str = Field(min_length=1, max_length=256)
    prompt: str = Field(min_length=1, max_length=4096)
    parent_id: str | None = Field(default=None, max_length=64)
    source_id: str | None = Field(default=None, max_length=64)


class RunRequest(_Strict):
    confirmed: StrictBool
    cloud_consent_destinations: list[str] = Field(default_factory=list, max_length=16)


class ReviewRequest(_Strict):
    reviewer_agent_id: str = Field(min_length=1, max_length=256)
    passed: StrictBool
    evidence: str = Field(min_length=1, max_length=2048)


class ApproveRequest(_Strict):
    confirmed: StrictBool
    verification_evidence: str = Field(min_length=1, max_length=2048)


class ConfirmRequest(_Strict):
    confirmed: StrictBool


@contextmanager
def _safe():
    try:
        yield
    except WorkflowNotFound as error:
        raise HTTPException(404, str(error)) from None
    except WorkflowConflict as error:
        raise HTTPException(409, str(error)) from None
    except ValueError:
        raise HTTPException(422, "Invalid workflow request") from None


def _service(application):
    return application.workflow_review()


@router.get("", dependencies=_READ)
def list_workflows(application=Depends(get_application_service)):
    return {"workflows": _service(application).list()}


@router.get("/map")
def workflow_map(principal=Depends(require_permission("workflow:read")),
                 application=Depends(get_application_service)):
    return build_workflow_map(application, principal.permissions)

@router.get("/{workflow_id}", dependencies=_READ)
def get_workflow(workflow_id: str, application=Depends(get_application_service)):
    with _safe():
        return _service(application).report(workflow_id)


@router.post("", status_code=201)
def create_workflow(body: WorkflowCreateRequest, principal=_MANAGE,
                    application=Depends(get_application_service)):
    with _safe():
        for dest in body.destinations:
            if not application.provider_exists(dest.provider_id):
                raise ValueError("Unknown provider")
            cloud = application.provider_requires_explicit_cloud_consent(dest.provider_id)
            if cloud != (dest.kind == "online"):
                raise ValueError("Destination kind does not match the provider")
        return _service(application).create(
            principal.identity, body.title, task_id=body.task_id,
            destinations=[d.model_dump() for d in body.destinations],
            preference=body.preference, max_depth=body.max_depth,
            max_children=body.max_children, spend_ceiling_cents=body.spend_ceiling_cents,
            fallback_enabled=body.fallback_enabled,
        )


@router.post("/{workflow_id}/items", status_code=201, dependencies=[_MANAGE])
def add_item(workflow_id: str, body: WorkItemRequest,
             application=Depends(get_application_service)):
    with _safe():
        return _service(application).add_item(workflow_id, **body.model_dump())


@router.post("/{workflow_id}/items/{item_id}/run", dependencies=[_MANAGE])
def run_item(workflow_id: str, item_id: str, body: RunRequest,
             application=Depends(get_application_service)):
    with _safe():
        return _service(application).run(
            workflow_id, item_id, confirmed=body.confirmed,
            cloud_consent_destinations=body.cloud_consent_destinations,
        )


@router.post("/{workflow_id}/items/{item_id}/review", dependencies=[_MANAGE])
def review_item(workflow_id: str, item_id: str, body: ReviewRequest,
                application=Depends(get_application_service)):
    with _safe():
        return _service(application).review(workflow_id, item_id, **body.model_dump())


@router.post("/{workflow_id}/items/{item_id}/approve")
def approve_item(workflow_id: str, item_id: str, body: ApproveRequest, principal=_MANAGE,
                 application=Depends(get_application_service)):
    with _safe():
        return _service(application).approve(
            workflow_id, item_id, principal.identity, confirmed=body.confirmed,
            verification_evidence=body.verification_evidence,
        )


@router.post("/{workflow_id}/items/{item_id}/recover", dependencies=[_MANAGE])
def recover_item(workflow_id: str, item_id: str, body: ConfirmRequest,
                 application=Depends(get_application_service)):
    with _safe():
        return _service(application).recover(workflow_id, item_id, confirmed=body.confirmed)


@router.post("/{workflow_id}/pause", dependencies=[_MANAGE])
def pause(workflow_id: str, application=Depends(get_application_service)):
    with _safe():
        return _service(application).pause(workflow_id)


@router.post("/{workflow_id}/resume", dependencies=[_MANAGE])
def resume(workflow_id: str, application=Depends(get_application_service)):
    with _safe():
        return _service(application).resume(workflow_id)


@router.post("/{workflow_id}/cancel", dependencies=[_MANAGE])
def cancel(workflow_id: str, application=Depends(get_application_service)):
    with _safe():
        return _service(application).cancel(workflow_id)
