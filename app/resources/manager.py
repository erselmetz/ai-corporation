"""Configured local slot accounting; not hardware telemetry or execution control."""
from dataclasses import dataclass
from threading import RLock


def identifier(value):
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 256:
        raise ValueError("Resource IDs must be nonempty text of at most 256 bytes")


def slots(value):
    if type(value) is not int or not 1 <= value <= 10000:
        raise ValueError("Slot limits must be integers from 1 to 10000")


@dataclass(frozen=True)
class ProviderLimit:
    provider_id: str
    slots: int

    def __post_init__(self):
        identifier(self.provider_id)
        slots(self.slots)


@dataclass(frozen=True)
class ModelLimit:
    provider_id: str
    model_id: str
    slots: int

    def __post_init__(self):
        identifier(self.provider_id)
        identifier(self.model_id)
        slots(self.slots)


@dataclass(frozen=True)
class ResourceLimits:
    global_slots: int
    providers: tuple[ProviderLimit, ...]
    models: tuple[ModelLimit, ...]

    def __post_init__(self):
        slots(self.global_slots)
        for values, kind in ((self.providers, ProviderLimit), (self.models, ModelLimit)):
            if not isinstance(values, tuple) or not 1 <= len(values) <= 100:
                raise ValueError("Resource limits require immutable tuples of 1 to 100 entries")
            if not all(isinstance(value, kind) for value in values):
                raise TypeError("Invalid resource limit entry")
        providers = {value.provider_id for value in self.providers}
        models = {(value.provider_id, value.model_id) for value in self.models}
        if len(providers) != len(self.providers) or len(models) != len(self.models):
            raise ValueError("Duplicate resource limits")
        if any(value.provider_id not in providers for value in self.models):
            raise ValueError("Every model requires an explicit provider limit")


@dataclass(frozen=True)
class Allocation:
    id: str
    provider_id: str
    model_id: str


@dataclass(frozen=True)
class Capacity:
    limit: int
    allocated: int

    @property
    def remaining(self):
        return self.limit - self.allocated


@dataclass(frozen=True)
class ResourceSnapshot:
    global_capacity: Capacity
    providers: tuple[tuple[str, Capacity], ...]
    models: tuple[tuple[str, str, Capacity], ...]
    allocations: tuple[Allocation, ...]
    registered_providers: tuple[str, ...]
    hardware_capacity: str = "unknown"
    provider_health: str = "unknown"


class ResourceCapacityError(ValueError):
    pass


class ResourceManager:
    MAX_ALLOCATION_IDS = 10000

    def __init__(self, limits: ResourceLimits, provider_registry):
        if not isinstance(limits, ResourceLimits):
            raise TypeError("Expected ResourceLimits")
        for limit in limits.providers:
            provider_registry.get(limit.provider_id)
        self._limits = limits
        self._registry = provider_registry
        self._allocations = {}
        self._used_ids = set()
        self._lock = RLock()

    def allocate(self, allocation_id: str, *, provider_id: str, model_id: str):
        for value in (allocation_id, provider_id, model_id):
            identifier(value)
        with self._lock:
            if allocation_id in self._used_ids:
                raise ValueError("Allocation ID has already been used")
            if len(self._used_ids) >= self.MAX_ALLOCATION_IDS:
                raise ResourceCapacityError("Local allocation history limit reached")
            self._registry.get(provider_id)
            provider = next((value for value in self._limits.providers if value.provider_id == provider_id), None)
            model = next((value for value in self._limits.models if (value.provider_id, value.model_id) == (provider_id, model_id)), None)
            if provider is None or model is None:
                raise ValueError("Resource has no configured slot limit")
            active = tuple(self._allocations.values())
            if (len(active) >= self._limits.global_slots
                    or sum(value.provider_id == provider_id for value in active) >= provider.slots
                    or sum((value.provider_id, value.model_id) == (provider_id, model_id) for value in active) >= model.slots):
                raise ResourceCapacityError("Configured slot capacity is exhausted")
            allocation = Allocation(allocation_id, provider_id, model_id)
            self._allocations[allocation_id] = allocation
            self._used_ids.add(allocation_id)
            return allocation

    def release(self, allocation_id: str):
        identifier(allocation_id)
        with self._lock:
            if allocation_id not in self._allocations:
                raise KeyError("No active allocation with this ID")
            return self._allocations.pop(allocation_id)

    def snapshot(self):
        with self._lock:
            active = tuple(sorted(self._allocations.values(), key=lambda item: item.id))
            providers = tuple((value.provider_id, Capacity(value.slots, sum(item.provider_id == value.provider_id for item in active)))
                              for value in sorted(self._limits.providers, key=lambda item: item.provider_id))
            models = tuple((value.provider_id, value.model_id, Capacity(value.slots, sum((item.provider_id, item.model_id) == (value.provider_id, value.model_id) for item in active)))
                           for value in sorted(self._limits.models, key=lambda item: (item.provider_id, item.model_id)))
            registered = tuple(sorted(value.provider_id for value in self._limits.providers if self._registry.exists(value.provider_id)))
            return ResourceSnapshot(Capacity(self._limits.global_slots, len(active)), providers, models, active, registered)
