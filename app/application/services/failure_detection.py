"""Bounded classification of persisted failed Tasks without raw error details."""

from dataclasses import dataclass
from datetime import datetime, timezone

from app.orchestrator.task import TaskFailureCategory, TaskStatus
from app.orchestrator.task_registry import TaskRegistry


@dataclass(frozen=True, slots=True)
class DetectedFailure:
    task_id: str
    category: TaskFailureCategory


@dataclass(frozen=True, slots=True)
class FailureDetectionReport:
    observed_at: datetime
    total_failures: int
    failures: tuple[DetectedFailure, ...]
    omitted_count: int


class FailureDetectionService:
    MAX_FAILURES = 100
    MAX_TASK_ID_BYTES = 256

    def __init__(self, *, tasks: TaskRegistry):
        self._tasks = tasks

    def report(self) -> FailureDetectionReport:
        failed_tasks: list[tuple[str, TaskFailureCategory]] = []
        for task in self._tasks.all():
            if task.status is not TaskStatus.FAILED:
                continue
            category = task.failure_category
            if category is None:
                category = TaskFailureCategory.UNKNOWN
            elif not isinstance(category, TaskFailureCategory):
                raise TypeError("Failed Task has an invalid failure category")
            failed_tasks.append((task.id, category))
        failed_tasks.sort(key=lambda item: item[0])

        failures: list[DetectedFailure] = []
        omitted_count = 0
        for task_id, category in failed_tasks:
            try:
                valid_id = isinstance(task_id, str) and (
                    len(task_id.encode("utf-8")) <= self.MAX_TASK_ID_BYTES
                )
            except UnicodeEncodeError:
                valid_id = False
            if not valid_id or len(failures) >= self.MAX_FAILURES:
                omitted_count += 1
                continue
            failures.append(DetectedFailure(task_id, category))
        return FailureDetectionReport(
            observed_at=datetime.now(timezone.utc),
            total_failures=len(failed_tasks),
            failures=tuple(failures),
            omitted_count=omitted_count,
        )
