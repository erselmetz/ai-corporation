"""Owner-protected read-only software and integration inventory."""

from pathlib import Path

from fastapi import APIRouter, Depends, Request

from app.application.services.provider_connections import ProviderConnectionsService
from app.inventory import build_software_inventory
from .chat import get_application_service
from .security import require_permission

router = APIRouter(prefix="/api/local/inventory")


def _provider_connections(request: Request, application):
    service = getattr(request.app.state, "provider_connections_service", None)
    if service is None:
        service = ProviderConnectionsService(application)
        request.app.state.provider_connections_service = service
    return service


@router.get("", dependencies=[Depends(require_permission("inventory:read"))])
def read_inventory(request: Request, application=Depends(get_application_service)):
    connections = _provider_connections(request, application).list()
    assignments = application.list_models()
    return build_software_inventory(
        checkout_root=Path(__file__).resolve().parents[2],
        provider_connections=connections,
        assignments=assignments,
        application_version=request.app.version,
    )
