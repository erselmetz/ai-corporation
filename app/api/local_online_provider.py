"""Credential-bearing Gemini controls mounted only in explicit local-owner mode."""
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.application.services.local_online_provider import LocalOnlineProviderService
from app.integrations.gemini_chat import GeminiConnectionError
from .chat import get_application_service
from .security import require_permission


class CatalogRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: str = Field(min_length=1, max_length=4096, repr=False)


class ConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: str = Field(min_length=1, max_length=256)
    model_id: str = Field(min_length=1, max_length=256)


def create_local_online_provider_router(connection_manager):
    router = APIRouter(prefix="/api/local/online-provider")

    @contextmanager
    def safe_operation():
        try:
            yield
        except GeminiConnectionError as error:
            raise HTTPException(409, str(error)) from None
        except ValueError:
            raise HTTPException(422, "Gemini connection or model selection is invalid") from None
        except Exception:
            raise HTTPException(502, "Gemini operation failed. Check provider status and account limits.") from None

    def service(request: Request, application=Depends(get_application_service)):
        result = getattr(request.app.state, "local_online_provider", None)
        if result is None:
            result = LocalOnlineProviderService(application, connection_manager)
            request.app.state.local_online_provider = result
        return result

    @router.get("")
    def status(_principal=Depends(require_permission("model:read")), setup=Depends(service)):
        return setup.inventory()

    @router.post("/catalog")
    async def catalog(request: Request, principal=Depends(require_permission("online-provider:connect")),
                      setup=Depends(service)):
        payload = bytearray()
        async for chunk in request.stream():
            if len(payload) + len(chunk) > 8192:
                payload[:] = b"\0" * len(payload)
                raise HTTPException(413, "Gemini setup request too large")
            payload.extend(chunk)
        try:
            body = CatalogRequest.model_validate_json(bytes(payload))
        except ValueError:
            raise HTTPException(422, "Invalid Gemini setup fields") from None
        finally:
            payload[:] = b"\0" * len(payload)
        with safe_operation():
            try:
                return setup.discover(body.api_key)
            finally:
                del body

    @router.post("/catalog/refresh")
    def refresh(_principal=Depends(require_permission("online-provider:connect")), setup=Depends(service)):
        with safe_operation():
            return setup.refresh()

    @router.put("/connection")
    async def connect(request: Request, principal=Depends(require_permission("online-provider:connect")),
                      setup=Depends(service)):
        from app.api.chat import bounded_body
        payload = await bounded_body(request)
        try:
            body = ConnectRequest.model_validate_json(payload)
        except ValueError:
            raise HTTPException(422, "Invalid Gemini connection fields") from None
        with safe_operation():
            return setup.connect(body.agent_id, body.model_id)

    @router.delete("/connection/{agent_id}")
    def disconnect(agent_id: str, _principal=Depends(require_permission("online-provider:disconnect")),
                   setup=Depends(service)):
        with safe_operation():
            return setup.disconnect(agent_id)

    @router.delete("/credential")
    def erase_credential(_principal=Depends(require_permission("online-provider:disconnect")),
                         setup=Depends(service)):
        with safe_operation():
            return setup.clear_staged_credential()

    return router
