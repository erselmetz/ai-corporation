"""Review-only planning; no execution, scheduling, or persistence side effects."""
from dataclasses import dataclass
from datetime import datetime

from app.memory import MemoryScope
from app.memory.models import _identifier, _time
from app.orchestrator.task import TaskStatus
from .context_retrieval import ContextRetrievalResult


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 1024:
        raise ValueError("Outcome criteria require nonempty text of at most 1024 bytes")


@dataclass(frozen=True)
class OutcomeCriteria:
    expected_outcome: str
    verification_method: str
    expected_evidence: str

    def __post_init__(self):
        for value in (self.expected_outcome, self.verification_method, self.expected_evidence):
            _text(value)


@dataclass(frozen=True)
class PlanningRequest:
    task_id: str
    dependencies: tuple[str, ...]
    outcomes: tuple[OutcomeCriteria, ...]

    def __post_init__(self):
        _identifier(self.task_id, "task_id")
        if not isinstance(self.dependencies, tuple) or len(self.dependencies) > 49:
            raise ValueError("Dependencies must be an immutable tuple of at most 49 IDs")
        for dependency in self.dependencies:
            _identifier(dependency, "dependency")
        if len(set(self.dependencies)) != len(self.dependencies) or self.task_id in self.dependencies:
            raise ValueError("Duplicate or self dependencies are invalid")
        if not isinstance(self.outcomes, tuple) or not 1 <= len(self.outcomes) <= 10:
            raise ValueError("Each Task requires 1 to 10 explicit outcome criteria")
        if not all(isinstance(item, OutcomeCriteria) for item in self.outcomes):
            raise TypeError("Expected OutcomeCriteria")


@dataclass(frozen=True)
class PlannedTask:
    task_id: str
    title: str
    status: TaskStatus
    dependencies: tuple[str, ...]
    unmet_dependencies: tuple[str, ...]
    outcomes: tuple[OutcomeCriteria, ...]
    outcomes_verified: bool = False


@dataclass(frozen=True)
class TaskPlan:
    project_id: str
    created_at: datetime
    tasks: tuple[PlannedTask, ...]
    context: ContextRetrievalResult | None


class TaskPlanningService:
    """Trusted callers authorize selected Tasks and bind the supplied actor.

    Dependency order and status are review snapshots; neither enforces execution
    nor proves outcome criteria. Context remains untrusted, expiring knowledge.
    """
    def __init__(self, orchestrator, context_retrieval):
        self._orchestrator = orchestrator
        self._context_retrieval = context_retrieval

    def build(self, project_id: str, requests: tuple[PlanningRequest, ...], *,
              actor_id: str, now: datetime, context_query: str | None = None,
              context_scope: MemoryScope | None = None, context_scope_id: str | None = None):
        _identifier(project_id, "project_id")
        _identifier(actor_id, "actor_id")
        _time(now)
        if not isinstance(requests, tuple) or not 1 <= len(requests) <= 50:
            raise ValueError("A plan requires 1 to 50 explicit Task requests")
        if not all(isinstance(item, PlanningRequest) for item in requests):
            raise TypeError("Expected PlanningRequest")
        by_id = {item.task_id: item for item in requests}
        if len(by_id) != len(requests):
            raise ValueError("Duplicate Task requests are invalid")
        self._orchestrator.projects.get(project_id)
        selected = {}
        for identifier, request in by_id.items():
            task = self._orchestrator.tasks.get(identifier)
            if task.project_id != project_id:
                raise ValueError("Selected Tasks must belong to the exact Project")
            if not isinstance(task.status, TaskStatus):
                raise ValueError("Invalid Task lifecycle status")
            if any(dependency not in by_id for dependency in request.dependencies):
                raise ValueError("Every dependency must be explicitly selected in this plan")
            selected[identifier] = task
        # Bounded deterministic topological sort, with no registry mutation.
        ordered = []
        remaining = set(by_id)
        while remaining:
            ready = sorted(identifier for identifier in remaining
                           if not (set(by_id[identifier].dependencies) & remaining))
            if not ready:
                raise ValueError("Task dependency cycle detected")
            ordered.extend(ready)
            remaining.difference_update(ready)
        supplied = (context_query is not None, context_scope is not None, context_scope_id is not None)
        if any(supplied) and not all(supplied):
            raise ValueError("Context requires explicit query, scope, and resource ID")
        if context_scope is MemoryScope.PROJECT and context_scope_id != project_id:
            raise ValueError("Project context must match the planned Project")
        context = None
        if all(supplied):
            context = self._context_retrieval.retrieve(context_query, actor_id=actor_id,
                                                       scope=context_scope, scope_id=context_scope_id, now=now)
        tasks = tuple(PlannedTask(identifier, selected[identifier].title, selected[identifier].status,
                                  tuple(sorted(by_id[identifier].dependencies)),
                                  tuple(sorted(dependency for dependency in by_id[identifier].dependencies
                                               if selected[dependency].status is not TaskStatus.COMPLETED)),
                                  by_id[identifier].outcomes) for identifier in ordered)
        return TaskPlan(project_id, now, tasks, context)
