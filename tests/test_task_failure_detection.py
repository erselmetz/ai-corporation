from dataclasses import FrozenInstanceError

import pytest

from app.orchestrator import Task, TaskFailureCategory, TaskRegistry, TaskStatus
from app.providers import AIProvider
from app.runtime.factory import create_corporation_runtime


class FailingProvider(AIProvider):
    def generate(self, model: str, prompt: str) -> str:
        raise RuntimeError("auth_token=do-not-disclose")


def test_known_routing_failure_is_persisted_and_reported_without_raw_error():
    runtime = create_corporation_runtime()
    task = Task(
        "routing-failure",
        "Unroutable",
        "No routing requirement",
    )
    runtime.tasks.register(task)

    result = runtime.application_service.execute_task(task.id)
    report = runtime.application_service.detect_failures()
    reloaded = runtime.tasks.get(task.id)

    assert result.status == TaskStatus.FAILED.value
    assert reloaded.failure_category is TaskFailureCategory.ROUTING
    assert report.total_failures == 1
    assert [(item.task_id, item.category) for item in report.failures] == [
        ("routing-failure", TaskFailureCategory.ROUTING)
    ]
    assert (
        TaskRegistry().get(task.id).failure_category
        is TaskFailureCategory.ROUTING
    )
    assert "No suitable agent found" not in repr(report)


def test_execution_failure_is_classified_and_secret_exception_text_is_not_reported():
    runtime = create_corporation_runtime()
    runtime.providers.remove("ollama")
    runtime.providers.register("ollama", FailingProvider())
    task = Task(
        "execution-failure",
        "Provider failure",
        "Run with failing Provider",
        assigned_agent="local_worker",
    )
    runtime.tasks.register(task)

    result = runtime.application_service.execute_task(task.id)
    report = runtime.application_service.detect_failures()
    persisted = runtime.tasks.get(task.id)

    assert result.status == TaskStatus.FAILED.value
    assert persisted.failure_category is TaskFailureCategory.EXECUTION
    assert report.failures[0].category is TaskFailureCategory.EXECUTION
    assert "auth_token=do-not-disclose" not in repr(report)
    with pytest.raises(FrozenInstanceError):
        report.failures[0].category = TaskFailureCategory.UNKNOWN


def test_unclassified_failure_is_unknown_and_failure_output_is_bounded():
    runtime = create_corporation_runtime()
    for index in range(101):
        runtime.tasks.register(
            Task(
                f"failure-{index:03}",
                "Historical failure",
                "Previously persisted error",
                status=TaskStatus.FAILED,
                error="old raw exception",
            )
        )
    runtime.tasks.register(
        Task(
            "oversized-" + "x" * 260,
            "Oversized identifier",
            "Failure",
            status=TaskStatus.FAILED,
            error="must not be exposed",
        )
    )

    report = runtime.application_service.detect_failures()

    assert report.total_failures == 102
    assert len(report.failures) == 100
    assert report.omitted_count == 2
    assert all(item.category is TaskFailureCategory.UNKNOWN for item in report.failures)
    assert report.failures[0].task_id == "failure-000"
    assert "old raw exception" not in repr(report)
    assert "must not be exposed" not in repr(report)
