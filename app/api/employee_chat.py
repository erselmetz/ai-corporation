"""Authorized principal-owned chats associated with registered Employees."""
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.application.services.owned_chat import (
    ChatConflict,
    ChatConsentRequired,
    ChatLimit,
    ChatNotFound,
    ChatUnavailable,
)
from .chat import bounded_body, contains_gemini_key, get_application_service
from .models import (
    EmployeeChatAgentResponse,
    EmployeeChatConversationResponse,
    EmployeeChatIdentityResponse,
    EmployeeChatListItemResponse,
    EmployeeChatListResponse,
    EmployeeChatMessageResponse,
    EmployeeChatResponse,
)
from .security import require_permission

router = APIRouter(prefix="/api/employee-chat/conversations")


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: str = Field(min_length=1, max_length=256)

    @field_validator("employee_id")
    @classmethod
    def require_non_blank_employee(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Employee ID cannot be blank")
        return value.strip()


class SendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=8192)
    cloud_consent: bool = False

    @field_validator("text")
    @classmethod
    def require_non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message text cannot be blank")
        return value


def _parse(model, payload: bytes):
    try:
        return model.model_validate_json(payload)
    except ValueError:
        raise HTTPException(422, "Invalid individual chat request fields") from None


@contextmanager
def _chat_errors():
    try:
        yield
    except ChatConsentRequired as error:
        raise HTTPException(403, str(error)) from None
    except ChatNotFound:
        raise HTTPException(404, "Conversation or Employee not found") from None
    except ChatConflict as error:
        raise HTTPException(409, str(error)) from None
    except ChatLimit as error:
        raise HTTPException(429, str(error)) from None
    except ChatUnavailable as error:
        raise HTTPException(503, str(error)) from None
    except ValueError:
        raise HTTPException(422, "Chat input or conversation state is invalid") from None
    except RuntimeError:
        raise HTTPException(
            502,
            "Individual chat response failed; check the assigned provider. No automatic retry occurred.",
        ) from None


def _snapshot_response(snapshot) -> EmployeeChatResponse:
    conversation = snapshot.conversation
    return EmployeeChatResponse(
        conversation=EmployeeChatConversationResponse(
            id=conversation.id,
            employee_id=snapshot.employee.id,
            agent_id=conversation.target.agent_id,
            status=conversation.status.value,
            messages=[
                EmployeeChatMessageResponse(
                    id=message.id,
                    role=message.role.value,
                    content=message.content,
                    status=message.status.value,
                )
                for message in conversation.messages
            ],
        ),
        employee=EmployeeChatIdentityResponse(
            id=snapshot.employee.id,
            name=snapshot.employee.name,
            role=snapshot.employee.role,
        ),
        agent=EmployeeChatAgentResponse(
            id=snapshot.agent.id,
            name=snapshot.agent.name,
            role=snapshot.agent.role,
            provider_id=snapshot.agent.provider_id,
            model_id=snapshot.agent.model_id,
        ),
    )


def _list_item_response(item) -> EmployeeChatListItemResponse:
    return EmployeeChatListItemResponse(
        conversation_id=item.conversation_id,
        employee=EmployeeChatIdentityResponse(
            id=item.employee.id,
            name=item.employee.name,
            role=item.employee.role,
        ),
        agent=EmployeeChatAgentResponse(
            id=item.agent.id,
            name=item.agent.name,
            role=item.agent.role,
            provider_id=item.agent.provider_id,
            model_id=item.agent.model_id,
        ),
        status=item.status.value,
    )


@router.get("", response_model=EmployeeChatListResponse)
def list_conversations(
    principal=Depends(require_permission("employee-chat:read")),
    service=Depends(get_application_service),
) -> EmployeeChatListResponse:
    with _chat_errors():
        return EmployeeChatListResponse(
            items=[
                _list_item_response(item)
                for item in service.owned_employee_chat().list(principal.identity)
            ]
        )


@router.post(
    "",
    response_model=EmployeeChatResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_conversation(
    payload=Depends(bounded_body),
    principal=Depends(require_permission("employee-chat:start")),
    service=Depends(get_application_service),
) -> EmployeeChatResponse:
    body = _parse(StartRequest, payload)
    with _chat_errors():
        return _snapshot_response(
            service.owned_employee_chat().start(
                principal.identity, body.employee_id
            )
        )


@router.get("/{identifier}", response_model=EmployeeChatResponse)
def get_conversation(
    identifier: str,
    principal=Depends(require_permission("employee-chat:read")),
    service=Depends(get_application_service),
) -> EmployeeChatResponse:
    with _chat_errors():
        return _snapshot_response(
            service.owned_employee_chat().get(principal.identity, identifier)
        )


@router.post("/{identifier}/messages", response_model=EmployeeChatResponse)
def send_message(
    identifier: str,
    payload=Depends(bounded_body),
    principal=Depends(require_permission("employee-chat:send")),
    service=Depends(get_application_service),
) -> EmployeeChatResponse:
    body = _parse(SendRequest, payload)
    if contains_gemini_key(body.text):
        raise HTTPException(
            422,
            "This message looks like it contains a Gemini API key. It was not saved or sent. "
            "Use the Gemini online setup page to connect a key.",
        )
    with _chat_errors():
        return _snapshot_response(
            service.owned_employee_chat().send(
                principal.identity,
                identifier,
                body.text,
                cloud_consent=body.cloud_consent,
            )
        )


@router.post("/{identifier}/close", response_model=EmployeeChatResponse)
def close_conversation(
    identifier: str,
    principal=Depends(require_permission("employee-chat:close")),
    service=Depends(get_application_service),
) -> EmployeeChatResponse:
    with _chat_errors():
        return _snapshot_response(
            service.owned_employee_chat().close(principal.identity, identifier)
        )
