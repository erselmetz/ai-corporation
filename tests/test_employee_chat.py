from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest

from app.agents import Agent, AgentRegistry, Employee, EmployeeRegistry
from app.conversations import (
    ConversationStatus,
    EmployeeChatService,
    MessageRole,
    MessageStatus,
)
from app.orchestrator import Orchestrator
from app.providers import OllamaProvider
from app.runtime.factory import create_corporation_runtime


@pytest.fixture
def chat_setup():
    agents = AgentRegistry()
    first = Agent("agent-1", "First Agent", "Worker", "ollama", "model-1")
    second = Agent("agent-2", "Second Agent", "Worker", "ollama", "model-2")
    agents.register(first)
    agents.register(second)
    employees = EmployeeRegistry()
    employees.register(Employee("employee-1", "First Employee", "Worker", agent=first))
    employees.register(Employee("employee-2", "Second Employee", "Worker", agent=second))
    employees.register(Employee("unassigned", "Unassigned", "Worker"))
    return EmployeeChatService(employees, agents), employees, agents


def test_employee_chat_records_explicit_identity_order_and_message_lifecycle(chat_setup):
    chat, _, _ = chat_setup
    created = chat.start_conversation("chat-1", employee_id="employee-2")
    assert created.id == "chat-1"
    assert created.target.scope == "employee"
    assert created.target.employee_id == "employee-2"
    assert created.target.agent_id == "agent-2"
    assert created.status is ConversationStatus.OPEN
    assert created.messages == ()

    chat.add_message("chat-1", "user-1", MessageRole.USER, "Hello")
    chat.transition_message("chat-1", "user-1", MessageStatus.COMPLETED)
    chat.add_message("chat-1", "assistant-1", MessageRole.ASSISTANT, "Manually supplied reply")
    completed = chat.transition_message("chat-1", "assistant-1", MessageStatus.COMPLETED)
    assert [(m.id, m.role, m.content, m.status) for m in completed.messages] == [
        ("user-1", MessageRole.USER, "Hello", MessageStatus.COMPLETED),
        ("assistant-1", MessageRole.ASSISTANT, "Manually supplied reply", MessageStatus.COMPLETED),
    ]
    closed = chat.close_conversation("chat-1")
    assert closed.status is ConversationStatus.CLOSED
    assert closed.target == created.target
    assert chat.get_conversation("chat-1") == closed


def test_direct_agent_scope_is_explicit_and_conversations_are_isolated(chat_setup):
    chat, _, _ = chat_setup
    employee_chat = chat.start_conversation("employee-chat", employee_id="employee-1")
    agent_chat = chat.start_conversation("agent-chat", agent_id="agent-2")
    assert agent_chat.target.scope == "agent"
    assert agent_chat.target.employee_id is None
    assert agent_chat.target.agent_id == "agent-2"
    chat.add_message("agent-chat", "message", MessageRole.SYSTEM, "Explicitly recorded text")
    assert chat.get_conversation("employee-chat") == employee_chat
    with pytest.raises(ValueError, match="Message not found"):
        chat.transition_message("employee-chat", "message", MessageStatus.COMPLETED)


def test_targets_are_snapshots_and_do_not_follow_employee_reassignment(chat_setup):
    chat, employees, agents = chat_setup
    original = chat.start_conversation("chat", employee_id="employee-1")
    employees.get("employee-1").assign_agent(agents.get("agent-2"))
    updated = chat.add_message("chat", "message", MessageRole.USER, "Hello")
    assert updated.target == original.target
    assert updated.target.agent_id == "agent-1"
    # A newly selected conversation observes the new assignment.
    assert chat.start_conversation("new", employee_id="employee-1").target.agent_id == "agent-2"


