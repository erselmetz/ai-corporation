from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.application.services.owned_chat import ChatConflict
from app.orchestrator.task import Task
from app.providers import AIProvider
from app.runtime.factory import create_corporation_runtime


class BlockingProvider(AIProvider):
    def __init__(self):
        self.entered = Event()
        self.release = Event()
        self.calls = []

    def generate(self, model, prompt):
        self.calls.append((model, prompt))
        self.entered.set()
        if not self.release.wait(5):
            raise RuntimeError("Test provider was not released")
        return "deterministic result"


def runtime_with_provider():
    runtime = create_corporation_runtime()
    provider = BlockingProvider()
    runtime.providers.remove("ollama")
    runtime.providers.register("ollama", provider)
    return runtime, provider


def test_assignment_is_rejected_during_agent_execution():
    runtime, provider = runtime_with_provider()
    with ThreadPoolExecutor(max_workers=1) as executor:
        execution = executor.submit(runtime.orchestrator.run_agent, "local_worker", "prompt")
        assert provider.entered.wait(5)
        with pytest.raises(ChatConflict, match="active work"):
            runtime.application_service.replace_model(
                "local_worker", "ollama", "different-model"
            )
        provider.release.set()
        assert execution.result(timeout=5) == "deterministic result"
    assert provider.calls == [("llama3.2:3b", "prompt")]


def test_running_task_is_not_silently_sent_to_a_changed_assignment():
    runtime, provider = runtime_with_provider()
    task = Task(
        "task-108", "Task", "Do not change the selected connection",
        assigned_agent="local_worker",
    )
    runtime.orchestrator.tasks.update = lambda _task: None

    def change_assignment_after_task_starts(_task_id, event, _message):
        if event == "TASK_STARTED":
            runtime.application_service.replace_model(
                "local_worker", "ollama", "changed-before-provider-call"
            )

    runtime.orchestrator.logger.log = change_assignment_after_task_starts
    result = runtime.orchestrator.execute_task(task)
    assert result.status.value == "failed"
    assert result.assigned_agent == "local_worker"
    assert "assignment changed before execution" in result.error
    assert provider.calls == []


def test_new_agent_execution_is_rejected_while_assignment_is_changing():
    runtime, provider = runtime_with_provider()
    with runtime.application_service.agent_assignment_change("local_worker"):
        with pytest.raises(RuntimeError, match="connection is changing"):
            runtime.orchestrator.run_agent("local_worker", "prompt")
    assert provider.calls == []
