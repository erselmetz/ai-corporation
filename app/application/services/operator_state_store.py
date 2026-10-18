"""SQLite persistence for bounded, local operator state (Task 184)."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json

from app.database.connection import get_connection

MAX_OPERATOR_STATE_BYTES = 2 * 1024 * 1024
NO_AUTOMATIC_CONVERSATION_EXPIRY = "9999-12-31T23:59:59+00:00"


def _encode(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_OPERATOR_STATE_BYTES:
        raise ValueError("Operator state exceeds the local storage limit")
    return encoded


class OperatorStateStore:
    """Store corporation-scoped configuration and owner-scoped records.

    Credentials, provider objects, live allocations and active request state are
    deliberately excluded. A database transaction is the migration/write
    rollback boundary; this service never creates an unencrypted sidecar backup.
    """

    def __init__(self, corporation_id: str):
        if not isinstance(corporation_id, str) or not corporation_id.strip():
            raise ValueError("Corporation identity is required")
        self._corporation_id = corporation_id

    def load_positions(self) -> tuple[dict, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT record_json FROM operator_positions WHERE corporation_id = ? ORDER BY rowid",
                (self._corporation_id,),
            ).fetchall()
        return tuple(json.loads(row[0]) for row in rows)

    def save_positions(self, records) -> None:
        records = tuple(records)
        _encode(records)
        rows = [(self._corporation_id, record["id"], _encode(record)) for record in records]
        with self._connection() as connection, connection:
            connection.execute(
                "DELETE FROM operator_positions WHERE corporation_id = ?",
                (self._corporation_id,),
            )
            connection.executemany(
                "INSERT INTO operator_positions(corporation_id, position_id, record_json) VALUES(?,?,?)",
                rows,
            )

    def load_resource_limits(self) -> dict | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT limits_json FROM operator_resource_limits WHERE corporation_id = ?",
                (self._corporation_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save_resource_limits(self, limits: dict) -> None:
        encoded = _encode(limits)
        with self._connection() as connection, connection:
            connection.execute(
                "INSERT INTO operator_resource_limits(corporation_id, limits_json, updated_at) "
                "VALUES(?,?,CURRENT_TIMESTAMP) ON CONFLICT(corporation_id) DO UPDATE SET "
                "limits_json=excluded.limits_json, updated_at=CURRENT_TIMESTAMP",
                (self._corporation_id, encoded),
            )

    def save_proposal(self, *, owner_id: str, proposal_id: str, conversation_id: str,
                      digest: str, fingerprint: str, summary: dict,
                      created_at: datetime, expires_at: datetime) -> None:
        row = (self._corporation_id, owner_id, proposal_id, conversation_id, digest,
               fingerprint, _encode(summary), created_at.astimezone(timezone.utc).isoformat(),
               expires_at.astimezone(timezone.utc).isoformat())
        with self._connection() as connection, connection:
            connection.execute(
                "DELETE FROM operator_task_proposals WHERE corporation_id=? AND expires_at<=?",
                (self._corporation_id, created_at.astimezone(timezone.utc).isoformat()),
            )
            connection.execute(
                "INSERT INTO operator_task_proposals(corporation_id,owner_id,proposal_id,conversation_id,"
                "digest,fingerprint,summary_json,created_at,expires_at,state) VALUES(?,?,?,?,?,?,?,?,?,'prepared')",
                row,
            )

    def prune_proposals(self, now: datetime) -> None:
        with self._connection() as connection, connection:
            connection.execute(
                "UPDATE operator_task_proposals SET state='expired' WHERE corporation_id=? "
                "AND state='prepared' AND expires_at<=?",
                (self._corporation_id, now.astimezone(timezone.utc).isoformat()),
            )
            connection.execute(
                "DELETE FROM operator_task_proposals WHERE corporation_id=? AND expires_at<=?",
                (self._corporation_id, now.astimezone(timezone.utc).isoformat()),
            )

    def invalidate_unfinished_proposals(self) -> None:
        """Make prepared proposals unusable across a process restart."""
        with self._connection() as connection, connection:
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                "UPDATE operator_task_proposals SET state='restart-invalidated' "
                "WHERE corporation_id=? AND state='prepared' AND expires_at>?",
                (self._corporation_id, now),
            )
            connection.execute(
                "DELETE FROM operator_task_proposals WHERE corporation_id=? AND expires_at<=?",
                (self._corporation_id, now),
            )

    def consume_proposal(self, proposal_id: str) -> None:
        with self._connection() as connection, connection:
            changed = connection.execute(
                "UPDATE operator_task_proposals SET state='consumed' WHERE corporation_id=? "
                "AND proposal_id=? AND state='prepared'",
                (self._corporation_id, proposal_id),
            ).rowcount
            if changed != 1:
                raise ValueError("Task proposal is no longer available")

    def expire_proposal(self, proposal_id: str) -> None:
        with self._connection() as connection, connection:
            connection.execute(
                "UPDATE operator_task_proposals SET state='expired' WHERE corporation_id=? "
                "AND proposal_id=? AND state='prepared'",
                (self._corporation_id, proposal_id),
            )

    def created_fingerprints(self) -> frozenset[str]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT DISTINCT fingerprint FROM operator_task_proposals WHERE corporation_id=? AND state='consumed'",
                (self._corporation_id,),
            ).fetchall()
        return frozenset(row[0] for row in rows)

    def list_proposals(self, owner_id: str, now: datetime | None = None) -> tuple[dict, ...]:
        if now is not None:
            self.prune_proposals(now)
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT proposal_id,conversation_id,digest,summary_json,created_at,expires_at,state "
                "FROM operator_task_proposals WHERE corporation_id=? AND owner_id=? ORDER BY created_at,proposal_id",
                (self._corporation_id, owner_id),
            ).fetchall()
        return tuple({**dict(row), "summary": json.loads(row["summary_json"])} for row in rows)

    def save_conversation(self, *, owner_id: str, conversation_id: str,
                          record: dict, created_at: datetime) -> None:
        encoded = _encode(record)
        created = created_at.astimezone(timezone.utc)
        with self._connection() as connection, connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM operator_conversations WHERE corporation_id=? AND owner_id=?",
                (self._corporation_id, owner_id),
            ).fetchone()[0]
            exists = connection.execute(
                "SELECT 1 FROM operator_conversations WHERE corporation_id=? AND conversation_id=?",
                (self._corporation_id, conversation_id),
            ).fetchone()
            if count >= 100 and exists is None:
                raise ValueError("Retained conversation limit reached; delete a conversation first")
            connection.execute(
                "INSERT INTO operator_conversations(corporation_id,owner_id,conversation_id,conversation_json,created_at,expires_at) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(corporation_id,conversation_id) DO UPDATE SET "
                "owner_id=excluded.owner_id,conversation_json=excluded.conversation_json",
                (self._corporation_id, owner_id, conversation_id, encoded, created.isoformat(),
                 NO_AUTOMATIC_CONVERSATION_EXPIRY),
            )

    def load_conversations(self, owner_id: str) -> tuple[dict, ...]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT conversation_json FROM operator_conversations WHERE corporation_id=? AND owner_id=? ORDER BY created_at,conversation_id",
                (self._corporation_id, owner_id),
            ).fetchall()
        if len(rows) > 100:
            raise RuntimeError("Stored Employee conversation limit is exceeded")
        return tuple(json.loads(row[0]) for row in rows)

    def delete_conversation(self, owner_id: str, conversation_id: str) -> None:
        with self._connection() as connection, connection:
            connection.execute(
                "DELETE FROM operator_conversations WHERE corporation_id=? AND owner_id=? AND conversation_id=?",
                (self._corporation_id, owner_id, conversation_id),
            )

    @staticmethod
    @contextmanager
    def _connection():
        connection = get_connection()
        try:
            # initialize_database is the single schema/migration entry point.
            # Runtime construction calls it before any application service is exposed.
            connection.execute("SELECT 1 FROM operator_positions LIMIT 0")
            yield connection
        except Exception:
            raise
        finally:
            connection.close()
