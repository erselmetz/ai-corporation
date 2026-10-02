from dataclasses import FrozenInstanceError, replace
from unittest.mock import Mock, patch

import pytest

from app.orchestrator.task import Task, TaskStatus
from app.providers.availability import AvailabilityState
from app.resources import ModelLimit, ProviderLimit, ResourceLimits
from app.application import (
    CapacityScope,
    MonitoringSignalType,
)
from app.runtime.factory import create_corporation_runtime


def test_on_demand_report_is_read_only_and_never_probes_providers():
    runtime = create_corporation_runtime()
    resource_manager = runtime.application_service.resource_manager(
        ResourceLimits(
            1,
            (ProviderLimit("ollama", 1),),
            (ModelLimit("ollama", "llama3.2:3b", 1),),
        )
    )
    resource_manager.allocate(
        "active-slot",
        provider_id="ollama",
        model_id="llama3.2:3b",
    )
    failed_task = Task(
        "failed-monitor-task",
        "Failed task",
        "Sensitive details do not belong in monitoring output",
        assigned_agent="local_worker",
        status=TaskStatus.FAILED,
        error="secret-provider-token",
    )
    pending_task = Task(
        "pending-monitor-task",
        "Pending task",
        "Pending",
        assigned_agent="local_worker",
    )
    runtime.tasks.register(failed_task)
    runtime.tasks.register(pending_task)

    task_state = tuple(replace(task) for task in runtime.tasks.all())
    agent_state = tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    )
    resource_state = resource_manager.snapshot()
    provider = runtime.providers.get("ollama")
    availability_check = Mock(side_effect=AssertionError("Provider probe attempted"))
    generate = Mock(side_effect=AssertionError("Task executed"))
    with (
        patch.object(provider, "check_availability", availability_check),
        patch.object(provider, "generate", generate),
    ):
        report = runtime.application_service.monitor_system()

    availability_check.assert_not_called()
    generate.assert_not_called()
    assert report.provider_availability is AvailabilityState.UNKNOWN
    assert report.registered_provider_ids == ("ollama",)
    assert report.resource_capacities is not None
    assert tuple(
        (status, count) for status, count in report.task_status_counts
    ) == (
        (TaskStatus.PENDING, 1),
        (TaskStatus.RUNNING, 0),
        (TaskStatus.COMPLETED, 0),
        (TaskStatus.FAILED, 1),
    )
    failed_signal = next(
        signal
        for signal in report.signals
        if signal.type is MonitoringSignalType.FAILED_TASKS
    )
    assert failed_signal.task_ids == ("failed-monitor-task",)
    assert "secret-provider-token" not in repr(report)
    exhausted = [
        signal.capacity
        for signal in report.signals
        if signal.type is MonitoringSignalType.CAPACITY_EXHAUSTED
    ]
    assert {item.scope for item in exhausted} == {
        CapacityScope.GLOBAL,
        CapacityScope.PROVIDER,
        CapacityScope.MODEL,
    }
    assert tuple(replace(task) for task in runtime.tasks.all()) == task_state
    assert tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    ) == agent_state
    assert resource_manager.snapshot() == resource_state
    with pytest.raises(FrozenInstanceError):
        report.provider_availability = AvailabilityState.AVAILABLE


def test_report_does_not_invent_resource_capacity_when_unconfigured():
    runtime = create_corporation_runtime()

    report = runtime.application_service.monitor_system()

    assert report.resource_capacities is None
    assert report.provider_availability is AvailabilityState.UNKNOWN
    assert report.signals == ()


def test_report_bounds_failed_task_ids_and_reports_omitted_count():
    runtime = create_corporation_runtime()
    provider = runtime.providers.get("ollama")
    for index in range(101):
        runtime.providers.register(f"provider-{index:03}", provider)
    runtime.providers.register("p" * 257, provider)
    for index in range(101):
        runtime.tasks.register(
            Task(
                f"failed-{index:03}",
                "Failed task",
                "Failed",
                status=TaskStatus.FAILED,
                error="not exposed",
            )
        )
    runtime.tasks.register(
        Task("t" * 257, "Long ID", "Failed", status=TaskStatus.FAILED)
    )

    report = runtime.application_service.monitor_system()
    signal = next(
        item for item in report.signals if item.type is MonitoringSignalType.FAILED_TASKS
    )

    assert len(signal.task_ids) == 100
    assert signal.omitted_task_count == 2
    assert signal.task_ids[0] == "failed-000"
    assert signal.task_ids[-1] == "failed-099"
    assert len(report.registered_provider_ids) == 100
    assert report.omitted_provider_count == 3
