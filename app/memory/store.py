from app.database import get_connection


class MemoryStore:
    def remember(
        self,
        agent_id: str,
        key: str,
        value: str,
    ) -> None:
        connection = get_connection()

        try:
            connection.execute(
                """
                INSERT INTO agent_memory (
                    agent_id,
                    key,
                    value
                )
                VALUES (?, ?, ?)
                ON CONFLICT(agent_id, key)
                DO UPDATE SET
                    value = excluded.value
                """,
                (
                    agent_id,
                    key,
                    value,
                ),
            )

            connection.commit()

        finally:
            connection.close()

    def recall(
        self,
        agent_id: str,
        key: str,
    ) -> str | None:
        connection = get_connection()

        try:
            row = connection.execute(
                """
                SELECT value
                FROM agent_memory
                WHERE agent_id = ?
                  AND key = ?
                """,
                (
                    agent_id,
                    key,
                ),
            ).fetchone()

            if row is None:
                return None

            return row["value"]

        finally:
            connection.close()

    def forget(
        self,
        agent_id: str,
        key: str,
    ) -> None:
        connection = get_connection()

        try:
            connection.execute(
                """
                DELETE FROM agent_memory
                WHERE agent_id = ?
                  AND key = ?
                """,
                (
                    agent_id,
                    key,
                ),
            )

            connection.commit()

        finally:
            connection.close()