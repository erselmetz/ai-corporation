"""Authorized owned chat; routes depend only on application services."""
import base64
import binascii
import re
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from starlette.responses import StreamingResponse

from app.application.services.github_inspection import (
    GitHubInspectionRateLimited,
    GitHubInspectionRequestError,
    GitHubInspectionUnavailable,
    GitHubRepositoryNotFound,
    GitHubRepositoryScopeDenied,
)
from app.application.services.repository_study import RepositoryStudyService
from app.application.services.chat_history import ChatHistoryError
from app.application.services.capability_authorization import (
    CapabilityAuthorizationDenied,
    DEFAULT_CAPABILITY_AUTHORIZATION,
)
from app.application.services.chat_knowledge import (
    ContextRequest, KnowledgeNotFound, SelectedKnowledgeScope,
)
from app.application.services.reviewed_chat_tools import run_reviewed_tools
from app.application.services.chat_route_suggestions import suggest_route
from app.application.services.owned_chat import (
    ChatConflict, ChatConsentRequired, ChatLimit, ChatNotFound, ChatUnavailable,
)
from app.application.services.chat_task_proposals import (
    ChatTaskProposalConflict,
    ChatTaskProposalExpired,
    ChatTaskProposalNotFound,
)
from app.memory import MemoryScope
from app.conversations import ConversationStatus
from app.integrations import (
    GitHubRateLimitError,
    ProposalGenerationError,
    SourceAnalysisError,
)
from app.providers.base import ProviderCapacityError, ProviderCapacityUnknown
from .security import require_permission

router = APIRouter(prefix="/api/chat/conversations")
_GEMINI_KEY_PATTERN = re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b")
_GEMINI_KEY_ASSIGNMENT_PATTERN = re.compile(
    r"\b(?:GEMINI|GOOGLE)_API_KEY\s*=\s*\S+", re.IGNORECASE
)
SECRET_PASTE_GUIDANCE = (
    "This message looks like it contains a Gemini API key. It was not saved or sent. "
    "Use the Gemini online setup page to connect a key."
)


def contains_gemini_key(text: str) -> bool:
    return bool(
        _GEMINI_KEY_PATTERN.search(text)
        or _GEMINI_KEY_ASSIGNMENT_PATTERN.search(text)
    )


def _presentation_preferences(request: Request, owner_id: str):
    store = getattr(request.app.state, "owner_preferences_service", None)
    return store.response_contract(owner_id) if store is not None else None


def get_application_service(request: Request):
    return request.app.state.application_service


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: str = Field(min_length=1, max_length=256)


class ChatContextBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=1024)
    scope: MemoryScope
    scope_id: str = Field(min_length=1, max_length=256)
    limit: int = Field(default=3, ge=1, le=3)


class KnowledgeScopeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: MemoryScope
    scope_id: str = Field(default="", max_length=256)


class KnowledgePreviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=8192)
    scopes: list[KnowledgeScopeBody] = Field(min_length=1, max_length=3)


class CalculatorToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["calculator"]
    expression: str = Field(min_length=1, max_length=256)


class LocalDocumentToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["local-document-lookup"]
    document_id: str = Field(min_length=1, max_length=256)
    query: str = Field(min_length=1, max_length=160)


ReviewedToolRequest = Annotated[
    CalculatorToolRequest | LocalDocumentToolRequest,
    Field(discriminator="kind"),
]


class SendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=8192)
    cloud_consent: bool = False
    image_ids: list[str] = Field(default_factory=list, max_length=4)
    image_consent: StrictBool = False
    include_local_ocr: StrictBool = False
    context: ChatContextBody | None = None
    knowledge_enabled: StrictBool = False
    knowledge_scopes: list[KnowledgeScopeBody] = Field(default_factory=list, max_length=3)
    knowledge_preview_digest: str | None = Field(default=None, min_length=64, max_length=64)
    capture_local_prompt: StrictBool = False
    reviewed_tools: list[ReviewedToolRequest] = Field(default_factory=list, max_length=2)
    route_provider_id: str | None = Field(default=None, min_length=1, max_length=256)
    route_model_id: str | None = Field(default=None, min_length=1, max_length=256)
    route_consent: StrictBool = False


class RouteSuggestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=8192)


class RetainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str = Field(min_length=1, max_length=256)
    expires_at: datetime
    retention_opt_in: StrictBool


class ImageUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_type: str = Field(min_length=1, max_length=32)
    data_base64: str = Field(min_length=1, max_length=2_800_000)


class ScreenCaptureUploadRequest(ImageUploadRequest):
    display_surface: Literal["monitor", "window", "browser"]
    captured_at: datetime


class CameraCaptureUploadRequest(ImageUploadRequest):
    captured_at: datetime


def get_chat_now():
    return datetime.now(timezone.utc)


def _selected_scopes(scopes):
    return tuple(SelectedKnowledgeScope(item.scope, item.scope_id) for item in scopes)


def _knowledge_preview(service, owner, identifier, query, scopes, now):
    try:
        result = service.chat_knowledge().retrieve_selected(
            owner, identifier, query, _selected_scopes(scopes), now)
    except PermissionError:
        raise HTTPException(403, "Selected knowledge scope is not available to this owner.") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception:
        raise HTTPException(503, "Selected knowledge could not be retrieved safely.") from None
    return result