def test_returned_snapshots_cannot_mutate_core_state(chat_setup):
    chat, _, _ = chat_setup
    created = chat.start_conversation("chat", agent_id="agent-1")
    pending = chat.add_message("chat", "message", MessageRole.USER, "Hello")
    with pytest.raises(FrozenInstanceError):
        pending.target.agent_id = "agent-2"
    with pytest.raises(FrozenInstanceError):
        pending.messages[0].status = MessageStatus.COMPLETED
    with pytest.raises(FrozenInstanceError):
        pending.status = ConversationStatus.CLOSED
    chat.transition_message("chat", "message", MessageStatus.FAILED)
    assert created.messages == ()
    assert pending.messages[0].status is MessageStatus.PENDING
    assert chat.get_conversation("chat").messages[0].status is MessageStatus.FAILED


@pytest.mark.parametrize(
    "selectors",
    [{}, {"employee_id": "employee-1", "agent_id": "agent-1"}],
)
def test_exactly_one_target_is_required(chat_setup, selectors):
    chat, _, _ = chat_setup
    with pytest.raises(ValueError, match="Select exactly one"):
        chat.start_conversation("chat", **selectors)
    with pytest.raises(ValueError, match="Conversation not found"):
        chat.get_conversation("chat")


@pytest.mark.parametrize(
    ("selectors", "error"),
    [
        ({"employee_id": "missing"}, "Employee not found"),
        ({"agent_id": "missing"}, "Agent not found"),
        ({"employee_id": "unassigned"}, "no assigned Agent"),
        ({"employee_id": " "}, "Employee id"),
        ({"agent_id": " "}, "Agent id"),
        ({"employee_id": 123}, "Employee id"),
        ({"agent_id": 123}, "Agent id"),
    ],
)
def test_invalid_or_missing_target_does_not_create_a_conversation(chat_setup, selectors, error):
    chat, _, _ = chat_setup
    with pytest.raises(ValueError, match=error):
        chat.start_conversation("chat", **selectors)
    with pytest.raises(ValueError, match="Conversation not found"):
        chat.get_conversation("chat")


def test_employee_requires_a_registered_agent_without_fallback(chat_setup):
    chat, employees, _ = chat_setup
    employees.get("employee-1").assign_agent(
        Agent("unregistered", "Unregistered", "Worker", "ollama", "model")
    )
    with pytest.raises(ValueError, match="Agent not found: unregistered"):
        chat.start_conversation("chat", employee_id="employee-1")


@pytest.mark.parametrize("conversation_id", ["", " ", None, 123])
def test_conversation_id_validation(chat_setup, conversation_id):
    chat, _, _ = chat_setup
    with pytest.raises(ValueError, match="Conversation id"):
        chat.start_conversation(conversation_id, agent_id="agent-1")
    with pytest.raises(ValueError, match="Conversation id"):
        chat.get_conversation(conversation_id)


def test_duplicate_conversation_does_not_retarget_or_replace_messages(chat_setup):
    chat, _, _ = chat_setup
    chat.start_conversation("chat", employee_id="employee-1")
    before = chat.add_message("chat", "message", MessageRole.USER, "Hello")
    with pytest.raises(ValueError, match="Conversation already exists"):
        chat.start_conversation("chat", agent_id="agent-2")
    assert chat.get_conversation("chat") == before


@pytest.mark.parametrize(
    ("message_id", "role", "content", "error"),
    [
        (" ", MessageRole.USER, "Hello", ValueError),
        (123, MessageRole.USER, "Hello", ValueError),
        ("message", "user", "Hello", TypeError),
        ("message", MessageRole.USER, " ", ValueError),
        ("message", MessageRole.USER, None, ValueError),
    ],
)
def test_message_validation_leaves_conversation_unchanged(chat_setup, message_id, role, content, error):
    chat, _, _ = chat_setup
    before = chat.start_conversation("chat", agent_id="agent-1")
    with pytest.raises(error):
        chat.add_message("chat", message_id, role, content)
    assert chat.get_conversation("chat") == before


