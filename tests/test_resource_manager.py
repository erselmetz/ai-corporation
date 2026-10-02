from dataclasses import FrozenInstanceError
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from app.providers import ProviderRegistry
from app.resources import ResourceManager, ResourceLimits, ProviderLimit, ModelLimit, ResourceCapacityError
from app.runtime.factory import create_corporation_runtime


def manager(global_slots=3, provider_slots=2, model_slots=1):
    registry = ProviderRegistry()
    registry.register("p", Mock())
    registry.register("q", Mock())
    limits = ResourceLimits(global_slots, (ProviderLimit("p", provider_slots), ProviderLimit("q", 2)),
                            (ModelLimit("p", "a", model_slots), ModelLimit("p", "b", 2), ModelLimit("q", "a", 2)))
    return ResourceManager(limits, registry), registry


def test_explicit_tracking_release_and_immutable_snapshots():
    resource, registry = manager()
    resource.allocate("one", provider_id="p", model_id="a")
    snapshot = resource.snapshot()
    assert snapshot.global_capacity.remaining == 2
    assert snapshot.models[0][2].remaining == 0
    assert snapshot.hardware_capacity == snapshot.provider_health == "unknown"
    with pytest.raises(FrozenInstanceError):
        snapshot.allocations[0].model_id = "changed"
    resource.release("one")
    assert resource.snapshot().global_capacity.allocated == 0
    assert snapshot.global_capacity.allocated == 1
    with pytest.raises(KeyError):
        resource.release("one")
    with pytest.raises(ValueError, match="already been used"):
        resource.allocate("one", provider_id="p", model_id="a")
    assert not registry.get("p").mock_calls


@pytest.mark.parametrize("kind", ["global", "provider", "model"])
def test_each_capacity_boundary_rejects_atomically(kind):
    resource, _ = manager(global_slots=1 if kind == "global" else 3,
                          provider_slots=1 if kind == "provider" else 2)
    resource.allocate("first", provider_id="p", model_id="a")
    before = resource.snapshot()
    with pytest.raises(ResourceCapacityError):
        resource.allocate("next", provider_id="q" if kind == "global" else "p", model_id="b" if kind == "provider" else "a")
    assert resource.snapshot() == before


def test_unknown_unconfigured_and_removed_provider_denied_but_release_available():
    resource, registry = manager()
    for provider, model in [("missing", "a"), ("p", "missing")]:
        with pytest.raises(ValueError):
            resource.allocate("failed", provider_id=provider, model_id=model)
    resource.allocate("active", provider_id="p", model_id="a")
    registry.remove("p")
    assert resource.snapshot().registered_providers == ("q",)
    with pytest.raises(ValueError):
        resource.allocate("new", provider_id="p", model_id="a")
    resource.release("active")


@pytest.mark.parametrize("value", [0, -1, True, 1.5, 10001])
def test_invalid_capacity_configuration(value):
    with pytest.raises(ValueError):
        ProviderLimit("p", value)


def test_config_requires_explicit_unique_provider_model_limits():
    with pytest.raises(ValueError):
        ResourceLimits(1, (ProviderLimit("p", 1), ProviderLimit("p", 1)), (ModelLimit("p", "a", 1),))
    with pytest.raises(ValueError):
        ResourceLimits(1, (ProviderLimit("p", 1),), (ModelLimit("q", "a", 1),))
    with pytest.raises(ValueError):
        ResourceLimits(1, [ProviderLimit("p", 1)], (ModelLimit("p", "a", 1),))


def test_atomic_accounting_for_competing_explicit_allocations():
    resource, _ = manager(global_slots=1)
    def attempt(index):
        try:
            resource.allocate(str(index), provider_id="p", model_id="a")
            return True
        except ResourceCapacityError:
            return False
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(attempt, range(20))) == 1
    assert resource.snapshot().global_capacity.allocated == 1


def test_application_requires_explicit_configuration_and_preserves_manager():
    application = create_corporation_runtime().application_service
    with pytest.raises(RuntimeError):
        application.resource_manager()
    limits = ResourceLimits(1, (ProviderLimit("ollama", 1),), (ModelLimit("ollama", "llama3.2:3b", 1),))
    resource = application.resource_manager(limits)
    assert application.resource_manager() is resource
    with pytest.raises(ValueError):
        application.resource_manager(limits)
    assert application.list_tasks() == []
