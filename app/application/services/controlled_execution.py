"""Explicit local controlled execution using existing routing and slot budgets."""
from threading import RLock
from uuid import uuid4

from app.orchestrator.task import TaskStatus
from app.resources.manager import identifier


class ControlledExecution:
    def __init__(self, orchestrator, resources):
        self._orchestrator = orchestrator
        self._resources = resources
        self._active = set()
        self._lock = RLock()

    def execute(
        self,
        task_id,
        *,
        expected_agent_id=None,
        expected_provider=None,
        expected_model=None,
    ):
        identifier(task_id)
        allocation_id = None
        with self._lock:
            if task_id in self._active:
                raise ValueError("Task already has an active controlled execution")
            task = self._orchestrator.tasks.get(task_id)
            if task.status is not TaskStatus.PENDING:
                raise ValueError("Controlled execution requires a pending Task")
            route = self._orchestrator.execute_task(task, dry_run=True)
            if (
                expected_agent_id is not None
                and route.selected_agent.id != expected_agent_id
            ) or (
                expected_provider is not None
                and route.provider != expected_provider
            ) or (
                expected_model is not None
                and route.model != expected_model
            ):
                raise ValueError("Task route changed after dispatch review")
            allocation_id = uuid4().hex
            self._resources.allocate(allocation_id, provider_id=route.provider, model_id=route.model)
            self._active.add(task_id)
        try:
            return self._orchestrator.execute_task(task, agent_id=route.selected_agent.id)
        finally:
            with self._lock:
                try:
                    self._resources.release(allocation_id)
                finally:
                    self._active.remove(task_id)
