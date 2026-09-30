from app.database import get_connection


class TaskLogger:
    def log(
        self,
        task_id: str,
        event: str,
        message: str | None = None,
    ) -> None:
        connection = get_connection()

        try:
            connection.execute(
                """
                INSERT INTO task_logs (
                    task_id,
                    event,
                    message
                )
                VALUES (?, ?, ?)
                """,
                (
                    task_id,
                    event,
                    message,
                ),
            )

            connection.commit()

        finally:
            connection.close()

    def list_activity(
        self,
        limit: int = 100,
        task_id: str | None = None,
    ) -> list[dict]:
        """Return the newest bounded activity records, optionally for one task."""
        if not 1 <= limit <= 100:
            raise ValueError("Activity limit must be between 1 and 100")

        connection = get_connection()

        try:
            if task_id is None:
                rows = connection.execute(
                    """
                    SELECT
                        id,
                        task_id,
                        event,
                        created_at
                    FROM task_logs
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT
                        id,
                        task_id,
                        event,
                        created_at
                    FROM task_logs
                    WHERE task_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (task_id, limit),
                ).fetchall()

            return [dict(row) for row in rows]

        finally:
            connection.close()

    def get_task_logs(self, task_id: str) -> list[dict]:
        connection = get_connection()

        try:
            rows = connection.execute(
                """
                SELECT
                    id,
                    task_id,
                    event,
                    message,
                    created_at
                FROM task_logs
                WHERE task_id = ?
                ORDER BY id ASC
                """,
                (task_id,),
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            connection.close()