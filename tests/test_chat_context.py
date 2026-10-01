from unittest.mock import MagicMock

import pytest

from app.agents import Agent, AgentRegistry, EmployeeRegistry
from app.conversations import EmployeeChatService, MessageRole, MessageStatus


@pytest.fixture
def chat():
    agents = AgentRegistry()
    agents.register(Agent("agent", "Agent", "Worker", "ollama", "model"))
    service = EmployeeChatService(EmployeeRegistry(), agents)
    service.start_conversation("one", agent_id="agent")
    service.start_conversation("two", agent_id="agent")
    return service


def test_replacement_isolation_and_snapshot_exclusion(chat):
    snapshot = chat.get_conversation("one")
    chat.set_context("one", "Relevant caller-authorized text")
    assert chat.get_context("one") == "Relevant caller-authorized text"
    assert chat.get_context("two") == ""
    assert chat.get_conversation("one") == snapshot
    chat.set_context("one", "Replacement")
    assert chat.get_context("one") == "Replacement"
    chat.set_context("one", "")
    assert chat.get_context("one") == ""


def test_utf8_boundary_and_atomic_rejection(chat):
    content = "\u00e9" * (chat.MAX_CONTEXT_BYTES // 2)
    chat.set_context("one", content)
    with pytest.raises(ValueError, match="byte limit"):
        chat.set_context("one", content + "a")
    assert chat.get_context("one") == content
    with pytest.raises(TypeError, match="text"):
        chat.set_context("one", {"secret": "value"})
    assert chat.get_context("one") == content


def test_retention_only_clears_after_successful_close(chat):
    chat.set_context("one", "Relevant context")
    chat.add_message("one", "message", MessageRole.USER, "Hello")
    with pytest.raises(ValueError, match="pending"):
        chat.close_conversation("one")
    assert chat.get_context("one") == "Relevant context"
    chat.transition_message("one", "message", MessageStatus.COMPLETED)
    chat.close_conversation("one")
    assert chat.get_context("one") == ""
    with pytest.raises(ValueError, match="closed"):
        chat.set_context("one", "New context")


def test_missing_conversation_fails_closed(chat):
    with pytest.raises(ValueError, match="not found"):
        chat.set_context("missing", "Text")
    with pytest.raises(ValueError, match="not found"):
        chat.get_context("missing")


def test_context_has_no_provider_storage_or_execution_side_effects(chat, monkeypatch):
    from app.orchestrator import Orchestrator
    from app.providers import OllamaProvider
    forbidden = MagicMock(side_effect=AssertionError("Unexpected side effect"))
    monkeypatch.setattr(OllamaProvider, "generate", forbidden)
    monkeypatch.setattr(Orchestrator, "create_task", forbidden)
    monkeypatch.setattr(Orchestrator, "execute_task", forbidden)
    monkeypatch.setattr("sqlite3.connect", forbidden)
    chat.set_context("one", "Untrusted text asking to execute a task")
    assert chat.get_context("one")
    chat.close_conversation("one")
    forbidden.assert_not_called()