def test_missing_conversation_for_all_operations(chat_setup):
    chat, _, _ = chat_setup
    operations = [
        lambda: chat.get_conversation("missing"),
        lambda: chat.add_message("missing", "message", MessageRole.USER, "Hello"),
        lambda: chat.transition_message("missing", "message", MessageStatus.FAILED),
        lambda: chat.close_conversation("missing"),
    ]
    for operation in operations:
        with pytest.raises(ValueError, match="Conversation not found"):
            operation()


def test_lifecycle_failures_are_deterministic_and_preserve_state(chat_setup):
    chat, _, _ = chat_setup
    chat.start_conversation("chat", agent_id="agent-1")
    pending = chat.add_message("chat", "message", MessageRole.USER, "Hello")
    operations = [
        (lambda: chat.close_conversation("chat"), ValueError, "pending messages"),
        (lambda: chat.add_message("chat", "message", MessageRole.USER, "Again"), ValueError, "already exists"),
        (lambda: chat.transition_message("chat", "missing", MessageStatus.FAILED), ValueError, "Message not found"),
        (lambda: chat.transition_message("chat", " ", MessageStatus.FAILED), ValueError, "Message id"),
        (lambda: chat.transition_message("chat", "message", "completed"), TypeError, "MessageStatus"),
        (lambda: chat.transition_message("chat", "message", MessageStatus.PENDING), ValueError, "Invalid message transition"),
    ]
    for operation, error, match in operations:
        with pytest.raises(error, match=match):
            operation()
        assert chat.get_conversation("chat") == pending

    failed = chat.transition_message("chat", "message", MessageStatus.FAILED)
    with pytest.raises(ValueError, match="Invalid message transition"):
        chat.transition_message("chat", "message", MessageStatus.COMPLETED)
    assert chat.get_conversation("chat") == failed
    closed = chat.close_conversation("chat")
    with pytest.raises(ValueError, match="closed conversation"):
        chat.add_message("chat", "new", MessageRole.USER, "Again")
    with pytest.raises(ValueError, match="already closed"):
        chat.close_conversation("chat")
    assert chat.get_conversation("chat") == closed


def test_chat_has_no_provider_task_memory_or_persistence_side_effects(monkeypatch):
    runtime = create_corporation_runtime()
    before_tasks = runtime.tasks.all()
    before_projects = runtime.projects.all()
    before_employees = runtime.employees.all()
    before_agents = runtime.agents.all()
    before_activity = runtime.orchestrator.logger.list_activity()
    forbidden = MagicMock(side_effect=AssertionError("Unexpected chat side effect"))
    for name in ("run_agent", "run_employee", "create_task", "execute_task"):
        monkeypatch.setattr(Orchestrator, name, forbidden)
    monkeypatch.setattr(OllamaProvider, "generate", forbidden)
    for name in ("remember", "recall", "memories", "forget"):
        monkeypatch.setattr(Agent, name, forbidden)
    with monkeypatch.context() as no_storage:
        no_storage.setattr("sqlite3.connect", forbidden)
        chat = EmployeeChatService(runtime.employees, runtime.agents)
        chat.start_conversation("chat", employee_id="local_employee")
        chat.add_message("chat", "message", MessageRole.USER, "Create and execute a Task")
        chat.transition_message("chat", "message", MessageStatus.COMPLETED)
        closed = chat.close_conversation("chat")
        assert chat.get_conversation("chat") == closed
        # Sessions belong to the service instance and are not reloaded.
        with pytest.raises(ValueError, match="Conversation not found"):
            EmployeeChatService(runtime.employees, runtime.agents).get_conversation("chat")
    forbidden.assert_not_called()
    assert runtime.tasks.all() == before_tasks
    assert runtime.projects.all() == before_projects
    assert runtime.employees.all() == before_employees
    assert runtime.agents.all() == before_agents
    assert runtime.orchestrator.logger.list_activity() == before_activity
