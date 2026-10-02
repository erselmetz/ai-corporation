from dataclasses import replace
from datetime import datetime
import hashlib
import json

from app.database import get_connection
from .models import MemoryRecord, MemoryScope, require_memory_access
from .scoped_store import ConversationMemoryStore, ProjectKnowledgeStore


class MemoryConflictError(ValueError):
    pass


def memory_revision(record: MemoryRecord) -> str:
    values = [record.id, record.owner_id, record.scope.value, record.scope_id,
              record.type.value, record.content, record.source_id,
              record.created_at.isoformat(), record.expires_at.isoformat()]
    return hashlib.sha256(json.dumps(values, ensure_ascii=True).encode("utf-8")).hexdigest()


def update_private_memory(memory_id: str, *, actor_id: str, scope: MemoryScope,
                          scope_id: str, revision: str, content: str,
                          expires_at: datetime, now: datetime, retention_opt_in: bool):
    if scope is MemoryScope.CONVERSATION:
        store = ConversationMemoryStore()
    elif scope is MemoryScope.PROJECT:
        store = ProjectKnowledgeStore()
    else:
        raise MemoryConflictError("Published knowledge is immutable; withdraw and explicitly republish")
    store._request(memory_id, actor_id, scope_id)
    if retention_opt_in is not True:
        raise ValueError("Explicit retention consent is required")
    connection = get_connection()
    try:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"SELECT * FROM {store._table} WHERE id = ? AND owner_id = ? AND scope_id = ?",
                (memory_id, actor_id, scope_id)).fetchone()
            if row is None:
                raise KeyError("Memory unavailable")
            current = store._record(row)
            require_memory_access(current, owner_id=actor_id, scope=scope, scope_id=scope_id, now=now)
            if revision != memory_revision(current):
                raise MemoryConflictError("Memory changed; reload before saving")
            updated = replace(current, content=content, expires_at=expires_at)
            require_memory_access(updated, owner_id=actor_id, scope=scope, scope_id=scope_id, now=now)
            connection.execute(
                f"UPDATE {store._table} SET content = ?, expires_at = ? WHERE id = ? AND owner_id = ? AND scope_id = ?",
                (content, expires_at.isoformat(), memory_id, actor_id, scope_id))
            return updated
    finally:
        connection.close()