def _workflow_steps(retrieval, tools, coordinator, *, retrieval_ms=0,
                    answer_ms=None, answer_status="completed", turn_route=None):
    steps = [{"step": "plan", "status": "completed", "source": "bounded configured chat workflow",
              "duration_ms": 0}]
    if retrieval:
        sources = retrieval.get("returned_chunks", retrieval.get("sources", []))
        labels = []
        for source in sources[:5] if isinstance(sources, list) else []:
            if isinstance(source, dict):
                label = source.get("source") or source.get("origin_reference") or source.get("memory_id")
                if label:
                    labels.append(str(label)[:128])
        steps.append({"step": "retrieve", "status": "completed",
                      "source": ", ".join(labels)[:512] if labels else "selected knowledge (no matching excerpts)",
                      "result_count": len(sources) if isinstance(sources, list) else 0,
                      "duration_ms": max(0, int(retrieval_ms))})
    else:
        steps.append({"step": "retrieve", "status": "skipped", "source": None,
                      "reason": "No separate knowledge retrieval was selected.", "duration_ms": 0})
    if tools:
        for item in tools[:2]:
            steps.append({"step": item.get("tool", "tool"),
                          "status": "completed" if item.get("outcome") == "completed" else "failed",
                          "source": str(item.get("source", "source unknown"))[:256],
                          "duration_ms": max(0, int(item.get("duration_ms", 0))),
                          "result_characters": max(0, int(item.get("result_characters", 0)))})
    else:
        steps.append({"step": "tools", "status": "skipped", "source": None,
                      "reason": "No reviewed tools were selected.", "duration_ms": 0})
    answer_step = {"step": "answer", "status": answer_status,
                   "source": (f"owner-approved per-turn route {turn_route[0]}/{turn_route[1]}"
                              if turn_route else "configured coordinator (see route details)")}
    if answer_ms is not None:
        answer_step["duration_ms"] = max(0, int(answer_ms))
    steps.append(answer_step)
    return steps


def _record_unverified_turn(service, knowledge, owner, identifier, coordinator,
                            cloud_provider, cloud_consent, elapsed_ms, auto_context,
                            retrieved, trace_request, now, tools=None, retrieval_ms=0,
                            answer_ms=None, turn_route=None, vision=None):
    """Record only a failed/pending user turn; never serialize the raw exception."""
    try:
        record = service.owned_chat().get(owner, identifier)["conversation"]
        message = next((item for item in reversed(record.messages)
                        if item.role.value == "user" and item.status.value in {"failed", "pending"}), None)
        if message is None:
            return
        if auto_context:
            retrieval_trace = {"enabled": True, **auto_context["trace"]}
        elif retrieved is not None:
            retrieval_trace = knowledge.record_trace(owner, identifier, message.id,
                                                     retrieved, trace_request, now)
        else:
            retrieval_trace = None
        knowledge.record_turn_trace(
            owner, identifier, message.id, coordinator=coordinator,
            cloud_provider=cloud_provider, cloud_consent=cloud_consent,
            elapsed_ms=elapsed_ms, retrieval=retrieval_trace,
            tools=tools,
            steps=_workflow_steps(retrieval_trace, tools, coordinator,
                                  retrieval_ms=retrieval_ms,
                                  answer_ms=answer_ms,
                                  answer_status="failed" if message.status.value == "failed" else "unknown",
                                  turn_route=turn_route),
            turn_route=turn_route,
            outcome="failed" if message.status.value == "failed" else "unknown",
            failure="Provider or chat runtime did not produce a verified reply; raw diagnostics are omitted.",
            now=now, vision=vision)
    except Exception:
        # A diagnostic trace must never replace or disclose the original chat failure.
        return


@router.post("/{identifier}/knowledge-preview")
def preview_knowledge(identifier: str, body: KnowledgePreviewBody,
                      principal=Depends(require_permission("chat:send")),
                      service=Depends(get_application_service), now=Depends(get_chat_now)):
    if contains_gemini_key(body.query):
        raise HTTPException(422, SECRET_PASTE_GUIDANCE)
    with chat_errors():
        result = _knowledge_preview(service, principal.identity, identifier,
                                    body.query, body.scopes, now)
        return {"digest": result["digest"], "items": result["preview"],
                "trace": result["trace"],
                "cloud_preview_only": True,
                "note": "This exact preview is revalidated before Send; no provider was called."}


@router.post("/{identifier}/route-suggestions")
def route_suggestions(identifier: str, request: Request, body: RouteSuggestionRequest,
                      principal=Depends(require_permission("chat:send")),
                      service=Depends(get_application_service)):
    """Return local-only complexity hints and currently observed alternatives."""
    if contains_gemini_key(body.text):
        raise HTTPException(422, SECRET_PASTE_GUIDANCE)
    with chat_errors():
        current = service.owned_chat().get(principal.identity, identifier)
    coordinator = current["coordinator"]
    if current.get("local_model") is not True:
        return {"complexity": "unknown",
                "reason": "Route suggestions require a configured local coordinator; the current route is unchanged.",
                "suggested": None, "candidates": [],
                "default": {"provider_id": coordinator.provider, "model_id": coordinator.model,
                            "destination": "configured coordinator"}}
    inventory = service.local_model_inventory(coordinator.provider)
    local_models = inventory.models if inventory.state == "available" and inventory.supported else ()
    suggestion = suggest_route(body.text, coordinator.model, tuple(local_models))
    candidates = []
    if suggestion.complexity == "complex":
        from app.application.services.chat_route_suggestions import model_parameter_size
        for model in local_models:
            size, current_size = model_parameter_size(model), model_parameter_size(coordinator.model)
            if model != coordinator.model and current_size is not None and size is not None and size > current_size:
                candidates.append({"provider_id": coordinator.provider, "model_id": model,
                                   "destination": "local Ollama service", "kind": "local"})
        connections = getattr(request.app.state, "provider_connections_service", None)
        if connections is not None:
            try:
                for item in connections.list():
                    if item["provider_type"] != "gemini" or item["state"] != "available":
                        continue
                    for model in item["models"]:
                        candidates.append({"provider_id": item["provider_id"], "model_id": model,
                                           "destination": "Google Gemini online service", "kind": "cloud"})
            except (KeyError, TypeError, ValueError):
                pass
    candidates = candidates[:20]
    suggested = next((item for item in candidates if item["kind"] == "local"), None)
    if suggested is None:
        suggested = next((item for item in candidates if item["kind"] == "cloud"), None)
    return {"complexity": suggestion.complexity, "reason": suggestion.reason,
            "suggested": suggested, "candidates": candidates,
            "default": {"provider_id": coordinator.provider, "model_id": coordinator.model,
                        "destination": "configured coordinator"}}


