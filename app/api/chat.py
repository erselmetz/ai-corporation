"""Authorized owned chat; routes depend only on application services."""
import re
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.application.services.owned_chat import ChatConflict, ChatLimit, ChatNotFound, ChatUnavailable
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


def get_application_service(request: Request):
    return request.app.state.application_service


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: str = Field(min_length=1, max_length=256)


class SendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=8192)
    cloud_consent: bool = False


async def bounded_body(request: Request):
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > 65536:
            raise HTTPException(413, "Chat request too large")
        payload.extend(chunk)
    return bytes(payload)


def parse(model, payload):
    try:
        return model.model_validate_json(payload)
    except ValueError:
        raise HTTPException(422, "Invalid chat request fields") from None


@contextmanager
def chat_errors():
    try:
        yield
    except ChatNotFound:
        raise HTTPException(404, "Conversation not found") from None
    except ChatConflict as error:
        raise HTTPException(409, str(error)) from None
    except ChatLimit as error:
        raise HTTPException(429, str(error)) from None
    except ChatUnavailable as error:
        raise HTTPException(503, str(error)) from None
    except ValueError:
        raise HTTPException(422, "Chat input or conversation state is invalid") from None
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


@router.get("/{identifier}")
def get_conversation(identifier: str, principal=Depends(require_permission("chat:read")),
                     service=Depends(get_application_service)):
    with chat_errors():
        return service.owned_chat().get(principal.identity, identifier)


@router.post("/{identifier}/messages")
def send_message(identifier: str, payload=Depends(bounded_body),
                 principal=Depends(require_permission("chat:send")),
                 service=Depends(get_application_service)):
    body = parse(SendRequest, payload)
    if contains_gemini_key(body.text):
        raise HTTPException(422, SECRET_PASTE_GUIDANCE)
    with chat_errors():
        current = service.owned_chat().get(principal.identity, identifier)
        if current["coordinator"].provider == "gemini" and body.cloud_consent is not True:
            raise HTTPException(403, "Explicit consent is required before sending this turn and recent chat context to Gemini.")
        return service.owned_chat().send(principal.identity, identifier, body.text)


@router.post("/{identifier}/close")
def close_conversation(identifier: str, principal=Depends(require_permission("chat:close")),
                       service=Depends(get_application_service)):
    with chat_errors():
        return service.owned_chat().close(principal.identity, identifier)
