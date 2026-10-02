"""Shared controlled storage mechanics for explicitly scoped retained notes."""
from datetime import datetime
import sqlite3

from app.database import get_connection
from .models import MemoryRecord, MemoryScope, MemoryType, require_memory_access, _identifier, _time


class _ScopedMemoryStore:
    _scope = MemoryScope.CONVERSATION

    @property
    def _table(self):
        return {MemoryScope.CONVERSATION: "conversation_memory", MemoryScope.PROJECT: "project_knowledge", MemoryScope.CORPORATION: "corporation_knowledge"}[self._scope]

    @staticmethod
    def _request(memory_id: str, owner_id: str, scope_id: str):
        for label, value in (("id", memory_id), ("owner_id", owner_id), ("scope_id", scope_id)):
            _identifier(value, label)

    def _record(self, row) -> MemoryRecord:
        if row["retention_opt_in"] != 1:
            raise ValueError("Stored memory has invalid retention consent")
        return MemoryRecord(row["id"], row["owner_id"], self._scope,
                            row["scope_id"], MemoryType(row["type"]), row["content"],
                            row["source_id"], datetime.fromisoformat(row["created_at"]),
                            datetime.fromisoformat(row["expires_at"]), True)

    def _insert(self, connection, record: MemoryRecord) -> None:
        connection.execute(
            f"INSERT INTO {self._table} "
            "(id, owner_id, scope_id, type, content, source_id, created_at, expires_at, retention_opt_in) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (record.id, record.owner_id, record.scope_id, record.type.value,
             record.content, record.source_id, record.created_at.isoformat(),
             record.expires_at.isoformat(), 1))

    def retain(self, record: MemoryRecord, *, now: datetime) -> None:
        if not isinstance(record, MemoryRecord):
            raise TypeError("Expected a MemoryRecord")
        if record.scope is not self._scope:
            raise ValueError("Memory scope does not match store")
        require_memory_access(record, owner_id=record.owner_id, scope=record.scope,
                              scope_id=record.scope_id, now=now)
        connection = get_connection()
        try:
            with connection:
                self._insert(connection, record)
        except sqlite3.IntegrityError:
            raise ValueError("Memory id already exists or record violates storage constraints") from None
        finally:
            connection.close()

    def _retrieve(self, memory_id: str, *, owner_id: str, scope_id: str,
                 now: datetime) -> MemoryRecord:
        self._request(memory_id, owner_id, scope_id)
        _time(now)
        connection = get_connection()
        try:
            row = connection.execute(
                f"SELECT * FROM {self._table} WHERE id = ? AND owner_id = ? AND scope_id = ?",
                (memory_id, owner_id, scope_id)).fetchone()
            if row is None:
                raise KeyError(f"Memory not found in requested owner/{self._scope.value} scope")
            record = self._record(row)
            require_memory_access(record, owner_id=owner_id, scope=self._scope,
                                  scope_id=scope_id, now=now)
            return record
        finally:
            connection.close()

    def _forget(self, memory_id: str, *, owner_id: str, scope_id: str) -> None:
        self._request(memory_id, owner_id, scope_id)
        connection = get_connection()
        try:
            with connection:
                cursor = connection.execute(
                    f"DELETE FROM {self._table} WHERE id = ? AND owner_id = ? AND scope_id = ?",
                    (memory_id, owner_id, scope_id))
                if cursor.rowcount != 1:
                    raise KeyError(f"Memory not found in requested owner/{self._scope.value} scope")
        finally:
            connection.close()

    def _purge_expired(self, *, owner_id: str, scope_id: str, now: datetime) -> int:
        _identifier(owner_id, "owner_id")
        _identifier(scope_id, "scope_id")
        _time(now)
        connection = get_connection()
        try:
            with connection:
                rows = connection.execute(
                    f"SELECT * FROM {self._table} WHERE owner_id = ? AND scope_id = ?",
                    (owner_id, scope_id)).fetchall()
                # Validate all rows before deleting; invalid stored data is never silently discarded.
                records = [self._record(row) for row in rows]
                expired = [record.id for record in records if record.expires_at <= now]
                connection.executemany(
                    f"DELETE FROM {self._table} WHERE id = ? AND owner_id = ? AND scope_id = ?",
                    [(memory_id, owner_id, scope_id) for memory_id in expired])
                return len(expired)
        finally:
            connection.close()


class ConversationMemoryStore(_ScopedMemoryStore):
    def retrieve(self, memory_id: str, *, owner_id: str, conversation_id: str, now: datetime):
        return self._retrieve(memory_id, owner_id=owner_id, scope_id=conversation_id, now=now)

    def forget(self, memory_id: str, *, owner_id: str, conversation_id: str):
        return self._forget(memory_id, owner_id=owner_id, scope_id=conversation_id)

    def purge_expired(self, *, owner_id: str, conversation_id: str, now: datetime):
        return self._purge_expired(owner_id=owner_id, scope_id=conversation_id, now=now)


class ProjectKnowledgeStore(_ScopedMemoryStore):
    _scope = MemoryScope.PROJECT

    def retrieve(self, memory_id: str, *, owner_id: str, project_id: str, now: datetime):
        return self._retrieve(memory_id, owner_id=owner_id, scope_id=project_id, now=now)

    def forget(self, memory_id: str, *, owner_id: str, project_id: str):
        return self._forget(memory_id, owner_id=owner_id, scope_id=project_id)

    def purge_expired(self, *, owner_id: str, project_id: str, now: datetime):
        return self._purge_expired(owner_id=owner_id, scope_id=project_id, now=now)
