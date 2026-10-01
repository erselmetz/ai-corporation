from unittest.mock import MagicMock

import pytest

from app.agents import Agent, AgentRegistry
from app.application.services.corporation_chat import CorporationChatService
from app.conversations import MessageStatus
from app.interface.command import CommandInterface
from app.orchestrator import Orchestrator


@pytest.fixture
def setup():
    orchestrator = MagicMock(spec=Orchestrator)
    orchestrator.agents = AgentRegistry()
    orchestrator.agents.register(Agent("agent", "Agent", "Worker", "ollama", "model"))
    orchestrator.run_agent.return_value = "Explicit reply"
    return CorporationChatService("corp", orchestrator), orchestrator


def test_organization_identity_history_and_no_task_execution(setup):
    chat, orchestrator = setup
    chat.start("one", "agent")
    chat.start("two", "agent")
    result = chat.send("one", "Hello")
    assert result.corporation_id == "corp"
    assert result.coordinator_agent_id == "agent"
    assert [m.content for m in result.messages] == ["Hello", "Explicit reply"]
    assert all(m.status is MessageStatus.COMPLETED for m in result.messages)
    assert chat.get("two").messages == ()
    chat.send("one", "Next")
    assert "Hello" in orchestrator.run_agent.call_args.args[1]
    assert "Hello" not in str(chat.get("two"))
    orchestrator.create_task.assert_not_called()
    orchestrator.execute_task.assert_not_called()


@pytest.mark.parametrize("reply", [None, "", "x" * 8193])
def test_invalid_provider_reply_records_failure_and_allows_closure(setup, reply):
    chat, orchestrator = setup
    orchestrator.run_agent.return_value = reply
    chat.start("one", "agent")
    with pytest.raises(RuntimeError, match="response failed"):
        chat.send("one", "Hello")
    assert chat.get("one").messages[0].status is MessageStatus.FAILED
    chat.close("one")


def test_provider_failure_does_not_expose_internal_error(setup):
    chat, orchestrator = setup
    orchestrator.run_agent.side_effect = RuntimeError("sensitive internal details")
    chat.start("one", "agent")
    with pytest.raises(RuntimeError, match="^Corporation chat response failed$"):
        chat.send("one", "Hello")
    assert len(chat.get("one").messages) == 1


def test_validation_and_closed_chat_do_not_call_provider(setup):
    chat, orchestrator = setup
    with pytest.raises(ValueError):
        chat.start("missing", "missing")
    chat.start("one", "agent")
    for text in [None, "", "x" * 8193]:
        with pytest.raises(ValueError):
            chat.send("one", text)
    assert chat.get("one").messages == ()
    chat.close("one")
    with pytest.raises(ValueError, match="closed"):
        chat.send("one", "Hello")
    orchestrator.run_agent.assert_not_called()


def test_prompt_limit_rejects_atomically(setup):
    chat, orchestrator = setup
    chat.start("one", "agent")
    orchestrator.run_agent.return_value = "x" * 8192
    chat.send("one", "x" * 8192)
    before = chat.get("one")
    chat.MAX_PROMPT_BYTES = 100
    with pytest.raises(ValueError, match="Prompt exceeds"):
        chat.send("one", "Next")
    assert chat.get("one") == before
    assert orchestrator.run_agent.call_count == 1


def test_cli_uses_application_boundary(setup, capsys):
    chat, _ = setup
    application = MagicMock()
    application.corporation_chat.return_value = chat
    interface = CommandInterface(MagicMock(), application)
    interface.handle_command("chat start one agent")
    interface.handle_command('chat send one "Hello organization"')
    assert "Explicit reply" in capsys.readouterr().out
    interface.handle_command("chat close one")
    assert "closed" in capsys.readouterr().out


def test_runtime_application_facade_uses_configured_identity(monkeypatch):
    from app.runtime.factory import create_corporation_runtime
    from app.providers import OllamaProvider
    provider = MagicMock(return_value="Fake response")
    monkeypatch.setattr(OllamaProvider, "generate", provider)
    runtime = create_corporation_runtime()
    chat = runtime.application_service.corporation_chat()
    assert chat is runtime.application_service.corporation_chat()
    chat.start("runtime-chat", "local_worker")
    result = chat.send("runtime-chat", "Hello")
    assert result.corporation_id == runtime.corporation.id
    assert result.messages[-1].content == "Fake response"
    provider.assert_called_once()
