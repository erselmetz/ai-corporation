from .task import Task


class TaskRegistry:
    def __init__(self):
        self._tasks: dict[str, Task] = {}

    def register(self, task: Task) -> None:
        if task.id in self._tasks:
            raise ValueError(f"Task already registered: {task.id}")

        self._tasks[task.id] = task

    def get(self, task_id: str) -> Task:
        try:
            return self._tasks[task_id]
        except KeyError:
            raise ValueError(f"Task not found: {task_id}")

    def all(self) -> list[Task]:
        return list(self._tasks.values())

    def exists(self, task_id: str) -> bool:
        return task_id in self._tasks