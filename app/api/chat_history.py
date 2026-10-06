"""Opt-in durable chat history; owner-scoped, read-only after restart."""
from contextlib import contextmanager
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.application.services.chat_history import ChatHistoryError, HistoryNotFound
from app.application.services.owned_chat import ChatNotFound
from .security import require_permission

router = APIRouter(prefix="/api/chat/history")


class EnableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: str = Field(min_length=1, max_length=256)
    expires_at: datetime
    history_opt_in: StrictBool


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acknowledge_uncertain: StrictBool


def get_history_now():
    return datetime.now(timezone.utc)


def application(request: Request):
    return request.app.state.application_service


@contextmanager
def history_errors():
    try:
        yield
    except (HistoryNotFound, ChatNotFound):
        raise HTTPException(404, "Conversation history not found") from None
    except ChatHistoryError as error:
        raise HTTPException(503, str(error)) from None
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


@router.get("")
def list_history(principal=Depends(require_permission("chat:read")), service=Depends(application),
                 now=Depends(get_history_now)):
    with history_errors():
        return service.chat_history().list(principal.identity, now)


@router.post("")
def enable_history(body: EnableRequest, principal=Depends(require_permission("chat-history:manage")),
                   service=Depends(application), now=Depends(get_history_now)):
    with history_errors():
        live = service.owned_chat().get(principal.identity, body.conversation_id)
        record = live["conversation"]
        messages = [{"id": m.id, "role": m.role.value, "content": m.content, "status": m.status.value}
                    for m in record.messages]
        return service.chat_history().enable(
            principal.identity, body.conversation_id, record.coordinator_agent_id,
            record.status.value, messages, expires_at=body.expires_at, opt_in=body.history_opt_in, now=now)


@router.delete("")
def delete_all_history(principal=Depends(require_permission("chat-history:manage")),
                       service=Depends(application)):
    with history_errors():
        return service.chat_history().delete_all(principal.identity)


@router.get("/{identifier}")
def get_history(identifier: str, principal=Depends(require_permission("chat:read")),
                service=Depends(application), now=Depends(get_history_now)):
    with history_errors():
        return service.chat_history().get(principal.identity, identifier, now)


@router.post("/{identifier}/messages/{message_id}/review")
def review_message(identifier: str, message_id: str, body: ReviewRequest,
                   principal=Depends(require_permission("chat-history:manage")),
                   service=Depends(application), now=Depends(get_history_now)):
    if body.acknowledge_uncertain is not True:
        raise HTTPException(422, "Acknowledge that the turn's outcome is uncertain")
    with history_errors():
        return service.chat_history().review(principal.identity, identifier, message_id, now)


@router.delete("/{identifier}")
def delete_history(identifier: str, principal=Depends(require_permission("chat-history:manage")),
                   service=Depends(application)):
    with history_errors():
        return service.chat_history().delete(principal.identity, identifier)