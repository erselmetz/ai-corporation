"""Explicit short-lived grants; no persistent capability policy is configured here."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr

from app.application.services.capability_grants import (
    CapabilityGrantConflict,
    CapabilityGrantNotFound,
    CapabilityGrantService,
)
from .security import AuthenticatedPrincipal, require_permission

router = APIRouter(prefix="/api/capabilities/grants")
GrantId = Annotated[str, Path(min_length=1, max_length=64)]


class GrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capability_id: StrictStr = Field(min_length=1, max_length=128)
    scope_type: StrictStr = Field(min_length=1, max_length=64)
    scope_id: StrictStr = Field(min_length=1, max_length=256)
    ttl_seconds: StrictInt = Field(ge=1, le=CapabilityGrantService.MAX_TTL_SECONDS)


class CapabilityEnableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


def service(request: Request) -> CapabilityGrantService:
    return request.app.state.capability_grant_service


def invoke(operation, grants: CapabilityGrantService):
    try:
        result = operation()
        if isinstance(result, dict):
            return result
        if isinstance(result, tuple):
            return {"items": [grants.snapshot(item) for item in result]}
        return grants.snapshot(result)
    except CapabilityGrantNotFound:
        raise HTTPException(404, "Capability or session grant unavailable") from None
    except CapabilityGrantConflict as error:
        raise HTTPException(409, str(error)) from None
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except (OSError, RuntimeError):
        raise HTTPException(503, "Capability grant service unavailable") from None


@router.get("/eligible")
def eligible(principal: AuthenticatedPrincipal = Depends(require_permission("capability-grant:manage")),
             grants: CapabilityGrantService = Depends(service)):
    return {"items": list(grants.eligible(identity=principal.identity,
                                           permissions=principal.permissions))}


@router.get("/policy")
def list_policy(principal: AuthenticatedPrincipal = Depends(require_permission("capability-grant:manage")),
                grants: CapabilityGrantService = Depends(service)):
    return {"items": list(grants.enabled_snapshot())}


@router.put("/policy/{capability_id}")
def set_policy(capability_id: Annotated[str, Path(min_length=1, max_length=128)],
               body: CapabilityEnableRequest, request: Request,
               principal: AuthenticatedPrincipal = Depends(require_permission("capability-grant:manage")),
               grants: CapabilityGrantService = Depends(service)):
    if principal.session_id is None:
        raise HTTPException(403, "Capability policy management requires an authenticated session")
    csrf = getattr(request.app.state.authentication_backend, "require_csrf", None)
    if callable(csrf):
        csrf(request)
    return invoke(lambda: grants.set_enabled(capability_id, enabled=body.enabled,
                                             actor_id=principal.identity), grants)


@router.get("")
def list_grants(principal: AuthenticatedPrincipal = Depends(require_permission("capability-grant:manage")),
                grants: CapabilityGrantService = Depends(service)):
    if principal.session_id is None:
        raise HTTPException(403, "Session-scoped grant management requires an authenticated session")
    return invoke(lambda: grants.list_for_session(grantor=principal.identity,
                                                  session_id=principal.session_id), grants)


@router.post("", status_code=201)
def create_grant(body: GrantRequest, request: Request,
                 principal: AuthenticatedPrincipal = Depends(require_permission("capability-grant:manage")),
                 grants: CapabilityGrantService = Depends(service)):
    if principal.session_id is None:
        raise HTTPException(403, "Session-scoped grant management requires an authenticated session")
    csrf = getattr(request.app.state.authentication_backend, "require_csrf", None)
    if callable(csrf):
        csrf(request)
    return invoke(lambda: grants.issue(grantor=principal.identity,
                                      permissions=principal.permissions,
                                      session_id=principal.session_id,
                                      capability_id=body.capability_id,
                                      scope_type=body.scope_type, scope_id=body.scope_id,
                                      ttl_seconds=body.ttl_seconds), grants)


@router.post("/{grant_id}/revoke")
def revoke_grant(grant_id: GrantId, request: Request,
                 principal: AuthenticatedPrincipal = Depends(require_permission("capability-grant:manage")),
                 grants: CapabilityGrantService = Depends(service)):
    if principal.session_id is None:
        raise HTTPException(403, "Session-scoped grant management requires an authenticated session")
    csrf = getattr(request.app.state.authentication_backend, "require_csrf", None)
    if callable(csrf):
        csrf(request)
    return invoke(lambda: grants.revoke(grant_id, grantor=principal.identity,
                                       session_id=principal.session_id), grants)
