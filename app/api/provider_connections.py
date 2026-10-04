"""Local-owner provider connection configuration and explicit Agent assignment."""
from contextlib import contextmanager
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.application.services.provider_connections import (
    ProviderConnectionConflict,
    ProviderConnectionUnavailable,
    ProviderConnectionsService,
)
from .chat import bounded_body, get_application_service
from .security import require_permission


_SUPPORTED_GEMINI_KEY = re.compile(r"AIza[A-Za-z0-9_-]{35}\Z")
router = APIRouter(prefix="/api/local/provider-connections")


class OllamaConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=48)
    name: str = Field(min_length=1, max_length=256)
    base_url: str = Field(min_length=1, max_length=2048)
    request_slots: StrictInt = Field(ge=1, le=16)


class GeminiConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=48)
    name: str = Field(min_length=1, max_length=256)
    api_key: str = Field(min_length=1, max_length=4096, repr=False)
    request_slots: StrictInt = Field(ge=1, le=16)


class ProviderAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(min_length=1, max_length=256)
    provider_id: str = Field(min_length=1, max_length=256)
    model_id: str = Field(min_length=1, max_length=256)
    expected_provider_id: str = Field(min_length=1, max_length=256)
    expected_model_id: str = Field(min_length=1, max_length=256)


def _connection_service(request: Request, application=Depends(get_application_service)):
    service = getattr(request.app.state, "provider_connections_service", None)
    if service is None:
        service = ProviderConnectionsService(application)
        request.app.state.provider_connections_service = service
    return service


@contextmanager
def _safe_operation():
    try:
        yield
    except ProviderConnectionConflict as error:
        raise HTTPException(409, str(error)) from None
    except ProviderConnectionUnavailable as error:
        raise HTTPException(503, str(error)) from None
    except ValueError:
        raise HTTPException(422, "Provider connection or assignment is invalid") from None


@router.get("", dependencies=[Depends(require_permission("provider-connection:read"))])
def list_connections(service=Depends(_connection_service)):
    items = service.list()
    return {
        "items": list(items),
        "capacity": {
            "global_request_slots": sum(
                item["request_capacity"].get("provider_slots", 0) for item in items
            ),
            "hardware_feasibility": "unknown",
        },
    }


@router.post("/ollama", status_code=201,
             dependencies=[Depends(require_permission("provider-connection:manage"))])
def add_ollama_connection(payload=Depends(bounded_body), service=Depends(_connection_service)):
    try:
        body = OllamaConnectionRequest.model_validate_json(payload)
    except ValueError:
        raise HTTPException(422, "Invalid Ollama connection fields") from None
    with _safe_operation():
        return service.add_ollama(body.id, body.name, body.base_url, body.request_slots)


@router.post("/gemini", status_code=201,
             dependencies=[Depends(require_permission("provider-connection:manage"))])
async def add_gemini_connection(
    request: Request,
    service=Depends(_connection_service),
):
    payload = bytearray()
    try:
        async for chunk in request.stream():
            if len(payload) + len(chunk) > 8192:
                raise HTTPException(413, "Gemini setup request too large")
            payload.extend(chunk)
        try:
            body = GeminiConnectionRequest.model_validate_json(payload)
        except ValueError:
            raise HTTPException(422, "Invalid Gemini connection fields") from None
    finally:
        payload[:] = b"\0" * len(payload)
    if _SUPPORTED_GEMINI_KEY.fullmatch(body.api_key) is None:
        del body
        raise HTTPException(422, "Unsupported Gemini API key format")
    try:
        with _safe_operation():
            return service.add_gemini(
                body.id, body.name, body.api_key, body.request_slots
            )
    finally:
        del body


@router.post("/{provider_id}/refresh",
             dependencies=[Depends(require_permission("provider-connection:manage"))])
def refresh_connection(provider_id: str, service=Depends(_connection_service)):
    with _safe_operation():
        return service.refresh(provider_id)


@router.put("/assignment",
            dependencies=[Depends(require_permission("provider-connection:manage"))])
def assign_provider(payload=Depends(bounded_body), service=Depends(_connection_service)):
    try:
        body = ProviderAssignmentRequest.model_validate_json(payload)
    except ValueError:
        raise HTTPException(422, "Invalid Agent assignment fields") from None
    with _safe_operation():
        return service.assign(
            body.agent_id,
            body.provider_id,
            body.model_id,
            body.expected_provider_id,
            body.expected_model_id,
        )


@router.delete("/{provider_id}", status_code=204,
               dependencies=[Depends(require_permission("provider-connection:manage"))])
def remove_connection(provider_id: str, service=Depends(_connection_service)):
    with _safe_operation():
        service.remove(provider_id)
