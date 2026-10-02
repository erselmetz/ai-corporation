from dataclasses import dataclass
from datetime import datetime
import sqlite3

from app.database import get_connection
from .models import MemoryRecord, MemoryScope, MemoryDataError, require_memory_access, _identifier, _time
from .scoped_store import _ScopedMemoryStore


@dataclass(frozen=True)
class KnowledgeProvenance:
    source_scope: MemoryScope
    source_scope_id: str
    source_reference: str
    source_created_at: datetime

    def __post_init__(self):
        if self.source_scope not in (MemoryScope.CONVERSATION, MemoryScope.PROJECT) or not isinstance(self.source_scope, MemoryScope):
            raise ValueError("Knowledge source must be private conversation or project memory")
        _identifier(self.source_scope_id, "source_scope_id")
        _identifier(self.source_reference, "source_reference")
        _time(self.source_created_at)


@dataclass(frozen=True)
class CorporationKnowledge:
    record: MemoryRecord
    provenance: KnowledgeProvenance


class CorporationKnowledgeStore(_ScopedMemoryStore):
    _scope = MemoryScope.CORPORATION

    def retain(self, record, *, now):
        raise ValueError("Corporation knowledge requires explicit owner publication")

    def publish(self, source: MemoryRecord, *, knowledge_id: str, actor_id: str,
                corporation_id: str, readers, now: datetime, publication_opt_in: bool = False):
        if publication_opt_in is not True:
            raise ValueError("Explicit owner publication consent is required")
        if not isinstance(source, MemoryRecord):
            raise TypeError("Expected a MemoryRecord")
        if source.scope not in (MemoryScope.CONVERSATION, MemoryScope.PROJECT):
            raise ValueError("Only private memory can be published")
        require_memory_access(source, owner_id=actor_id, scope=source.scope,
                              scope_id=source.scope_id, now=now)
        if not isinstance(readers, (tuple, list, frozenset, set)) or not 1 <= len(readers) <= 100:
            raise ValueError("Publication needs 1 to 100 named readers")
        for reader in readers:
            _identifier(reader, "reader_id")
            if reader == "*":
                raise ValueError("Wildcard readers are not allowed")
        if len(set(readers)) != len(readers):
            raise ValueError("Duplicate readers are not allowed")
        record = MemoryRecord(knowledge_id, source.owner_id, MemoryScope.CORPORATION,
                              corporation_id, source.type, source.content, source.id,
                              now, source.expires_at, True)
        provenance = KnowledgeProvenance(source.scope, source.scope_id,
                                         source.source_id, source.created_at)
        connection = get_connection()
        try:
            with connection:
                self._insert(connection, record)
                connection.execute(
                    "INSERT INTO corporation_knowledge_provenance VALUES (?, ?, ?, ?, ?)",
                    (record.id, provenance.source_scope.value, provenance.source_scope_id,
                     provenance.source_reference, provenance.source_created_at.isoformat()))
                connection.executemany(
                    "INSERT INTO corporation_knowledge_readers VALUES (?, ?)",
                    [(record.id, reader) for reader in readers])
            return CorporationKnowledge(record, provenance)
        except sqlite3.IntegrityError:
            raise ValueError("Publication conflicts with existing knowledge") from None
        finally:
            connection.close()

    def retrieve(self, knowledge_id: str, *, actor_id: str, corporation_id: str, now: datetime):
        self._request(knowledge_id, actor_id, corporation_id)
        _time(now)
        connection = get_connection()
        try:
            row = connection.execute(
                "SELECT k.* FROM corporation_knowledge k WHERE k.id = ? AND k.scope_id = ? "
                "AND (k.owner_id = ? OR EXISTS (SELECT 1 FROM corporation_knowledge_readers r "
                "WHERE r.knowledge_id = k.id AND r.reader_id = ?))",
                (knowledge_id, corporation_id, actor_id, actor_id)).fetchone()
            if row is None:
                raise KeyError("Knowledge unavailable in requested actor/Corporation scope")
            record = self._record(row)
            require_memory_access(record, owner_id=record.owner_id, scope=self._scope,
                                  scope_id=corporation_id, now=now)
            source = connection.execute(
                "SELECT * FROM corporation_knowledge_provenance WHERE knowledge_id = ?",
                (knowledge_id,)).fetchone()
            try:
                if source is None:
                    raise ValueError("Knowledge provenance is missing")
                provenance = KnowledgeProvenance(MemoryScope(source["source_scope"]),
                                                 source["source_scope_id"], source["source_reference"],
                                                 datetime.fromisoformat(source["source_created_at"]))
                if provenance.source_created_at > record.created_at:
                    raise ValueError("Knowledge provenance time is invalid")
            except (ValueError, TypeError, KeyError, IndexError):
                raise MemoryDataError("Stored knowledge provenance is invalid") from None
            return CorporationKnowledge(record, provenance)
        finally:
            connection.close()

    def _require_owner(self, connection, knowledge_id, actor_id, corporation_id):
        self._request(knowledge_id, actor_id, corporation_id)
        row = connection.execute(
            "SELECT id FROM corporation_knowledge WHERE id = ? AND owner_id = ? AND scope_id = ?",
            (knowledge_id, actor_id, corporation_id)).fetchone()
        if row is None:
            raise KeyError("Knowledge unavailable in requested owner/Corporation scope")

    def revoke_reader(self, knowledge_id: str, *, actor_id: str, corporation_id: str, reader_id: str):
        _identifier(reader_id, "reader_id")
        connection = get_connection()
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                self._require_owner(connection, knowledge_id, actor_id, corporation_id)
                cursor = connection.execute(
                    "DELETE FROM corporation_knowledge_readers WHERE knowledge_id = ? AND reader_id = ?",
                    (knowledge_id, reader_id))
                if cursor.rowcount != 1:
                    raise KeyError("Reader grant not found")
        finally:
            connection.close()

    def withdraw(self, knowledge_id: str, *, actor_id: str, corporation_id: str):
        connection = get_connection()
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                self._require_owner(connection, knowledge_id, actor_id, corporation_id)
                connection.execute("DELETE FROM corporation_knowledge_readers WHERE knowledge_id = ?", (knowledge_id,))
                connection.execute("DELETE FROM corporation_knowledge_provenance WHERE knowledge_id = ?", (knowledge_id,))
                connection.execute("DELETE FROM corporation_knowledge WHERE id = ?", (knowledge_id,))
        finally:
            connection.close()
