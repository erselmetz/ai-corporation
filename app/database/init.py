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
                project_id TEXT,
                assigned_agent TEXT,
                required_role TEXT,
                required_capability TEXT,
                status TEXT NOT NULL,
                result TEXT,
                error TEXT
            )
            """
        )

        task_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
        }
        if "project_id" not in task_columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN project_id TEXT")
        if "required_role" not in task_columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN required_role TEXT")
        if "required_capability" not in task_columns:
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN required_capability TEXT"
            )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS task_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                event TEXT NOT NULL,
                message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(agent_id, key)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_id, key)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_memory (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                source_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                retention_opt_in INTEGER NOT NULL CHECK(retention_opt_in = 1)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_knowledge (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                source_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                retention_opt_in INTEGER NOT NULL CHECK(retention_opt_in = 1)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS corporation_knowledge (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                source_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                retention_opt_in INTEGER NOT NULL CHECK(retention_opt_in = 1)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS corporation_knowledge_provenance (
                knowledge_id TEXT PRIMARY KEY,
                source_scope TEXT NOT NULL,
                source_scope_id TEXT NOT NULL,
                source_reference TEXT NOT NULL,
                source_created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS corporation_knowledge_readers (
                knowledge_id TEXT NOT NULL,
                reader_id TEXT NOT NULL,
                PRIMARY KEY (knowledge_id, reader_id)
            )
            """
        )

        connection.commit()

    finally:
        connection.close()