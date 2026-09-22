from .connection import get_connection


def initialize_database() -> None:
    connection = get_connection()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                assigned_agent TEXT,
                status TEXT NOT NULL,
                result TEXT,
                error TEXT
            )
            """
        )

        connection.commit()

    finally:
        connection.close()