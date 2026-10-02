import pytest
from app.providers import ProviderRegistry, AIProvider
from app.resources import ResourceManager, ResourceLimits, ProviderLimit, ModelLimit, ResourceCapacityError
from app.resources.manager import Capacity, ResourceSnapshot

class NeverCalled(AIProvider):
    def generate(self, model, prompt):
        raise AssertionError("Snapshot must not call a provider")

def manager():
    registry = ProviderRegistry()
    registry.register("p", NeverCalled())
    return ResourceManager(ResourceLimits(1, (ProviderLimit("p", 1),), (ModelLimit("p", "m", 1),)), registry)

def test_history_counts_used_ids_and_release_only_restores_active_slots():
    resource = manager()
    first = resource.snapshot()
    assert first.allocation_id_history_capacity == Capacity(resource.MAX_ALLOCATION_IDS, 0)
    resource.allocate("one", provider_id="p", model_id="m")
    assert resource.snapshot().allocation_id_history_capacity.allocated == 1
    resource.release("one")
    released = resource.snapshot()
    assert released.global_capacity.remaining == 1
    assert released.providers[0][1].remaining == 1
    assert released.models[0][2].remaining == 1
    assert released.allocation_id_history_capacity.remaining == resource.MAX_ALLOCATION_IDS - 1
    with pytest.raises(ValueError, match="already been used"):
        resource.allocate("one", provider_id="p", model_id="m")
    assert resource.snapshot() == released
    resource.allocate("two", provider_id="p", model_id="m")
    assert resource.snapshot().allocation_id_history_capacity.allocated == 2
    assert first.allocation_id_history_capacity.allocated == 0

def test_real_public_history_exhaustion_with_all_slots_free():
    resource = manager()
    for index in range(resource.MAX_ALLOCATION_IDS):
        resource.allocate(str(index), provider_id="p", model_id="m")
        resource.release(str(index))
    snapshot = resource.snapshot()
    assert snapshot.global_capacity.remaining == 1
    assert snapshot.allocation_id_history_capacity.remaining == 0
    with pytest.raises(ResourceCapacityError, match="history limit"):
        resource.allocate("fresh", provider_id="p", model_id="m")
    assert resource.snapshot() == snapshot

def test_old_positional_snapshot_constructor_keeps_unknown_history_default():
    old = ResourceSnapshot(Capacity(1, 0), (), (), (), (), "unknown", "unknown")
    assert old.global_capacity.remaining == 1
    assert old.hardware_capacity == old.provider_health == "unknown"
    assert old.allocation_id_history_capacity is None
