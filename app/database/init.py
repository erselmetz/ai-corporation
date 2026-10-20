from .connection import get_connection

CURRENT_CONFIGURATION_VERSION = 4


def initialize_database() -> None:
    connection = get_connection()

    try:
        configuration_version = connection.execute("PRAGMA user_version").fetchone()[0]
        if configuration_version > CURRENT_CONFIGURATION_VERSION:
            raise RuntimeError("Application configuration is newer than this release supports")
        connection.execute("BEGIN IMMEDIATE")
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
                error TEXT,
                failure_category TEXT
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
        if "failure_category" not in task_columns:
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN failure_category TEXT"
            )
        connection.execute(
            """
            UPDATE tasks
            SET failure_category = 'unknown'
            WHERE status = 'failed' AND failure_category IS NULL
            """
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
            CREATE TABLE IF NOT EXISTS owner_knowledge (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                source_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                retention_opt_in INTEGER NOT NULL CHECK(retention_opt_in = 1),
                CHECK(owner_id = scope_id)
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

        connection.execute("""
            CREATE TABLE IF NOT EXISTS execution_queue (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                corporation_id TEXT NOT NULL,
                id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('queued','claimed','completed','failed','abandoned')),
                worker_id TEXT,
                claim_id TEXT,
                resolution TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(corporation_id, id),
                UNIQUE(corporation_id, task_id),
                UNIQUE(corporation_id, claim_id)
            )
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS execution_queue_fifo ON execution_queue(corporation_id, state, sequence)")

        connection.execute("""
            CREATE TABLE IF NOT EXISTS local_first_run (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0, 1)),
                skipped INTEGER NOT NULL DEFAULT 0 CHECK(skipped IN (0, 1)),
                provider_type TEXT NOT NULL DEFAULT 'none' CHECK(provider_type IN ('none', 'ollama', 'gemini')),
                provider_id TEXT,
                model_id TEXT,
                ollama_base_url TEXT,
                gemini_models TEXT,
                gemini_key_persisted INTEGER NOT NULL DEFAULT 0 CHECK(gemini_key_persisted IN (0, 1)),
                global_slots INTEGER NOT NULL DEFAULT 1 CHECK(global_slots BETWEEN 1 AND 10000),
                provider_slots INTEGER NOT NULL DEFAULT 1 CHECK(provider_slots BETWEEN 1 AND 10000),
                model_slots INTEGER NOT NULL DEFAULT 1 CHECK(model_slots BETWEEN 1 AND 10000),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Task 184: additive operator-state records. Each domain stores its own
        # versioned JSON payload so existing in-memory/domain validation remains
        # authoritative. The enclosing SQLite transaction makes schema upgrade
        # rollback atomic; no secrets or active resource allocations are stored.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS operator_positions (
                corporation_id TEXT NOT NULL,
                position_id TEXT NOT NULL,
                record_json TEXT NOT NULL CHECK(json_valid(record_json)),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (corporation_id, position_id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS operator_resource_limits (
                corporation_id TEXT PRIMARY KEY,
                limits_json TEXT NOT NULL CHECK(json_valid(limits_json)),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS operator_agent_profiles (
                corporation_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                record_json TEXT NOT NULL CHECK(json_valid(record_json)),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (corporation_id, agent_id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS operator_task_proposals (
                corporation_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                proposal_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                digest TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                summary_json TEXT NOT NULL CHECK(json_valid(summary_json)),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('prepared', 'consumed', 'expired', 'restart-invalidated')),
                PRIMARY KEY (corporation_id, proposal_id)
            )
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS operator_proposals_owner_expiry ON operator_task_proposals(corporation_id, owner_id, expires_at)")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS operator_conversations (
                corporation_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                conversation_json TEXT NOT NULL CHECK(json_valid(conversation_json)),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                PRIMARY KEY (corporation_id, conversation_id)
            )
        """)
        connection.execute("CREATE INDEX IF NOT EXISTS operator_conversations_owner_expiry ON operator_conversations(corporation_id, owner_id, expires_at)")

        # Publish the migrated version only after every additive DDL/DML step succeeds.
        connection.execute(f"PRAGMA user_version = {CURRENT_CONFIGURATION_VERSION}")
        connection.commit()

    finally:
        connection.close()
