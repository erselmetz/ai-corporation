"""Owner controls and read-only suggestions for the explicitly configured local app."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.api.chat import get_application_service
from app.api.security import AuthenticatedPrincipal, require_permission
from app.application.services.owner_suggestions import OwnerSuggestionService, OwnerSuggestionsError

router = APIRouter(prefix="/api/local/suggestions", tags=["local-owner-suggestions"])


class SuggestionSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool | None = None
    quiet_start: str | None = Field(default=None, pattern=r"^(?:|(?:[01]\d|2[0-3]):[0-5]\d)$")
    quiet_end: str | None = Field(default=None, pattern=r"^(?:|(?:[01]\d|2[0-3]):[0-5]\d)$")


def _service(request: Request) -> OwnerSuggestionService:
    return request.app.state.owner_suggestion_service


@router.get("/preferences")
def get_preferences(principal: AuthenticatedPrincipal = Depends(require_permission("chat:read")),
                    service: OwnerSuggestionService = Depends(_service)):
    return {"preferences": service.get_preferences(principal.identity).__dict__}


@router.put("/preferences")
def update_preferences(body: SuggestionSettingsUpdate,
                       principal: AuthenticatedPrincipal = Depends(require_permission("chat:read")),
                       service: OwnerSuggestionService = Depends(_service)):
    changes = body.model_dump(exclude_unset=True)
    try:
        preferences = service.update_preferences(principal.identity, changes)
    except OwnerSuggestionsError as error:
        raise HTTPException(422, str(error)) from None
    return {"preferences": preferences.__dict__}


@router.get("")
def list_suggestions(principal: AuthenticatedPrincipal = Depends(require_permission("workflow:read")),
                     service: OwnerSuggestionService = Depends(_service),
                     application=Depends(get_application_service)):
    try:
        return service.list_suggestions(principal.identity, application.workflow_review())
    except OwnerSuggestionsError as error:
        raise HTTPException(409, str(error)) from None


@router.post("/{suggestion_id}/dismiss")
def dismiss_suggestion(suggestion_id: str,
                       principal: AuthenticatedPrincipal = Depends(require_permission("workflow:read")),
                       _owner=Depends(require_permission("chat:read")),
                       service: OwnerSuggestionService = Depends(_service),
                       application=Depends(get_application_service)):
    try:
        service.dismiss(principal.identity, suggestion_id, application.workflow_review())
    except OwnerSuggestionsError as error:
        raise HTTPException(409, str(error)) from None
    return {"dismissed": True}
