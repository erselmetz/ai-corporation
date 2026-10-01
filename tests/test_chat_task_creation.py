from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest

from app.agents import Agent, AgentRegistry
from app.application.services.corporation_chat import CorporationChatService
from app.conversations import MessageRole, MessageStatus
from app.interface.command import CommandInterface
from app.orchestrator import Orchestrator, Task, TaskStatus


@pytest.fixture
def setup():
    orchestrator = MagicMock(spec=Orchestrator)
    orchestrator.agents = AgentRegistry()
    orchestrator.agents.register(Agent("agent", "Agent", "Worker", "ollama", "model"))
    orchestrator.projects = MagicMock()
    orchestrator.run_agent.return_value = "Reply"
    orchestrator.create_task.return_value = Task("task", "Title", "Request", "project", "agent")
    chat = CorporationChatService("corp", orchestrator)
    chat.start("one", "agent")
    record = chat.send("one", "Request")
    return chat, orchestrator, record.messages[0].id


def test_review_confirm_and_replay_prevention(setup):
    chat, orchestrator, source = setup
    review = chat.review_task("one", source, "Title", "project", "agent")
    assert review.description == "Request"
    with pytest.raises(FrozenInstanceError):
        review.agent_id = "other"
    orchestrator.create_task.assert_not_called()
    with pytest.raises(ValueError, match="confirmation"):
        chat.confirm_task(review.id)
    result = chat.confirm_task(review.id, confirmed=True)
    assert result.status is TaskStatus.PENDING
    assert result.review_id == review.id
    orchestrator.create_task.assert_called_once_with("Title", "Request", "project", agent_id="agent")
    with pytest.raises(ValueError, match="consumed"):
        chat.confirm_task(review.id, confirmed=True)
    orchestrator.execute_task.assert_not_called()


def test_only_completed_user_messages_are_reviewable(setup):
    chat, orchestrator, _ = setup
    assistant = chat.get("one").messages[-1].id
    for source in ["missing", assistant]:
        with pytest.raises(ValueError, match="completed user"):
            chat.review_task("one", source, "Title", "project", "agent")
    orchestrator.create_task.assert_not_called()


def test_missing_resources_and_closed_chat_fail_closed(setup):
    chat, orchestrator, source = setup
    with pytest.raises(ValueError):
        chat.review_task("one", source, "Title", "project", "missing-agent")
    review = chat.review_task("one", source, "Title", "project", "agent")
    orchestrator.projects.get.side_effect = ValueError("Project missing")
    with pytest.raises(ValueError, match="Project missing"):
        chat.confirm_task(review.id, confirmed=True)
    orchestrator.projects.get.side_effect = None
    chat.close("one")
    with pytest.raises(ValueError, match="closed"):
        chat.confirm_task(review.id, confirmed=True)
    orchestrator.create_task.assert_not_called()


def test_uncertain_creation_failure_consumes_review(setup):
    chat, orchestrator, source = setup
    review = chat.review_task("one", source, "Title", "project", "agent")
    orchestrator.create_task.side_effect = RuntimeError("Persistence error")
    with pytest.raises(RuntimeError):
        chat.confirm_task(review.id, confirmed=True)
    with pytest.raises(ValueError, match="consumed"):
        chat.confirm_task(review.id, confirmed=True)
    assert orchestrator.create_task.call_count == 1


def test_cli_displays_review_and_requires_confirmation_token(setup, capsys):
    chat, orchestrator, source = setup
    application = MagicMock()
    application.corporation_chat.return_value = chat
    cli = CommandInterface(MagicMock(), application)
    cli.handle_command(f'chat review-task one {source} "Title" project agent')
    output = capsys.readouterr().out
    assert "description='Request'" in output
    assert "route=explicit_agent" in output
    review_id = output.split()[1].rstrip(":")
    cli.handle_command(f"chat confirm-task {review_id} yes")
    orchestrator.create_task.assert_not_called()
    cli.handle_command(f"chat confirm-task {review_id} CONFIRM")
    assert "Task task: pending" in capsys.readouterr().out


def test_runtime_conversion_persists_pending_task_without_provider_execution(monkeypatch):
    from app.providers import OllamaProvider
    from app.runtime.factory import create_corporation_runtime
    monkeypatch.setattr(OllamaProvider, "generate", lambda *_: "Reply")
    runtime = create_corporation_runtime()
    project = runtime.application_service.create_project("Chat project", "")
    chat = runtime.application_service.corporation_chat()
    chat.start("one", "local_worker")
    source = chat.send("one", "Do explicit work").messages[0].id
    review = chat.review_task("one", source, "Reviewed work", project.id, "local_worker")
    forbidden = MagicMock(side_effect=AssertionError("Execution is forbidden"))
    monkeypatch.setattr(OllamaProvider, "generate", forbidden)
    result = chat.confirm_task(review.id, confirmed=True)
    task = runtime.application_service.get_task(result.task_id)
    assert task.status == "pending"
    assert task.assigned_agent == "local_worker"
    assert task.description == "Do explicit work"
    forbidden.assert_not_called()
