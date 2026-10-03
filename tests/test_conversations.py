from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.application import CorporationApplicationService
from app.conversations import (
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
    MessageStatus,
)
from app.orchestrator import Orchestrator


def test_conversation_contains_ordered_messages_without_task_side_effects():
    conversation = Conversation("conversation-1")
    user_message = Message("message-1", MessageRole.USER, "Please explain this.")
    assistant_message = Message("message-2", MessageRole.ASSISTANT, "A response.")

    conversation.add_message(user_message)
    conversation.add_message(assistant_message)

    assert conversation.id == "conversation-1"
    assert conversation.status is ConversationStatus.OPEN
    assert conversation.messages == (user_message, assistant_message)
    assert conversation.get_message("message-1") is user_message
    assert user_message.status is MessageStatus.PENDING
    assert assistant_message.status is MessageStatus.PENDING
    assert not hasattr(conversation, "task_id")
    assert not hasattr(user_message, "task_id")


@pytest.mark.parametrize(
    ("conversation_id", "message_id", "role", "content"),
    [
        (" ", "message", MessageRole.USER, "content"),
        ("conversation", " ", MessageRole.USER, "content"),
        ("conversation", "message", "user", "content"),
        ("conversation", "message", MessageRole.USER, " "),
    ],
)
def test_conversation_and_message_required_fields_are_validated(
    conversation_id,
    message_id,
    role,
    content,
):
    if conversation_id.isspace():
        with pytest.raises(ValueError, match="Conversation id"):
            Conversation(conversation_id)
    else:
        with pytest.raises((ValueError, TypeError)):
            Message(message_id, role, content)


def test_message_lifecycle_allows_only_pending_to_a_terminal_state():
    message = Message("message-1", MessageRole.ASSISTANT, "Generated response")

    message.transition(MessageStatus.COMPLETED)

    assert message.status is MessageStatus.COMPLETED
    with pytest.raises(ValueError, match="Invalid message transition"):
        message.transition(MessageStatus.FAILED)
    with pytest.raises(AttributeError):
        message.status = MessageStatus.PENDING

    failed_message = Message("message-2", MessageRole.ASSISTANT, "Failed response")
    failed_message.transition(MessageStatus.FAILED)
    assert failed_message.status is MessageStatus.FAILED
    with pytest.raises(ValueError, match="Invalid message transition"):
        failed_message.transition(MessageStatus.COMPLETED)


def test_conversation_rejects_non_messages_and_duplicate_message_ids():
    conversation = Conversation("conversation-1")
    message = Message("message-1", MessageRole.USER, "Hello")
    conversation.add_message(message)

    with pytest.raises(TypeError, match="Only Message instances"):
        conversation.add_message("not a message")
    with pytest.raises(ValueError, match="already exists"):
        conversation.add_message(Message("message-1", MessageRole.USER, "Again"))


def test_conversation_closes_only_after_pending_messages_finish():
    conversation = Conversation("conversation-1")
    message = Message("message-1", MessageRole.USER, "Hello")
    conversation.add_message(message)

    with pytest.raises(ValueError, match="pending messages"):
        conversation.close()

    message.transition(MessageStatus.COMPLETED)
    conversation.close()
    assert conversation.status is ConversationStatus.CLOSED
    with pytest.raises(ValueError, match="closed conversation"):
        conversation.add_message(Message("message-2", MessageRole.USER, "Again"))
    with pytest.raises(ValueError, match="already closed"):
        conversation.close()


def test_message_lookup_reports_missing_message():
    conversation = Conversation("conversation-1")

    with pytest.raises(ValueError, match="Message not found"):
        conversation.get_message("missing")


def test_chat_page_does_not_bypass_default_authentication_or_execute_domain_work():
    orchestrator = MagicMock(spec=Orchestrator)
    application = create_app(CorporationApplicationService(orchestrator))

    with TestClient(application) as client:
        assert client.get("/api/conversations").status_code == 404
        assert client.get("/ui/chat").status_code == 200
        assert client.get("/api/chat/conversations").status_code == 401
        assert client.post("/api/chat/conversations", json={"agent_id": "agent"}).status_code == 401
        assert client.post("/api/chat/conversations/id/messages", json={"text": "Hello"}).status_code == 401

    assert orchestrator.method_calls == []
