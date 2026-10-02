"""On-demand, read-only monitoring over local runtime snapshots."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from app.orchestrator.task import TaskStatus
from app.orchestrator.task_registry import TaskRegistry
from app.providers import ProviderRegistry
from app.providers.availability import AvailabilityState
from app.resources.manager import ResourceManager, ResourceSnapshot


class MonitoringSignalType(Enum):
    FAILED_TASKS = "failed_tasks"
    CAPACITY_EXHAUSTED = "capacity_exhausted"


class CapacityScope(Enum):
    GLOBAL = "global"
    PROVIDER = "provider"
    MODEL = "model"
    ALLOCATION_HISTORY = "allocation_history"


@dataclass(frozen=True, slots=True)
class CapacityObservation:
    scope: CapacityScope
    limit: int
    allocated: int
    remaining: int
    provider_id: str | None = None
    model_id: str | None = None


@dataclass(frozen=True, slots=True)
class MonitoringSignal:
    type: MonitoringSignalType
    task_ids: tuple[str, ...] = ()
    omitted_task_count: int = 0
    capacity: CapacityObservation | None = None


@dataclass(frozen=True, slots=True)
class SystemMonitoringReport:
    observed_at: datetime
    task_status_counts: tuple[tuple[TaskStatus, int], ...]
    registered_provider_ids: tuple[str, ...]
    omitted_provider_count: int
    provider_availability: AvailabilityState
    resource_capacities: tuple[CapacityObservation, ...] | None
    signals: tuple[MonitoringSignal, ...]


class SystemMonitoringService:
    MAX_REPORTED_TASK_IDS = 100
    MAX_REPORTED_PROVIDER_IDS = 100
    MAX_REPORTED_ID_BYTES = 256

    def __init__(
        self,
        *,
        tasks: TaskRegistry,
        providers: ProviderRegistry,
        resource_manager: ResourceManager | None,
    ):
        self._tasks = tasks
        self._providers = providers
        self._resource_manager = resource_manager

    def report(self) -> SystemMonitoringReport:
        tasks = tuple((task.id, task.status) for task in self._tasks.all())
        task_status_counts = tuple(
            (status, sum(task_status is status for _, task_status in tasks))
            for status in TaskStatus
        )
        failed_task_ids, omitted_task_count = _bounded_identifiers(
            (task_id for task_id, status in tasks if status is TaskStatus.FAILED),
            self.MAX_REPORTED_TASK_IDS,
            self.MAX_REPORTED_ID_BYTES,
        )
        signals: list[MonitoringSignal] = []
        if failed_task_ids or omitted_task_count:
            signals.append(
                MonitoringSignal(
                    type=MonitoringSignalType.FAILED_TASKS,
                    task_ids=failed_task_ids,
                    omitted_task_count=omitted_task_count,
                )
            )

        resource_snapshot = (
            self._resource_manager.snapshot()
            if self._resource_manager is not None
            else None
        )
        capacities = _capacity_observations(resource_snapshot)
        for capacity in capacities or ():
            if capacity.remaining <= 0:
                signals.append(
                    MonitoringSignal(
                        type=MonitoringSignalType.CAPACITY_EXHAUSTED,
                        capacity=capacity,
                    )
                )

        reported_provider_ids, omitted_provider_count = _bounded_identifiers(
            self._providers.all(),
            self.MAX_REPORTED_PROVIDER_IDS,
            self.MAX_REPORTED_ID_BYTES,
        )
        return SystemMonitoringReport(
            observed_at=datetime.now(timezone.utc),
            task_status_counts=task_status_counts,
            registered_provider_ids=reported_provider_ids,
            omitted_provider_count=omitted_provider_count,
            provider_availability=AvailabilityState.UNKNOWN,
            resource_capacities=capacities,
            signals=tuple(signals),
        )


def _bounded_identifiers(
    identifiers: Iterable[str],
    limit: int,
    max_bytes: int,
) -> tuple[tuple[str, ...], int]:
    accepted: list[str] = []
    omitted = 0
    for value in sorted(identifiers):
        try:
            valid = isinstance(value, str) and len(value.encode("utf-8")) <= max_bytes
        except UnicodeEncodeError:
            valid = False
        if not valid or len(accepted) >= limit:
            omitted += 1
        else:
            accepted.append(value)
    return tuple(accepted), omitted


def _capacity_observations(
    snapshot: ResourceSnapshot | None,
) -> tuple[CapacityObservation, ...] | None:
    if snapshot is None:
        return None
    capacities = [
        CapacityObservation(
            CapacityScope.GLOBAL,
            snapshot.global_capacity.limit,
            snapshot.global_capacity.allocated,
            snapshot.global_capacity.remaining,
        )
    ]
    capacities.extend(
        CapacityObservation(
            CapacityScope.PROVIDER,
            capacity.limit,
            capacity.allocated,
            capacity.remaining,
            provider_id,
        )
        for provider_id, capacity in snapshot.providers
    )
    capacities.extend(
        CapacityObservation(
            CapacityScope.MODEL,
            capacity.limit,
            capacity.allocated,
            capacity.remaining,
            provider_id,
            model_id,
        )
        for provider_id, model_id, capacity in snapshot.models
    )
    if snapshot.allocation_id_history_capacity is not None:
        history = snapshot.allocation_id_history_capacity
        capacities.append(
            CapacityObservation(
                CapacityScope.ALLOCATION_HISTORY,
                history.limit,
                history.allocated,
                history.remaining,
            )
        )
    return tuple(capacities)
