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