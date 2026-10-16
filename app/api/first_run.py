"""Local-owner first-run setup. Mounted only by explicitly configured local apps."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.application.services.first_run_setup import OllamaFirstRunService
from app.application.services.owned_chat import ChatConflict, ChatLimit
from app.resources import ModelLimit, ProviderLimit, ResourceLimits
from .chat import bounded_body, get_application_service
from .security import require_permission


GEMINI_DEFAULT_MODEL = "gemini-3.8-flash"
router = APIRouter(prefix="/api/local/first-run")


class GeminiSetupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: str = Field(min_length=1, max_length=4096, repr=False)
    remember_key: StrictBool = False


class OllamaPullRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: StrictBool
    manifest_digest: str = Field(min_length=71, max_length=71)
    manifest_bytes: int = Field(gt=0, le=OllamaFirstRunService.MAX_MODEL_BYTES)


def _state(request: Request):
    store = getattr(request.app.state, "first_run_setup_store", None)
    if store is None or not getattr(request.app.state, "first_run_enabled", False):
        return None
    return store.get()


def _configure_slots(application, provider_id: str, model_id: str) -> None:
    limits = ResourceLimits(
        global_slots=1,
        providers=(ProviderLimit(provider_id, 1),),
        models=(ModelLimit(provider_id, model_id, 1),),
    )
    application.resource_manager(limits)


def _online_provider_service(request: Request, application):
    service = getattr(request.app.state, "local_online_provider", None)
    if service is None:
        from app.application.services.local_online_provider import LocalOnlineProviderService
        service = LocalOnlineProviderService(
            application, request.app.state.gemini_connection_manager,
        )
        request.app.state.local_online_provider = service
    return service


def _start_coordinator_chat(application, owner_id: str) -> dict:
    try:
        return application.owned_chat().start(owner_id, "local_worker")
    except (ChatConflict, ChatLimit, ValueError):
        raise HTTPException(503, "Setup is ready, but the Coordinator conversation could not be opened. Retry from Chat.") from None


def _complete_ollama_setup(request: Request, principal, application, model_id: str) -> dict:
    application.replace_model("local_worker", "ollama", model_id)
    request.app.state.first_run_setup_store.complete_ollama(model_id)
    secret_store = getattr(request.app.state, "first_run_secret_store", None)
    if secret_store is not None:
        secret_store.clear()
    _configure_slots(application, "ollama", model_id)
    request.app.state.first_run_reconnect_required = False
    conversation = _start_coordinator_chat(application, principal.identity)
    return {"setup_complete": True, "conversation_id": conversation["conversation"].id,
            "provider_id": "ollama", "model_id": model_id}


@router.get("", dependencies=[Depends(require_permission("provider-connection:read"))])
def first_run_state(request: Request):
    config = _state(request)
    if config is None:
        return {"enabled": False, "completed": True, "skipped": False,
                "credential_needs_reentry": False}
    credential_needs_reentry = bool(
        getattr(request.app.state, "first_run_reconnect_required", False)
    )
    return {
        "enabled": True,
        "completed": config.completed and not credential_needs_reentry,
        "skipped": config.skipped,
        "provider_type": config.provider_type,
        "provider_id": config.provider_id,
        "model_id": config.model_id,
        "credential_persisted": config.gemini_key_persisted,
        "credential_needs_reentry": credential_needs_reentry,
        "hardware_feasibility": "unknown",
    }


@router.post("/skip", dependencies=[Depends(require_permission("provider-connection:manage"))])
def skip_setup(request: Request):
    if _state(request) is None:
        raise HTTPException(404, "First-run setup is unavailable")
    try:
        request.app.state.first_run_setup_store.skip()
    except RuntimeError:
        raise HTTPException(409, "First-run setup is not pending") from None
    return {"skipped": True, "configured": False}


@router.post("/ollama/status", dependencies=[Depends(require_permission("provider-connection:manage"))])
def ollama_status(request: Request):
    if _state(request) is None:
        raise HTTPException(404, "First-run setup is unavailable")
    return request.app.state.first_run_ollama_service.status()


@router.post("/ollama/model-preview", dependencies=[Depends(require_permission("provider-connection:manage"))])
def ollama_model_preview(request: Request):
    if _state(request) is None:
        raise HTTPException(404, "First-run setup is unavailable")
    try:
        return request.app.state.first_run_ollama_service.preview_model()
    except ValueError as error:
        raise HTTPException(503, str(error)) from None


@router.post("/ollama/use-installed", dependencies=[Depends(require_permission("provider-connection:manage"))])
def ollama_use_installed(request: Request, _payload=Depends(bounded_body),
                         principal=Depends(require_permission("provider-connection:manage")),
                         application=Depends(get_application_service)):
    if _state(request) is None:
        raise HTTPException(404, "First-run setup is unavailable")
    status = request.app.state.first_run_ollama_service.status()
    if status.get("state") != "available" or status.get("model_installed") is not True:
        raise HTTPException(409, "Ollama has not confirmed the recommended model as installed")
    try:
        return _complete_ollama_setup(request, principal, application, OllamaFirstRunService.MODEL_ID)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "The installed model was verified, but first-run setup could not be finalized. Retry setup from the local app.") from None


@router.post("/ollama/pull", dependencies=[Depends(require_permission("provider-connection:manage"))])
def ollama_pull(
    request: Request,
    payload=Depends(bounded_body),
    principal=Depends(require_permission("provider-connection:manage")),
    application=Depends(get_application_service),
):
    if _state(request) is None:
        raise HTTPException(404, "First-run setup is unavailable")
    try:
        body = OllamaPullRequest.model_validate_json(payload)
    except ValueError:
        raise HTTPException(422, "Invalid model download confirmation") from None
    if body.confirmed is not True:
        raise HTTPException(409, "Explicit model download confirmation is required")
    pull_service = request.app.state.first_run_ollama_service

    def stream():
        finished = False
        try:
            for line in pull_service.pull(
                expected_digest=body.manifest_digest,
                expected_bytes=body.manifest_bytes,
            ):
                try:
                    event = json.loads(line)
                except ValueError:
                    yield json.dumps({"event": "error", "message": "Download progress was invalid."}) + "\n"
                    return
                if event.get("event") == "complete":
                    try:
                        result = _complete_ollama_setup(request, principal, application, pull_service.MODEL_ID)
                        event = {**event, **result}
                        finished = True
                    except HTTPException as error:
                        yield json.dumps({"event": "error", "message": error.detail}) + "\n"
                        return
                    except Exception:
                        yield json.dumps({"event": "error", "message": "The model is installed, but first-run setup could not be finalized. Retry setup from the local app."}) + "\n"
                        return
                yield json.dumps(event, separators=(",", ":")) + "\n"
            if not finished:
                return
        finally:
            del body

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.post("/gemini/complete", dependencies=[Depends(require_permission("online-provider:connect"))])
async def gemini_complete(
    request: Request,
    payload=Depends(bounded_body),
    principal=Depends(require_permission("online-provider:connect")),
    application=Depends(get_application_service),
):
    config = _state(request)
    if config is None:
        raise HTTPException(404, "First-run setup is unavailable")
    try:
        body = GeminiSetupRequest.model_validate_json(payload)
    except ValueError:
        raise HTTPException(422, "Invalid Gemini setup fields") from None
    online_service = _online_provider_service(request, application)
    from app.api.local_online_provider import _SUPPORTED_GEMINI_KEY
    if _SUPPORTED_GEMINI_KEY.fullmatch(body.api_key) is None:
        del body
        raise HTTPException(422, "Use a supported Google AIza API key")
    api_key = body.api_key
    remember_key = body.remember_key
    try:
        # This action explicitly requests Google's model catalog. No prompt or
        # conversation is sent until a separate chat-turn consent.
        result = online_service.discover(api_key)
        models = tuple(result["models"])
        if GEMINI_DEFAULT_MODEL not in models:
            online_service.clear_staged_credential()
            raise HTTPException(409, "The recommended Gemini model is unavailable for this key. No provider assignment was changed; retry or skip setup.")
        online_service.connect_from_discovery(
            "local_worker", GEMINI_DEFAULT_MODEL,
            expected_provider_id=application.get_agent("local_worker").provider,
            expected_model_id=application.get_agent("local_worker").model,
        )
        secret_store = getattr(request.app.state, "first_run_secret_store", None)
        try:
            if remember_key:
                if secret_store is None:
                    raise ValueError("Current-Windows-user credential storage is unavailable")
                secret_store.save(api_key)
            else:
                if secret_store is not None:
                    secret_store.clear()
            request.app.state.first_run_setup_store.complete_gemini(
                GEMINI_DEFAULT_MODEL, models, key_persisted=remember_key,
            )
            _configure_slots(application, "gemini", GEMINI_DEFAULT_MODEL)
        except Exception:
            online_service.disconnect("local_worker")
            if secret_store is not None:
                secret_store.clear()
            raise
        request.app.state.first_run_reconnect_required = False
        conversation = _start_coordinator_chat(application, principal.identity)
        return {"setup_complete": True,
                "conversation_id": conversation["conversation"].id,
                "provider_id": "gemini", "model_id": GEMINI_DEFAULT_MODEL,
                "credential_persisted": remember_key,
                "next_step": "Coordinator Chat"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Gemini setup could not be completed. The key was not returned or logged; retry or skip setup.") from None
    finally:
        del body
        del api_key