def _validate_turn_route(request, service, current, body):
    if body.route_provider_id is None and body.route_model_id is None:
        if body.route_consent:
            raise HTTPException(422, "Route consent requires an alternate provider and model.")
        return None
    if not body.route_provider_id or not body.route_model_id:
        raise HTTPException(422, "Both alternate provider and model are required.")
    if body.route_consent is not True:
        raise HTTPException(403, "Explicit per-turn consent is required before using an alternate model.")
    coordinator = current["coordinator"]
    if current.get("local_model") is not True:
        raise HTTPException(422, "Alternate suggestions require the configured local coordinator to remain the default.")
    route_classification = suggest_route(body.text, coordinator.model, ()).complexity
    if route_classification != "complex":
        raise HTTPException(422, "Only a prompt with a complex cue may use an alternate route; keep the configured model for simple or uncertain prompts.")
    if (body.route_provider_id, body.route_model_id) == (coordinator.provider, coordinator.model):
        raise HTTPException(422, "Choose an alternate model; the configured model is already the default.")
    if not service.provider_exists(body.route_provider_id):
        raise HTTPException(503, "Selected provider is unavailable; the configured route was not changed.")
    if service.provider_requires_explicit_cloud_consent(body.route_provider_id):
        if body.cloud_consent is not True:
            raise HTTPException(403, "Separate per-turn cloud consent is required for this Gemini transfer.")
        connections = getattr(request.app.state, "provider_connections_service", None)
        try:
            item = next((entry for entry in connections.list()
                         if entry["provider_id"] == body.route_provider_id), None) if connections else None
        except (KeyError, TypeError, ValueError):
            item = None
        if item is None or item.get("provider_type") != "gemini" or item.get("state") != "available" \
                or body.route_model_id not in item.get("models", []):
            raise HTTPException(503, "Selected Gemini model is unavailable; no alternate route was used.")
    else:
        if not service.provider_is_local(body.route_provider_id):
            raise HTTPException(422, "Alternate routes are limited to installed local models or consented Gemini.")
        inventory = service.local_model_inventory(body.route_provider_id)
        if not inventory.supported or inventory.state != "available" or body.route_model_id not in inventory.models:
            raise HTTPException(503, "Selected local model is unavailable; no alternate route was used.")
        from app.application.services.chat_route_suggestions import model_parameter_size
        current_size = model_parameter_size(coordinator.model)
        alternate_size = model_parameter_size(body.route_model_id)
        if current_size is None or alternate_size is None or alternate_size <= current_size:
            raise HTTPException(422, "Only an explicitly sized larger local model may be selected; the configured route remains unchanged.")
    return body.route_provider_id, body.route_model_id


class TaskProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_message_id: str = Field(min_length=1, max_length=256)
    objective: str = Field(min_length=1, max_length=1024)
    project_id: str = Field(min_length=1, max_length=256)
    agent_id: str = Field(min_length=1, max_length=256)
    expected_outcome: str = Field(min_length=1, max_length=1024)
    verification_method: str = Field(min_length=1, max_length=1024)
    expected_evidence: str = Field(min_length=1, max_length=1024)
    context_query: str | None = Field(default=None, max_length=1024)
    context_scope: MemoryScope | None = None
    context_scope_id: str | None = Field(default=None, max_length=256)


class TaskProposalConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_digest: str = Field(min_length=64, max_length=64)
    confirmed: StrictBool


class RepositoryStudyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objective: str = Field(min_length=1, max_length=1024)
    owner: str = Field(min_length=1, max_length=100)
    repository: str = Field(min_length=1, max_length=100)

    @field_validator("objective")
    @classmethod
    def objective_must_fit_utf8_limit(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Study objective is required")
        try:
            encoded = value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError("Study objective must be valid UTF-8 text") from error
        if len(encoded) > RepositoryStudyService.MAX_OBJECTIVE_BYTES:
            raise ValueError("Study objective exceeds the UTF-8 byte limit")
        return value


async def bounded_body(request: Request):
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > 65536:
            raise HTTPException(413, "Chat request too large")
        payload.extend(chunk)
    return bytes(payload)


async def bounded_image_body(request: Request):
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > 3_000_000:
            raise HTTPException(413, "Image request exceeds the byte limit")
        payload.extend(chunk)
    return bytes(payload)


def parse(model, payload):
    try:
        return model.model_validate_json(payload)
    except ValueError:
        raise HTTPException(422, "Invalid chat request fields") from None


def decode_image_data(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, "Image data must be valid base64") from None


def get_repository_study_service(request: Request) -> RepositoryStudyService:
    return request.app.state.repository_study_service


@contextmanager
def chat_errors():
    try:
        yield
    except ChatTaskProposalNotFound:
        raise HTTPException(404, "Task proposal not found") from None
    except ChatTaskProposalExpired as error:
        raise HTTPException(410, str(error)) from None
    except ChatTaskProposalConflict as error:
        raise HTTPException(409, str(error)) from None
    except KnowledgeNotFound:
        raise HTTPException(404, "Retained knowledge not found") from None
    except PermissionError:
        raise HTTPException(403, "Context scope is not authorized for this conversation") from None
    except ChatNotFound:
        raise HTTPException(404, "Conversation not found") from None
    except ChatConsentRequired as error:
        raise HTTPException(403, str(error)) from None
    except ChatConflict as error:
        raise HTTPException(409, str(error)) from None
    except ChatLimit as error:
        raise HTTPException(429, str(error)) from None
    except ChatUnavailable as error:
        raise HTTPException(503, str(error)) from None
    except ProviderCapacityUnknown as error:
        raise HTTPException(503, str(error)) from None
    except ProviderCapacityError as error:
        raise HTTPException(429, str(error)) from None
    except ValueError:
        raise HTTPException(422, "Chat input or conversation state is invalid") from None
    except ChatHistoryError as error:
        raise HTTPException(503, str(error)) from None
    except RuntimeError:
        raise HTTPException(502, "Chat response failed; check the configured provider and model. No automatic retry occurred.") from None


@router.get("")
def list_conversations(principal=Depends(require_permission("chat:read")),
                       service=Depends(get_application_service)):
    with chat_errors():
        return {"items": service.owned_chat().list(principal.identity)}


@router.post("")
def start_conversation(payload=Depends(bounded_body),
                       principal=Depends(require_permission("chat:start")),
                       service=Depends(get_application_service)):
    body = parse(StartRequest, payload)
    with chat_errors():
        return service.owned_chat().start(principal.identity, body.agent_id)


@router.get("/task-proposals")
def list_task_proposals(principal=Depends(require_permission("chat:read")),
                        service=Depends(get_application_service)):
    with chat_errors():
        return {"items": service.chat_task_proposals().list_history(principal.identity)}


@router.get("/{identifier}")
def get_conversation(identifier: str, principal=Depends(require_permission("chat:read")),
                     service=Depends(get_application_service), now=Depends(get_chat_now)):
    with chat_errors():
        record = service.owned_chat().get(principal.identity, identifier)
        return {**record, "context_traces": service.chat_knowledge().traces(principal.identity, identifier, now)}


@router.get("/{identifier}/images")
def list_images(identifier: str,
                principal=Depends(require_permission("chat:read")),
                service=Depends(get_application_service)):
    with chat_errors():
        capability = service.owned_chat().image_capability(principal.identity, identifier)
        return {
            "items": [item.snapshot() for item in
                      service.owned_chat().list_images(principal.identity, identifier)],
            "destination": capability,
            "provider_transfer_supported": capability["state"] == "supported",
        }


@router.get("/{identifier}/images/{image_id}/preview")
def preview_image(identifier: str, image_id: str,
                  principal=Depends(require_permission("chat:read")),
                  service=Depends(get_application_service)):
    with chat_errors():
        image = service.owned_chat().selected_images_for_ocr(
            principal.identity, identifier, (image_id,)
        )[0]
        return Response(
            content=image._data,
            media_type=image.media_type,
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )


@router.post("/{identifier}/images")
def attach_image(identifier: str, payload=Depends(bounded_image_body),
                 principal=Depends(require_permission("chat:send")),
                 service=Depends(get_application_service)):
    body = parse(ImageUploadRequest, payload)
    data = decode_image_data(body.data_base64)
    with chat_errors():
        item = service.owned_chat().attach_image(
            principal.identity, identifier, data, body.media_type
        )
        capability = service.owned_chat().image_capability(principal.identity, identifier)
        return {
            "image": item.snapshot(),
            "destination": capability,
            "provider_transfer_supported": capability["state"] == "supported",
            "message": "Image is attached temporarily; it is sent only when selected and explicitly consented for one chat turn.",
        }


@router.post("/{identifier}/screen-captures")
def attach_screen_capture(identifier: str, payload=Depends(bounded_image_body),
                          principal=Depends(require_permission("chat:send")),
                          _capture_permission=Depends(require_permission("screen:capture")),
                          service=Depends(get_application_service)):
    body = parse(ScreenCaptureUploadRequest, payload)
    data = decode_image_data(body.data_base64)
    with chat_errors():
        item = service.owned_chat().attach_image(
            principal.identity, identifier, data, body.media_type,
            source="screen_capture", display_surface=body.display_surface,
            captured_at=body.captured_at,
        )
        return {
            "image": item.snapshot(),
            "provider_transfer_supported": service.owned_chat().get(principal.identity, identifier).get("image_input_supported", False),
            "message": "One screen frame is attached temporarily; it is sent only when selected and explicitly consented for one chat turn.",
        }


@router.post("/{identifier}/camera-captures")
def attach_camera_capture(identifier: str, payload=Depends(bounded_image_body),
                          principal=Depends(require_permission("chat:send")),
                          _capture_permission=Depends(require_permission("camera:capture")),
                          service=Depends(get_application_service)):
    body = parse(CameraCaptureUploadRequest, payload)
    data = decode_image_data(body.data_base64)
    with chat_errors():
        item = service.owned_chat().attach_image(
            principal.identity, identifier, data, body.media_type,
            source="camera_capture", captured_at=body.captured_at,
        )
        return {
            "image": item.snapshot(),
            "provider_transfer_supported": service.owned_chat().get(principal.identity, identifier).get("image_input_supported", False),
            "message": "One camera frame is attached temporarily; it is sent only when selected and explicitly consented for one chat turn.",
        }


@router.delete("/{identifier}/images/{image_id}")
def remove_image(identifier: str, image_id: str,
                 principal=Depends(require_permission("chat:send")),
                 service=Depends(get_application_service)):
    with chat_errors():
        removed = service.owned_chat().remove_image(principal.identity, identifier, image_id)
        if not removed:
            raise HTTPException(404, "Image attachment not found")
        return {"removed": True}


@router.post("/{identifier}/messages")
def send_message(identifier: str, request: Request, payload=Depends(bounded_body),
                 principal=Depends(require_permission("chat:send")),
                 service=Depends(get_application_service), now=Depends(get_chat_now)):
    body = parse(SendRequest, payload)
    if contains_gemini_key(body.text) or (body.context and contains_gemini_key(body.context.query)):
        raise HTTPException(422, SECRET_PASTE_GUIDANCE)
    if body.knowledge_enabled and (body.context is not None or body.image_ids):
        raise HTTPException(422, "Knowledge-assisted turns cannot combine with separate context or images.")
    if body.knowledge_enabled and (not body.knowledge_scopes or not body.knowledge_preview_digest):
        raise HTTPException(422, "Preview the selected knowledge scopes before sending.")
    if not body.knowledge_enabled and (body.knowledge_scopes or body.knowledge_preview_digest):
        raise HTTPException(422, "Knowledge scope and preview are required only when Use my knowledge is on.")
    if body.capture_local_prompt and (body.image_ids or body.context):
        raise HTTPException(422, "Exact prompt capture is unavailable for image or separate-context turns.")
    if body.reviewed_tools and body.image_ids:
        raise HTTPException(422, "Reviewed tools cannot be combined with image turns.")
    with chat_errors():
        started_at = time.perf_counter()
        presentation = _presentation_preferences(request, principal.identity)
        current = service.owned_chat().get(principal.identity, identifier)
        turn_route = _validate_turn_route(request, service, current, body)
        if turn_route and body.image_ids:
            raise HTTPException(422, "Temporary images use the configured provider route; alternate model routing is text-only.")
        if body.capture_local_prompt and not current.get("local_model"):
            raise HTTPException(422, "Exact prompt capture is available only for a configured local model.")
        if (body.capture_local_prompt and turn_route
                and service.provider_requires_explicit_cloud_consent(turn_route[0])):
            raise HTTPException(422, "Exact prompt capture is unavailable for an online alternate route.")
        route_provider_id = turn_route[0] if turn_route else current["coordinator"].provider
        cloud_requires_consent = service.provider_requires_explicit_cloud_consent(
            route_provider_id)
        if cloud_requires_consent and body.cloud_consent is not True:
            raise HTTPException(403, "Explicit consent is required before sending this turn, recent chat context, and any selected tool results to Gemini.")
        tool_trace, tool_context = [], None
        if body.reviewed_tools:
            if any(item.kind == "local-document-lookup" for item in body.reviewed_tools):
                authorizer = getattr(request.app.state, "capability_authorization_service",
                                     DEFAULT_CAPABILITY_AUTHORIZATION)
                try:
                    authorizer.require(identity=principal.identity, permissions=principal.permissions,
                                       capability_id="documentation:read", scope_type="principal",
                                       scope_id=principal.identity, session_grants=principal.session_grants)
                except CapabilityAuthorizationDenied:
                    audit = getattr(request.app.state, "capability_audit_service", None)
                    if audit is not None:
                        try:
                            audit.record(actor_id=principal.identity, capability_id="documentation:read",
                                         permission_decision="deny", action_state="authorization",
                                         result_state="denied", safe_reference="chat-local-document-lookup")
                        except (RuntimeError, OSError, ValueError):
                            raise HTTPException(503, "Capability audit unavailable") from None
                    raise HTTPException(403, "This session cannot read the selected local documentation.") from None
                audit = getattr(request.app.state, "capability_audit_service", None)
                if audit is not None:
                    try:
                        audit.record(actor_id=principal.identity, capability_id="documentation:read",
                                     permission_decision="allow", action_state="authorization",
                                     result_state="allowed", safe_reference="chat-local-document-lookup")
                    except (RuntimeError, OSError, ValueError):
                        raise HTTPException(503, "Capability audit unavailable") from None
        knowledge = service.chat_knowledge()
        retrieval_started_at = time.perf_counter()
        auto_context = None
        if body.knowledge_enabled:
            auto_context = _knowledge_preview(service, principal.identity, identifier,
                                               body.text, body.knowledge_scopes, now)
            if auto_context["digest"] != body.knowledge_preview_digest:
                raise HTTPException(409, "Selected knowledge changed after preview. Preview it again before sending.")
        retrieved = trace_request = None
        if body.context is not None:
            retrieved, trace_request = knowledge.retrieve(principal.identity, identifier, ContextRequest(
                body.context.query, body.context.scope, body.context.scope_id, body.context.limit), now)
        retrieval_ms = max(0, int((time.perf_counter() - retrieval_started_at) * 1000))
        tool_trace, tool_context = run_reviewed_tools(
            body.reviewed_tools, getattr(request.app.state, "documentation_service", None))
        if body.image_ids:
            if body.image_consent is not True:
                raise HTTPException(403, "Explicit per-turn consent is required before selected images are sent to the configured provider.")
            if body.context is not None:
                raise HTTPException(422, "Image turns cannot include separately retrieved context.")
            owned = service.owned_chat()
            capability = owned.image_capability(principal.identity, identifier)
            if capability["state"] != "supported":
                detail = ("The selected provider/model does not report vision support. No image was sent."
                          if capability["state"] == "unsupported" else
                          "Vision support for the selected provider/model could not be verified. No image was sent.")
                raise HTTPException(409, detail)
            images = owned.selected_images_for_ocr(principal.identity, identifier, tuple(body.image_ids))
            ocr_evidence = ()
            if body.include_local_ocr:
                ocr = service.ocr()
                ocr_evidence = tuple(ocr.recognize(image, language="eng") for image in images)
            answer_started_at = time.perf_counter()
            try:
                result = owned.send(principal.identity, identifier, body.text, presentation_preferences=presentation,
                                    image_ids=tuple(body.image_ids),
                                    image_consent=True, ocr_evidence=ocr_evidence)
            except Exception:
                image_provider, image_model = turn_route or (
                    current["coordinator"].provider, current["coordinator"].model
                )
                remaining = {item.id for item in owned.list_images(principal.identity, identifier)}
                image_retention = ("still_temporary_until_expiry_or_removal"
                                   if any(item in remaining for item in body.image_ids)
                                   else "discarded_after_one_use")
                _record_unverified_turn(
                    service, knowledge, principal.identity, identifier,
                    current["coordinator"],
                    image_provider if service.provider_requires_explicit_cloud_consent(image_provider) else None,
                    body.cloud_consent, (time.perf_counter() - started_at) * 1000,
                    None, None, None, now, retrieval_ms=retrieval_ms,
                    answer_ms=(time.perf_counter() - answer_started_at) * 1000,
                    vision={"used": True, "provider": image_provider, "model": image_model,
                            "destination": "local" if service.provider_is_local(image_provider) else "online",
                            "outcome": "failed", "image_count": len(body.image_ids),
                            "retention": image_retention})
                raise
            messages = result["conversation"].messages
            reply = next((message for message in reversed(messages)
                          if message.role.value == "assistant" and message.status.value == "completed"), None)
            if reply is not None:
                result = {**result, "context_trace": knowledge.record_turn_trace(
                    principal.identity, identifier, reply.id, coordinator=current["coordinator"],
                    cloud_provider=current["coordinator"].provider if cloud_requires_consent else None,
                    cloud_consent=body.cloud_consent,
                    elapsed_ms=(time.perf_counter() - started_at) * 1000,
                    retrieval=None,
                    steps=_workflow_steps(None, [], current["coordinator"], retrieval_ms=retrieval_ms,
                                          answer_ms=(time.perf_counter() - answer_started_at) * 1000),
                    vision={
                        "used": True,
                        "provider": result["image_transfer"]["provider_id"],
                        "model": result["image_transfer"]["model_id"],
                        "destination": "local" if result["image_transfer"]["local"] else "online",
                        "outcome": result["image_transfer"]["outcome"],
                        "image_count": len(result["image_transfer"]["image_ids"]),
                        "retention": result["image_transfer"]["retention"],
                    },
                    now=now)}
        else:
            if body.image_consent or body.include_local_ocr:
                raise HTTPException(422, "Image consent and OCR require selected images.")
            prompt_context = auto_context["prompt_context"] if auto_context else (
                knowledge.prompt_context(retrieved) if retrieved else None)
            captured_prompt = []
            cloud_provider = route_provider_id if cloud_requires_consent else None
            answer_started_at = time.perf_counter()
            try:
                result = service.owned_chat().send(
                    principal.identity, identifier, body.text, prompt_context,
                    presentation_preferences=presentation,
                    tool_context=tool_context,
                    prompt_observer=captured_prompt.append if body.capture_local_prompt else None,
                    turn_route=turn_route, route_consent=body.route_consent)
            except Exception:
                _record_unverified_turn(
                    service, knowledge, principal.identity, identifier, current["coordinator"],
                    cloud_provider, body.cloud_consent, (time.perf_counter() - started_at) * 1000,
                    auto_context, retrieved, trace_request, now, tool_trace, retrieval_ms,
                    (time.perf_counter() - answer_started_at) * 1000, turn_route=turn_route)
                raise
            messages = result["conversation"].messages
            reply = next((message for message in reversed(messages)
                          if message.role.value == "assistant" and message.status.value == "completed"), None)
            if reply is not None:
                retrieval_trace = ({"enabled": True, **auto_context["trace"]} if auto_context else
                                   knowledge.record_trace(principal.identity, identifier, reply.id,
                                                          retrieved, trace_request, now) if retrieved is not None else None)
                coordinator = current["coordinator"]
                trace = knowledge.record_turn_trace(
                    principal.identity, identifier, reply.id, coordinator=coordinator,
                    cloud_provider=cloud_provider, cloud_consent=body.cloud_consent,
                    elapsed_ms=(time.perf_counter() - started_at) * 1000,
                    retrieval=retrieval_trace, tools=tool_trace,
                    steps=_workflow_steps(retrieval_trace, tool_trace, coordinator,
                                          retrieval_ms=retrieval_ms,
                                          answer_ms=(time.perf_counter() - answer_started_at) * 1000,
                                          turn_route=turn_route),
                    turn_route=turn_route,
                    now=now)
                result = {**result, "context_trace": trace}
            if captured_prompt:
                result["advanced_prompt"] = captured_prompt[0]
        return result


@router.post("/{identifier}/messages/stream")
def stream_message(identifier: str, request: Request, payload=Depends(bounded_body),
                   principal=Depends(require_permission("chat:send")),
                   service=Depends(get_application_service), now=Depends(get_chat_now)):
    body = parse(SendRequest, payload)
    if body.route_provider_id is not None or body.route_model_id is not None or body.route_consent:
        raise HTTPException(422, "Per-turn alternate model routing uses the reviewed non-streaming endpoint.")
    if body.reviewed_tools:
        raise HTTPException(422, "Reviewed tools use the bounded non-streaming message endpoint.")
    if body.image_ids or body.image_consent or body.include_local_ocr:
        raise HTTPException(422, "Image turns use the bounded non-streaming message endpoint.")
    if contains_gemini_key(body.text) or (body.context and contains_gemini_key(body.context.query)):
        raise HTTPException(422, SECRET_PASTE_GUIDANCE)
    if body.knowledge_enabled and body.context is not None:
        raise HTTPException(422, "Knowledge-assisted turns cannot combine with separate context.")
    if body.knowledge_enabled and (not body.knowledge_scopes or not body.knowledge_preview_digest):
        raise HTTPException(422, "Preview the selected knowledge scopes before sending.")
    if not body.knowledge_enabled and (body.knowledge_scopes or body.knowledge_preview_digest):
        raise HTTPException(422, "Knowledge scope and preview are required only when Use my knowledge is on.")
    if body.capture_local_prompt:
        raise HTTPException(422, "Exact prompt capture uses the one-turn response view; send without streaming.")
    with chat_errors():
        started_at = time.perf_counter()
        presentation = _presentation_preferences(request, principal.identity)
        owned = service.owned_chat()
        current = owned.get(principal.identity, identifier)
        if not current.get("streaming_supported"):
            raise HTTPException(409, "The selected provider does not support response streaming.")
        cloud_requires_consent = service.provider_requires_explicit_cloud_consent(
            current["coordinator"].provider)
        if cloud_requires_consent and body.cloud_consent is not True:
            raise HTTPException(
                403,
                "Explicit consent is required before sending this turn and recent chat context to Gemini.",
            )
        knowledge = service.chat_knowledge()
        retrieval_started_at = time.perf_counter()
        auto_context = None
        if body.knowledge_enabled:
            auto_context = _knowledge_preview(service, principal.identity, identifier,
                                               body.text, body.knowledge_scopes, now)
            if auto_context["digest"] != body.knowledge_preview_digest:
                raise HTTPException(409, "Selected knowledge changed after preview. Preview it again before sending.")
        retrieved = trace_request = None
        if body.context is not None:
            retrieved, trace_request = knowledge.retrieve(
                principal.identity,
                identifier,
                ContextRequest(
                    body.context.query,
                    body.context.scope,
                    body.context.scope_id,
                    body.context.limit,
                ),
                now,
            )
        retrieval_ms = max(0, int((time.perf_counter() - retrieval_started_at) * 1000))

    def events():
        try:
            answer_started_at = time.perf_counter()
            for event in owned.stream(
                principal.identity,
                identifier,
                body.text,
                auto_context["prompt_context"] if auto_context else knowledge.prompt_context(retrieved) if retrieved else None,
                presentation,
            ):
                if event["type"] == "complete":
                    completed = event["conversation"]
                    reply = completed.messages[-1]
                    retrieval_trace = ({"enabled": True, **auto_context["trace"]} if auto_context else
                                       knowledge.record_trace(principal.identity, identifier, reply.id,
                                                              retrieved, trace_request, now) if retrieved is not None else None)
                    coordinator = event["coordinator"]
                    cloud_provider = coordinator.provider if cloud_requires_consent else None
                    turn_trace = knowledge.record_turn_trace(
                        principal.identity, identifier, reply.id, coordinator=coordinator,
                        cloud_provider=cloud_provider, cloud_consent=body.cloud_consent,
                        elapsed_ms=(time.perf_counter() - started_at) * 1000,
                        retrieval=retrieval_trace,
                        steps=_workflow_steps(retrieval_trace, [], coordinator,
                                              retrieval_ms=retrieval_ms,
                                              answer_ms=(time.perf_counter() - answer_started_at) * 1000),
                        now=now)
                    event = {
                        **event,
                        "context_trace": turn_trace,
                    }
                yield json.dumps(
                    jsonable_encoder(event), ensure_ascii=True, separators=(",", ":")
                ) + "\n"
        except ProviderCapacityError:
            _record_unverified_turn(
                service, knowledge, principal.identity, identifier, current["coordinator"],
                current["coordinator"].provider if cloud_requires_consent else None,
                body.cloud_consent, (time.perf_counter() - started_at) * 1000,
                auto_context, retrieved, trace_request, now, retrieval_ms=retrieval_ms,
                answer_ms=(time.perf_counter() - answer_started_at) * 1000)
            yield json.dumps({
                "type": "error",
                "message": "Configured provider request-slot capacity is exhausted; no provider request was admitted.",
            }) + "\n"
        except Exception:
            _record_unverified_turn(
                service, knowledge, principal.identity, identifier, current["coordinator"],
                current["coordinator"].provider if cloud_requires_consent else None,
                body.cloud_consent, (time.perf_counter() - started_at) * 1000,
                auto_context, retrieved, trace_request, now, retrieval_ms=retrieval_ms,
                answer_ms=(time.perf_counter() - answer_started_at) * 1000)
            yield json.dumps({
                "type": "error",
                "message": (
                    "The stream ended before a verified final response. The turn may have reached "
                    "the provider; inspect its pending status and do not resend it."
                ),
            }) + "\n"

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post(
    "/{identifier}/repository-studies",
    dependencies=[Depends(require_permission("github:read"))],
)
def study_repository(
    identifier: str,
    payload=Depends(bounded_body),
    principal=Depends(require_permission("chat:send")),
    service=Depends(get_application_service),
    study_service=Depends(get_repository_study_service),
):
    body = parse(RepositoryStudyRequest, payload)
    with chat_errors():
        conversation_status = service.owned_chat().get_status(
            principal.identity, identifier
        )
    if conversation_status is not ConversationStatus.OPEN:
        raise HTTPException(409, "Repository studies require an open owned conversation")
    try:
        report = study_service.study(body.objective, body.owner, body.repository)
    except GitHubInspectionRequestError:
        raise HTTPException(422, "GitHub repository identifier is invalid") from None
    except (GitHubRepositoryScopeDenied, GitHubRepositoryNotFound):
        raise HTTPException(
            404, "GitHub repository was not found or is not in scope"
        ) from None
    except (GitHubInspectionRateLimited, GitHubRateLimitError):
        raise HTTPException(429, "GitHub API rate limit exceeded") from None
    except GitHubInspectionUnavailable:
        raise HTTPException(503, "GitHub repository inspection is unavailable") from None
    except (SourceAnalysisError, ProposalGenerationError):
        raise HTTPException(503, "Repository study could not be completed") from None

    analysis = report.analysis
    discovery = report.discovery
    project_purpose = analysis.project_purpose
    response = {
        "objective": report.objective,
        "decision": report.decision.value,
        "studied_at": report.studied_at,
        "repository": {
            "owner": discovery.owner,
            "name": discovery.repository_name,
            "url": discovery.repository_url,
            "discovered_at": discovery.discovered_at,
            "description": discovery.description,
            "default_branch": discovery.default_branch,
            "license": {
                "name": discovery.license_name,
                "spdx_id": discovery.license_spdx_id,
            },
            "last_pushed_at": discovery.pushed_at,
            "revision_sha": analysis.revision_sha,
            "revision_url": (
                f"{discovery.repository_url}/tree/{analysis.revision_sha}"
                if analysis.revision_sha is not None
                else None
            ),
        },
        "analysis": {
            "complete": analysis.is_complete,
            "languages": list(analysis.detected_languages),
            "top_level_directories": list(analysis.top_level_directories),
            "dependency_manifests": list(analysis.dependency_manifests),
            "documentation_files": list(analysis.documentation_files),
            "test_paths": list(analysis.test_paths),
            "project_purpose": (
                None
                if project_purpose is None
                else {
                    "statement": project_purpose.statement,
                    "evidence_paths": list(project_purpose.evidence_paths),
                }
            ),
            "potential_capabilities": [
                {
                    "statement": observation.statement,
                    "evidence_paths": list(observation.evidence_paths),
                }
                for observation in analysis.potential_capabilities
            ],
            "notes": list(analysis.analysis_notes),
            "source_bytes_inspected": analysis.source_bytes_inspected,
        },
        "findings": jsonable_encoder(report.evaluation.findings),
        "strengths": list(report.evaluation.key_strengths),
        "concerns": list(report.evaluation.key_concerns),
        "unknowns": list(report.evaluation.unknowns),
        "integration_requirements": list(report.evaluation.integration_requirements),
        "proposal": {
            "id": report.proposal.id,
            "status": report.proposal.status.value,
            "requested_purpose": report.proposal.requested_purpose,
            "proposed_approach": report.proposal.proposed_approach,
            "risk_information": report.proposal.risk_information,
            "intended_capabilities": list(report.proposal.intended_capabilities),
            "key_strengths": list(report.proposal.key_strengths),
            "key_concerns": list(report.proposal.key_concerns),
            "unknowns": list(report.proposal.unknowns),
            "integration_requirements": list(
                report.proposal.integration_requirements
            ),
            "evidence_references": list(report.proposal.evidence_references),
        },
        "citations": jsonable_encoder(report.citations),
        "limitations": list(report.limitations),
    }
    if len(json.dumps(jsonable_encoder(response), ensure_ascii=True).encode("utf-8")) > 131072:
        raise HTTPException(502, "Repository study report exceeded its response limit")
    return response


@router.get("/{identifier}/retained")
def list_retained(identifier: str, principal=Depends(require_permission("chat:read")),
                  service=Depends(get_application_service), now=Depends(get_chat_now)):
    with chat_errors():
        return service.chat_knowledge().list_retained(principal.identity, identifier, now)


@router.post("/{identifier}/retained")
def retain_message(identifier: str, payload=Depends(bounded_body),
                   principal=Depends(require_permission("chat-knowledge:retain")),
                   service=Depends(get_application_service), now=Depends(get_chat_now)):
    body = parse(RetainRequest, payload)
    with chat_errors():
        return service.chat_knowledge().retain(
            principal.identity, identifier, body.message_id, expires_at=body.expires_at,
            retention_opt_in=body.retention_opt_in, now=now)


@router.delete("/{identifier}/retained/{memory_id}")
def withdraw_retained(identifier: str, memory_id: str,
                      principal=Depends(require_permission("chat-knowledge:withdraw")),
                      service=Depends(get_application_service)):
    with chat_errors():
        return service.chat_knowledge().withdraw(principal.identity, identifier, memory_id)


@router.post("/{identifier}/close")
def close_conversation(identifier: str, principal=Depends(require_permission("chat:close")),
                       service=Depends(get_application_service)):
    with chat_errors():
        return service.owned_chat().close(principal.identity, identifier)


@router.post("/{identifier}/task-proposals")
def create_task_proposal(
    identifier: str,
    payload=Depends(bounded_body),
    principal=Depends(require_permission("chat-task:create")),
    service=Depends(get_application_service),
):
    body = parse(TaskProposalRequest, payload)
    with chat_errors():
        return service.chat_task_proposals().create(
            principal.identity,
            identifier,
            source_message_id=body.source_message_id,
            objective=body.objective,
            project_id=body.project_id,
            agent_id=body.agent_id,
            expected_outcome=body.expected_outcome,
            verification_method=body.verification_method,
            expected_evidence=body.expected_evidence,
            context_query=body.context_query,
            context_scope=body.context_scope,
            context_scope_id=body.context_scope_id,
        )


@router.post("/{identifier}/task-proposals/{proposal_id}/confirm")
def confirm_task_proposal(
    identifier: str,
    proposal_id: str,
    payload=Depends(bounded_body),
    principal=Depends(require_permission("chat-task:create")),
    service=Depends(get_application_service),
):
    body = parse(TaskProposalConfirmation, payload)
    with chat_errors():
        return service.chat_task_proposals().confirm(
            principal.identity,
            identifier,
            proposal_id,
            proposal_digest=body.proposal_digest,
            confirmed=body.confirmed,
        )
