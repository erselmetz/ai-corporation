from app.database import get_connection

from .task import Task, TaskStatus


class TaskRegistry:
    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self.load_from_database()

    def register(self, task: Task) -> None:
        if task.id in self._tasks:
            raise ValueError(f"Task already registered: {task.id}")

        self._tasks[task.id] = task
        self.save_to_database(task)

    def get(self, task_id: str) -> Task:
        try:
            return self._tasks[task_id]
        except KeyError:
            raise ValueError(f"Task not found: {task_id}")

    def all(self) -> list[Task]:
        return list(self._tasks.values())

    def exists(self, task_id: str) -> bool:
        return task_id in self._tasks

    def save_to_database(self, task: Task) -> None:
        connection = get_connection()

        try:
            connection.execute(
                """
                INSERT INTO tasks (
                    id,
                    title,
                    description,
                    assigned_agent,
                    status,
                    result,
                    error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.title,
                    task.description,
                    task.assigned_agent,
                    task.status.value,
                    task.result,
                    task.error,
                ),
            )

            connection.commit()

        finally:
            connection.close()

    def load_from_database(self) -> None:
        connection = get_connection()

        try:
            rows = connection.execute(
                """
                SELECT
                    id,
                    title,
                    description,
                    assigned_agent,
                    status,
                    result,
                    error
                FROM tasks
                """
            ).fetchall()

            for row in rows:
                task = Task(
                    id=row["id"],
                    title=row["title"],
                    description=row["description"],
                    assigned_agent=row["assigned_agent"],
                    status=TaskStatus(row["status"]),
                    result=row["result"],
                    error=row["error"],
                )

                self._tasks[task.id] = task

        finally:
            connection.close()
    
    def update(self, task: Task) -> None:
        self._tasks[task.id] = task

        connection = get_connection()

        try:
            connection.execute(
                """
                UPDATE tasks
                SET
                    title = ?,
                    description = ?,
                    assigned_agent = ?,
                    status = ?,
                    result = ?,
                    error = ?
                WHERE id = ?
                """,
                (
                    task.title,
                    task.description,
                    task.assigned_agent,
                    task.status.value,
                    task.result,
                    task.error,
                    task.id,
                ),
            )

            connection.commit()

        finally:
            connection.close()