"""Explicit local-owner endpoints for the single supported software adapter."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.application.services.managed_software import ManagedSoftwareService, SoftwareManagementError
from .security import require_permission

router = APIRouter(prefix="/api/local/software")


class SoftwarePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(min_length=1, max_length=16)
    version: str | None = Field(default=None, min_length=1, max_length=32)


class SoftwareConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation_id: str = Field(min_length=32, max_length=32, pattern="^[0-9a-f]{32}$")
    preview_sha256: str = Field(min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")


def _service(request: Request) -> ManagedSoftwareService:
    service = getattr(request.app.state, "managed_software_service", None)
    if service is None:
        service = ManagedSoftwareService()
        request.app.state.managed_software_service = service
    return service


@router.get("", dependencies=[Depends(require_permission("software:read"))])
def read_managed_software(request: Request):
    try:
        return _service(request).status()
    except SoftwareManagementError as error:
        raise HTTPException(503, str(error)) from None


@router.post("/preview", dependencies=[Depends(require_permission("software:manage"))])
def preview_managed_software(body: SoftwarePreviewRequest, request: Request):
    try:
        return _service(request).preview(body.action, body.version)
    except PermissionError as error:
        raise HTTPException(403, str(error)) from None
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except SoftwareManagementError as error:
        raise HTTPException(409, str(error)) from None


@router.post("/confirm", dependencies=[Depends(require_permission("software:manage"))])
def confirm_managed_software(body: SoftwareConfirmationRequest, request: Request):
    try:
        return _service(request).confirm(body.confirmation_id, body.preview_sha256)
    except PermissionError as error:
        raise HTTPException(409, str(error)) from None
    except SoftwareManagementError as error:
        raise HTTPException(409, str(error)) from None
