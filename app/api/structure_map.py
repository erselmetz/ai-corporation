"""Permission-gated read-only corporation structure map."""

from fastapi import APIRouter, Depends, Request

from app.application.services.structure_map import build_structure_map
from .security import require_permission

router = APIRouter()


@router.get("/api/structure-map")
def structure_map(
    request: Request,
    principal=Depends(require_permission("position:read")),
):
    return build_structure_map(request.app.state.application_service, principal.permissions)
