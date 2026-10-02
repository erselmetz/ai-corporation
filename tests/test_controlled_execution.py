from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

import pytest

from app.orchestrator.task import Task, TaskStatus
from app.orchestrator.router import RoutingError
from app.providers import AIProvider
from app.resources import ResourceLimits, ProviderLimit, ModelLimit, ResourceCapacityError
from app.runtime.factory import create_corporation_runtime


class Provider(AIProvider):
    def __init__(self, *, blocking=False, fail=False, expected=1):
        self.blocking, self.fail, self.expected = blocking, fail, expected
        self.entered = Event(); self.finish = Event(); self.lock = Lock()
        self.calls = 0; self.active = 0; self.peak = 0

    def generate(self, model, prompt):
        with self.lock:
            self.calls += 1; self.active += 1; self.peak = max(self.peak, self.active)
            if self.active >= self.expected:
                self.entered.set()
        try:
            if self.blocking and not self.finish.wait(5):
                raise RuntimeError("Test did not release provider")
            if self.fail:
                raise RuntimeError("Provider failed")
            return "Deterministic result"
        finally:
            with self.lock:
                self.active -= 1


def setup(provider, *, capacity=None):
    runtime = create_corporation_runtime()
    runtime.providers.remove("ollama")
    runtime.providers.register("ollama", provider)
    for identifier in ("a", "b", "c"):
        runtime.tasks.register(Task(identifier, identifier, "Work", assigned_agent="local_worker"))
    if capacity is not None:
        runtime.application_service.resource_manager(ResourceLimits(capacity,
            (ProviderLimit("ollama", capacity),), (ModelLimit("ollama", "llama3.2:3b", capacity),)))
    return runtime, runtime.application_service


def test_missing_configuration_denies_controlled_execution_and_preserves_direct_path():
    provider = Provider()
    runtime, application = setup(provider)
    with pytest.raises(RuntimeError, match="not configured"):
        application.execute_controlled_task("a")
    assert runtime.tasks.get("a").status is TaskStatus.PENDING
    assert provider.calls == 0
    assert application.execute_task("a").status == "completed"
    assert provider.calls == 1


def test_capacity_and_duplicate_admission_before_provider_calls():
    provider = Provider(blocking=True)
    runtime, application = setup(provider, capacity=1)
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(application.execute_controlled_task, "a")
        try:
            assert provider.entered.wait(3)
            with pytest.raises(ValueError, match="active controlled"):
                application.execute_controlled_task("a")
            with pytest.raises(ResourceCapacityError):
                application.execute_controlled_task("b")
            assert runtime.tasks.get("b").status is TaskStatus.PENDING
            assert provider.calls == 1
        finally:
            provider.finish.set()
        assert first.result(timeout=3).status == "completed"
    assert application.resource_manager().snapshot().global_capacity.allocated == 0
    with pytest.raises(ValueError, match="pending"):
        application.execute_controlled_task("a")
    assert application.execute_controlled_task("b").status == "completed"


def test_two_tasks_run_in_parallel_within_configured_capacity():
    provider = Provider(blocking=True, expected=2)
    _, application = setup(provider, capacity=2)
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending = [executor.submit(application.execute_controlled_task, identifier) for identifier in ("a", "b")]
        try:
            assert provider.entered.wait(3)
            assert provider.peak == 2
            assert application.resource_manager().snapshot().global_capacity.allocated == 2
        finally:
            provider.finish.set()
        assert all(result.result(timeout=3).status == "completed" for result in pending)
    assert application.resource_manager().snapshot().global_capacity.allocated == 0


def test_provider_failure_releases_slot_and_preserves_task_failure():
    provider = Provider(fail=True)
    _, application = setup(provider, capacity=1)
    result = application.execute_controlled_task("a")
    assert result.status == "failed"
    assert result.error == "Provider failed"
    assert application.resource_manager().snapshot().global_capacity.allocated == 0
    assert application.execute_controlled_task("b").status == "failed"
    assert provider.calls == 2


def test_missing_task_and_route_error_do_not_consume_capacity():
    provider = Provider()
    runtime, application = setup(provider, capacity=1)
    with pytest.raises(ValueError):
        application.execute_controlled_task("missing")
    from dataclasses import replace
    runtime.tasks.update(replace(runtime.tasks.get("a"), assigned_agent="missing-agent"))
    with pytest.raises(RoutingError, match="Explicitly assigned agent.*not found"):
        application.execute_controlled_task("a")
    assert application.resource_manager().snapshot().global_capacity.allocated == 0
    assert runtime.tasks.get("a").status is TaskStatus.PENDING
    assert provider.calls == 0

@pytest.mark.parametrize("provider_slots,model_slots", [(1, 2), (2, 1)])
def test_provider_and_model_limits_apply_to_controlled_calls(provider_slots, model_slots):
    provider = Provider(blocking=True)
    runtime, application = setup(provider)
    application.resource_manager(ResourceLimits(2, (ProviderLimit("ollama", provider_slots),),
        (ModelLimit("ollama", "llama3.2:3b", model_slots),)))
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(application.execute_controlled_task, "a")
        try:
            assert provider.entered.wait(3)
            with pytest.raises(ResourceCapacityError):
                application.execute_controlled_task("b")
            assert provider.calls == 1
            assert runtime.tasks.get("b").status is TaskStatus.PENDING
        finally:
            provider.finish.set()
        assert pending.result(timeout=3).status == "completed"
    snapshot = application.resource_manager().snapshot()
    assert snapshot.global_capacity.allocated == 0
    assert all(capacity.allocated == 0 for _, capacity in snapshot.providers)
    assert all(capacity.allocated == 0 for _, _, capacity in snapshot.models)


def test_runtime_audit_failure_releases_capacity_without_automatic_retry():
    from unittest.mock import patch
    provider = Provider()
    runtime, application = setup(provider, capacity=1)
    with patch.object(runtime.orchestrator.logger, "log", side_effect=RuntimeError("Audit storage failed")):
        with pytest.raises(RuntimeError, match="Audit storage failed"):
            application.execute_controlled_task("a")
    assert runtime.tasks.get("a").status is TaskStatus.RUNNING
    assert provider.calls == 0
    assert application.resource_manager().snapshot().global_capacity.allocated == 0
    with pytest.raises(ValueError, match="pending"):
        application.execute_controlled_task("a")
    assert application.execute_controlled_task("b").status == "completed"
