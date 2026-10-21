"""Owner-scoped presentation preferences for the explicitly configured local app."""
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from app.api.security import AuthenticatedPrincipal, require_permission
from app.application.services.owner_preferences import (
    OwnerPreferencesError,
    OwnerPreferencesService,
    RETENTION_NOTICE,
)

router = APIRouter(prefix="/api/local/preferences", tags=["local-owner-preferences"])


class PreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response_mode: str | None = Field(default=None, max_length=20)
    locale: str | None = Field(default=None, max_length=10)
    detail_level: str | None = Field(default=None, max_length=20)
    voice_mode: str | None = Field(default=None, max_length=10)
    voice_language: str | None = Field(default=None, max_length=10)
    voice_id: str | None = Field(default=None, max_length=160)
    autonomy_level: Literal["chat_only", "auto_safe", "ask_every_action"] | None = None


def _service(request: Request) -> OwnerPreferencesService:
    return request.app.state.owner_preferences_service


def _body(preferences):
    return {"preferences": preferences.__dict__, "retention": RETENTION_NOTICE}


@router.get("", dependencies=[Depends(require_permission("chat:read"))])
def read_preferences(principal: AuthenticatedPrincipal = Depends(require_permission("chat:read")),
                     service: OwnerPreferencesService = Depends(_service)):
    try:
        return _body(service.get(principal.identity))
    except OwnerPreferencesError as error:
        raise HTTPException(409, str(error)) from None


@router.get("/export", dependencies=[Depends(require_permission("chat:read"))])
def export_preferences(principal: AuthenticatedPrincipal = Depends(require_permission("chat:read")),
                       service: OwnerPreferencesService = Depends(_service)):
    try:
        return service.export(principal.identity)
    except OwnerPreferencesError as error:
        raise HTTPException(409, str(error)) from None


@router.put("", dependencies=[Depends(require_permission("chat:read"))])
def update_preferences(body: PreferenceUpdate,
                       principal: AuthenticatedPrincipal = Depends(require_permission("chat:read")),
                       service: OwnerPreferencesService = Depends(_service)):
    try:
        changes = {key: value for key, value in body.model_dump(exclude_unset=True).items() if value is not None}
        return _body(service.update(principal.identity, changes))
    except OwnerPreferencesError as error:
        raise HTTPException(422, str(error)) from None


@router.post("/reset", dependencies=[Depends(require_permission("chat:read"))])
def reset_preferences(principal: AuthenticatedPrincipal = Depends(require_permission("chat:read")),
                      service: OwnerPreferencesService = Depends(_service)):
    return _body(service.reset(principal.identity))
