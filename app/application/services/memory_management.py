from datetime import datetime

from app.memory import MemoryScope, ConversationMemoryStore
from app.memory.corporation_knowledge import CorporationKnowledgeStore
from app.memory.scoped_store import ProjectKnowledgeStore
from app.memory.management import memory_revision, update_private_memory
from app.memory.models import _time
from .project_knowledge import ProjectKnowledgeService


class MemoryManagementService:
    def __init__(self, orchestrator, corporation_id: str | None):
        self._orchestrator = orchestrator
        self._corporation_id = corporation_id

    def _store(self, scope, scope_id):
        if scope is MemoryScope.CONVERSATION:
            return ConversationMemoryStore()
        if scope is MemoryScope.PROJECT:
            return ProjectKnowledgeStore()
        if scope is MemoryScope.CORPORATION:
            if self._corporation_id is None:
                raise RuntimeError("Corporation identity is not configured")
            if scope_id != self._corporation_id:
                raise KeyError("Memory unavailable in requested Corporation")
            return CorporationKnowledgeStore()
        raise ValueError("Unsupported memory scope")

    def list(self, *, actor_id, scope, scope_id, limit, now):
        _time(now)
        records = self._store(scope, scope_id).list_scoped(actor_id=actor_id, scope_id=scope_id, limit=limit)
        items = []
        for record in records:
            if now < record.created_at:
                raise ValueError("Memory creation time is in the future")
            items.append(dict(id=record.id, scope=record.scope.value, scope_id=record.scope_id,
                              type=record.type.value, expires_at=record.expires_at,
                              expired=now >= record.expires_at, can_manage=actor_id == record.owner_id))
        return items

    def inspect(self, memory_id, *, actor_id, scope, scope_id, now):
        store = self._store(scope, scope_id)
        provenance = None
        if scope is MemoryScope.CONVERSATION:
            record = store.retrieve(memory_id, owner_id=actor_id, conversation_id=scope_id, now=now)
        elif scope is MemoryScope.PROJECT:
            record = ProjectKnowledgeService(self._orchestrator).retrieve(
                memory_id, owner_id=actor_id, project_id=scope_id, now=now)
        else:
            knowledge = store.retrieve(memory_id, actor_id=actor_id, corporation_id=scope_id, now=now)
            record = knowledge.record
            provenance = knowledge.provenance
        return dict(id=record.id, scope=record.scope.value, scope_id=record.scope_id,
                    type=record.type.value, expires_at=record.expires_at, expired=False,
                    can_manage=actor_id == record.owner_id, content=record.content,
                    source_id=record.source_id, revision=memory_revision(record),
                    source_scope=provenance.source_scope.value if provenance else record.scope.value,
                    source_scope_id=provenance.source_scope_id if provenance else record.scope_id,
                    source_reference=provenance.source_reference if provenance else record.source_id)

    def update(self, memory_id, *, actor_id, scope, scope_id, revision, content,
               expires_at, retention_opt_in, now):
        detail = self.inspect(memory_id, actor_id=actor_id, scope=scope, scope_id=scope_id, now=now)
        if not detail["can_manage"]:
            raise PermissionError("Only the owner may modify memory")
        update_private_memory(memory_id, actor_id=actor_id, scope=scope, scope_id=scope_id,
                              revision=revision, content=content, expires_at=expires_at,
                              retention_opt_in=retention_opt_in, now=now)
        return self.inspect(memory_id, actor_id=actor_id, scope=scope, scope_id=scope_id, now=now)

    def remove(self, memory_id, *, actor_id, scope, scope_id):
        store = self._store(scope, scope_id)
        if scope is MemoryScope.CORPORATION:
            store.withdraw(memory_id, actor_id=actor_id, corporation_id=scope_id)
        elif scope is MemoryScope.PROJECT:
            store.forget(memory_id, owner_id=actor_id, project_id=scope_id)
        else:
            store.forget(memory_id, owner_id=actor_id, conversation_id=scope_id)
