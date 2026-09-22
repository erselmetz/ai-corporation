from app.database import get_connection


class ProjectMemoryStore:
    def remember(
        self,
        project_id: str,
        key: str,
        value: str,
    ) -> None:
        connection = get_connection()

        try:
            connection.execute(
                """
                INSERT INTO project_memory (
                    project_id,
                    key,
                    value
                )
                VALUES (?, ?, ?)
                ON CONFLICT(project_id, key)
                DO UPDATE SET
                    value = excluded.value
                """,
                (
                    project_id,
                    key,
                    value,
                ),
            )

            connection.commit()

        finally:
            connection.close()

    def recall(
        self,
        project_id: str,
        key: str,
    ) -> str | None:
        connection = get_connection()

        try:
            row = connection.execute(
                """
                SELECT value
                FROM project_memory
                WHERE project_id = ?
                  AND key = ?
                """,
                (
                    project_id,
                    key,
                ),
            ).fetchone()

            if row is None:
                return None

            return row["value"]

        finally:
            connection.close()

    def all(
        self,
        project_id: str,
    ) -> list[dict]:
        connection = get_connection()

        try:
            rows = connection.execute(
                """
                SELECT
                    id,
                    project_id,
                    key,
                    value,
                    created_at
                FROM project_memory
                WHERE project_id = ?
                ORDER BY id ASC
                """,
                (project_id,),
            ).fetchall()

            return [dict(row) for row in rows]

        finally:
            connection.close()

    def forget(
        self,
        project_id: str,
        key: str,
    ) -> None:
        connection = get_connection()

        try:
            connection.execute(
                """
                DELETE FROM project_memory
                WHERE project_id = ?
                  AND key = ?
                """,
                (
                    project_id,
                    key,
                ),
            )

            connection.commit()

        finally:
            connection.close()