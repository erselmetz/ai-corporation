"""Append-only, explicitly retained conversation notes in existing SQLite."""
from datetime import datetime
import sqlite3

from app.database import get_connection
from .models import MemoryRecord, MemoryScope, MemoryType, require_memory_access, _identifier, _time


class ConversationMemoryStore:
    @staticmethod
    def _request(memory_id: str, owner_id: str, conversation_id: str):
        for label, value in (("id", memory_id), ("owner_id", owner_id), ("scope_id", conversation_id)):
            _identifier(value, label)

    @staticmethod
    def _record(row) -> MemoryRecord:
        if row["retention_opt_in"] != 1:
            raise ValueError("Stored memory has invalid retention consent")
        return MemoryRecord(row["id"], row["owner_id"], MemoryScope.CONVERSATION,
                            row["scope_id"], MemoryType(row["type"]), row["content"],
                            row["source_id"], datetime.fromisoformat(row["created_at"]),
                            datetime.fromisoformat(row["expires_at"]), True)

    def retain(self, record: MemoryRecord, *, now: datetime) -> None:
        if not isinstance(record, MemoryRecord):
            raise TypeError("Expected a MemoryRecord")
        if record.scope is not MemoryScope.CONVERSATION:
            raise ValueError("Conversation memory requires conversation scope")
        require_memory_access(record, owner_id=record.owner_id, scope=record.scope,
                              scope_id=record.scope_id, now=now)
        connection = get_connection()
        try:
            with connection:
                connection.execute(
                    "INSERT INTO conversation_memory "
                    "(id, owner_id, scope_id, type, content, source_id, created_at, expires_at, retention_opt_in) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (record.id, record.owner_id, record.scope_id, record.type.value,
                     record.content, record.source_id, record.created_at.isoformat(),
                     record.expires_at.isoformat(), 1))
        except sqlite3.IntegrityError:
            raise ValueError("Memory id already exists or record violates storage constraints") from None
        finally:
            connection.close()

    def retrieve(self, memory_id: str, *, owner_id: str, conversation_id: str,
                 now: datetime) -> MemoryRecord:
        self._request(memory_id, owner_id, conversation_id)
        _time(now)
        connection = get_connection()
        try:
            row = connection.execute(
                "SELECT * FROM conversation_memory WHERE id = ? AND owner_id = ? AND scope_id = ?",
                (memory_id, owner_id, conversation_id)).fetchone()
            if row is None:
                raise KeyError("Memory not found in requested owner/conversation scope")
            record = self._record(row)
            require_memory_access(record, owner_id=owner_id, scope=MemoryScope.CONVERSATION,
                                  scope_id=conversation_id, now=now)
            return record
        finally:
            connection.close()

    def forget(self, memory_id: str, *, owner_id: str, conversation_id: str) -> None:
        self._request(memory_id, owner_id, conversation_id)
        connection = get_connection()
        try:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM conversation_memory WHERE id = ? AND owner_id = ? AND scope_id = ?",
                    (memory_id, owner_id, conversation_id))
                if cursor.rowcount != 1:
                    raise KeyError("Memory not found in requested owner/conversation scope")
        finally:
            connection.close()

    def purge_expired(self, *, owner_id: str, conversation_id: str, now: datetime) -> int:
        _identifier(owner_id, "owner_id")
        _identifier(conversation_id, "scope_id")
        _time(now)
        connection = get_connection()
        try:
            with connection:
                rows = connection.execute(
                    "SELECT * FROM conversation_memory WHERE owner_id = ? AND scope_id = ?",
                    (owner_id, conversation_id)).fetchall()
                # Validate all rows before deleting; invalid stored data is never silently discarded.
                records = [self._record(row) for row in rows]
                expired = [record.id for record in records if record.expires_at <= now]
                connection.executemany(
                    "DELETE FROM conversation_memory WHERE id = ? AND owner_id = ? AND scope_id = ?",
                    [(memory_id, owner_id, conversation_id) for memory_id in expired])
                return len(expired)
        finally:
            connection.close()
