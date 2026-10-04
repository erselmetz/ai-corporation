"""Owner-confirmed, single-Task dispatch through the durable queue."""

from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from app.orchestrator.execution_queue import QueueState
from app.orchestrator.router import RoutingError


class TaskDispatchNotFound(ValueError):
    pass


class TaskDispatchConflict(ValueError):
    pass


class TaskDispatchUnavailable(RuntimeError):
    pass


class TaskDispatchService:
    MAX_TITLE_BYTES = 1024
    MAX_DESCRIPTION_BYTES = 8192
    MAX_RESOLUTION_BYTES = 1024

    def __init__(self, application, *, clock=lambda: datetime.now(timezone.utc)):
        self._application = application
        self._clock = clock
        self._lock = RLock()

    def dispatch(self, owner_id, task_id, *, confirmed):
        if confirmed is not True:
            raise TaskDispatchConflict("Explicit owner confirmation is required")
        _text(owner_id, "owner_id", 256)
        _text(task_id, "task_id", 256)

        with self._lock:
            manager = self._resource_manager()
            queue = self._application.execution_queue()
            active = queue.list_active()
            if any(entry.state is QueueState.CLAIMED for entry in active):
                raise TaskDispatchConflict(
                    "A claimed action requires explicit human resolution before dispatch"
                )
            queued = tuple(
                entry for entry in active if entry.state is QueueState.QUEUED
            )
            entry = next((item for item in queued if item.task_id == task_id), None)
            if queued and (entry is None or queued[0].id != entry.id):
                raise TaskDispatchConflict(
                    "Dispatch is limited to the FIFO head; resolve or dispatch it first"
                )

            plan = self._preflight(task_id, manager)
            if entry is None:
                try:
                    entry = queue.enqueue(uuid4().hex, task_id, now=self._now())
                except ValueError as error:
                    raise TaskDispatchConflict(str(error)) from None

            try:
                claim = queue.claim_next(
                    worker_id=owner_id,
                    claim_id=uuid4().hex,
                    now=self._now(),
                    expected_entry_id=entry.id,
                )
            except ValueError as error:
                raise TaskDispatchConflict(str(error)) from None
            if claim is None:
                raise TaskDispatchConflict(
                    "The approved Task is no longer the FIFO head; inspect the queue"
                )

            try:
                result = self._application.execute_controlled_task(
                    task_id,
                    expected_agent_id=plan.selected_agent_id,
                    expected_provider=plan.provider,
                    expected_model=plan.model,
                )
            except ValueError:
                raise TaskDispatchConflict(
                    "Dispatch stopped after claim; inspect and explicitly resolve the queue entry"
                ) from None
            try:
                completed = queue.acknowledge(
                    claim.id,
                    worker_id=owner_id,
                    claim_id=claim.claim_id,
                    now=self._now(),
                )
            except ValueError:
                raise TaskDispatchConflict(
                    "Task outcome was not acknowledged; inspect and explicitly resolve the queue entry"
                ) from None
            return self._entry_snapshot(completed, result)

    def list_queue(self):
        entries = self._application.execution_queue().list(limit=100)
        return {
            "items": [self._entry_snapshot(entry) for entry in entries],
            "history_limit_reached": len(entries) == 100,
        }

    def resolve(self, owner_id, entry_id, *, resolution, confirmed):
        if confirmed is not True:
            raise TaskDispatchConflict("Explicit human confirmation is required")
        _text(owner_id, "owner_id", 256)
        _text(entry_id, "entry_id", 256)
        _text(resolution, "resolution", self.MAX_RESOLUTION_BYTES)
        if any(ord(character) < 32 for character in resolution):
            raise ValueError("Resolution must not contain control characters")
        recorded_resolution = f"Resolved by {owner_id}: {resolution}"
        if len(recorded_resolution.encode("utf-8")) > self.MAX_RESOLUTION_BYTES:
            raise ValueError("Resolution exceeds the byte limit")
        with self._lock:
            try:
                entry = self._application.execution_queue().abandon(
                    entry_id,
                    resolution=recorded_resolution,
                    confirm=True,
                    now=self._now(),
                )
            except KeyError:
                raise TaskDispatchNotFound("Queue entry not found") from None
            except ValueError as error:
                raise TaskDispatchConflict(str(error)) from None
            return self._entry_snapshot(entry)

    def _preflight(self, task_id, manager):
        try:
            task = self._application.get_task(task_id)
        except ValueError:
            raise TaskDispatchNotFound("Task not found") from None
        if task.status != "pending":
            raise TaskDispatchConflict("Only pending Tasks can be dispatched")
        try:
            title_bytes = len(task.title.encode("utf-8"))
            description_bytes = len(task.description.encode("utf-8"))
        except UnicodeEncodeError:
            raise TaskDispatchConflict("Task text is not valid UTF-8") from None
        if (
            title_bytes > self.MAX_TITLE_BYTES
            or description_bytes > self.MAX_DESCRIPTION_BYTES
        ):
            raise TaskDispatchConflict("Task input exceeds the dispatch byte limits")
        if task.project_id is not None:
            try:
                self._application.get_project(task.project_id)
            except ValueError:
                raise TaskDispatchConflict(
                    "Task Project is unavailable; correct its association before dispatch"
                ) from None
        try:
            plan = self._application.dry_run_task(task_id)
        except RoutingError:
            raise TaskDispatchConflict(
                "Task has no valid current Agent route"
            ) from None
        if (
            plan.provider != "ollama"
            or not self._application.is_loopback_ollama_provider(plan.provider)
        ):
            raise TaskDispatchConflict(
                "Only a configured loopback Ollama worker can receive dispatched Tasks"
            )
        snapshot = manager.snapshot()
        provider_capacity = dict(snapshot.providers).get(plan.provider)
        model_capacity = next(
            (
                capacity
                for provider_id, model_id, capacity in snapshot.models
                if (provider_id, model_id) == (plan.provider, plan.model)
            ),
            None,
        )
        if provider_capacity is None or model_capacity is None:
            raise TaskDispatchUnavailable(
                "Explicit provider and model slot budgets are required"
            )
        if (
            snapshot.global_capacity.remaining <= 0
            or provider_capacity.remaining <= 0
            or model_capacity.remaining <= 0
        ):
            raise TaskDispatchConflict("Configured worker slot capacity is exhausted")
        return plan

    def _resource_manager(self):
        try:
            return self._application.resource_manager()
        except RuntimeError:
            raise TaskDispatchUnavailable(
                "Controlled dispatch is unavailable until slot budgets are configured"
            ) from None

    def _entry_snapshot(self, entry, task=None):
        if task is None:
            try:
                task = self._application.get_task(entry.task_id)
            except ValueError:
                raise TaskDispatchConflict(
                    "Queue entry references an unavailable Task"
                ) from None
        return {
            "sequence": entry.sequence,
            "id": entry.id,
            "task_id": entry.task_id,
            "state": entry.state.value,
            "worker_id": entry.worker_id,
            "claim_id": entry.claim_id,
            "resolution": entry.resolution,
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat(),
            "task": {
                "title": task.title,
                "status": task.status,
                "result_recorded": task.result is not None,
                "error_recorded": task.error is not None,
            },
        }

    def _now(self):
        now = self._clock()
        if (
            not isinstance(now, datetime)
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise ValueError("Dispatch clock must return a timezone-aware datetime")
        return now


def _text(value, label, maximum):
    try:
        valid = (
            isinstance(value, str)
            and bool(value.strip())
            and len(value.encode("utf-8")) <= maximum
        )
    except UnicodeEncodeError:
        valid = False
    if not valid:
        raise ValueError(f"{label} must be nonempty text of at most {maximum} UTF-8 bytes")
