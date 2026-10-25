from datetime import datetime, timedelta
from uuid import uuid4

from app.memory import MemoryScope, ConversationMemoryStore, MemoryRecord, MemoryType, OwnerKnowledgeStore
from app.memory.corporation_knowledge import CorporationKnowledgeStore
from app.memory.scoped_store import ProjectKnowledgeStore
from app.memory.management import memory_revision, update_private_memory
from app.memory.models import _time
from .project_knowledge import ProjectKnowledgeService


class MemoryManagementService:
    def __init__(self, orchestrator, corporation_id: str | None, *, semantic_invalidator=None):
        self._orchestrator = orchestrator
        self._corporation_id = corporation_id
        self._semantic_invalidator = semantic_invalidator

    def _store(self, scope, scope_id, actor_id=None):
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
        if scope is MemoryScope.OWNER:
            if actor_id is None or scope_id != actor_id:
                raise KeyError("Owner knowledge is unavailable")
            return OwnerKnowledgeStore()
        raise ValueError("Unsupported memory scope")

    def list(self, *, actor_id, scope, scope_id, limit, now):
        _time(now)
        store = self._store(scope, scope_id, actor_id)
        records = store.list_scoped(actor_id=actor_id, scope_id=scope_id, limit=limit)
        items = []
        for record in records:
            if now < record.created_at:
                raise ValueError("Memory creation time is in the future")
            provenance = None
            if scope is MemoryScope.CORPORATION:
                knowledge = store.retrieve(record.id, actor_id=actor_id, corporation_id=scope_id, now=now)
                source = knowledge.provenance
                provenance = dict(source_scope=source.source_scope,
                                  source_scope_id=source.source_scope_id,
                                  source_reference=source.source_reference,
                                  source_created_at=source.source_created_at)
            items.append(dict(id=record.id, scope=record.scope.value, scope_id=record.scope_id,
                              type=record.type.value, created_at=record.created_at,
                              expires_at=record.expires_at,
                              expired=now >= record.expires_at, can_manage=actor_id == record.owner_id,
                              provenance=provenance))
        if scope is MemoryScope.OWNER:
            for item, record in zip(items, records):
                item["source_reference"] = record.source_id
        return items

    def inspect(self, memory_id, *, actor_id, scope, scope_id, now):
        store = self._store(scope, scope_id, actor_id)
        provenance = None
        if scope is MemoryScope.CONVERSATION:
            record = store.retrieve(memory_id, owner_id=actor_id, conversation_id=scope_id, now=now)
        elif scope is MemoryScope.PROJECT:
            record = ProjectKnowledgeService(self._orchestrator).retrieve(
                memory_id, owner_id=actor_id, project_id=scope_id, now=now)
        elif scope is MemoryScope.OWNER:
            record = store.retrieve(memory_id, owner_id=actor_id, now=now)
        else:
            knowledge = store.retrieve(memory_id, actor_id=actor_id, corporation_id=scope_id, now=now)
            record = knowledge.record
            provenance = knowledge.provenance
        return dict(id=record.id, scope=record.scope.value, scope_id=record.scope_id,
                    type=record.type.value, created_at=record.created_at,
                    expires_at=record.expires_at, expired=False,
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
        if self._semantic_invalidator is not None:
            self._semantic_invalidator(memory_id, scope=scope, scope_id=scope_id)
        return self.inspect(memory_id, actor_id=actor_id, scope=scope, scope_id=scope_id, now=now)

    def remove(self, memory_id, *, actor_id, scope, scope_id):
        store = self._store(scope, scope_id, actor_id)
        if scope is MemoryScope.CORPORATION:
            store.withdraw(memory_id, actor_id=actor_id, corporation_id=scope_id)
        elif scope is MemoryScope.PROJECT:
            store.forget(memory_id, owner_id=actor_id, project_id=scope_id)
        elif scope is MemoryScope.OWNER:
            store.forget(memory_id, owner_id=actor_id)
        else:
            store.forget(memory_id, owner_id=actor_id, conversation_id=scope_id)
        if self._semantic_invalidator is not None:
            self._semantic_invalidator(memory_id, scope=scope, scope_id=scope_id)

    def create_owner_note(self, actor_id, content, *, source_name, expires_at, retention_opt_in, now):
        if retention_opt_in is not True:
            raise ValueError("Explicit retention consent is required")
        _time(now)
        if not isinstance(expires_at, datetime) or expires_at.tzinfo is None or expires_at.utcoffset() is None:
            raise ValueError("Expiry must be timezone-aware")
        if not timedelta(minutes=1) <= expires_at - now <= timedelta(days=30):
            raise ValueError("Expiry must be between 1 minute and 30 days from now")
        record = MemoryRecord(uuid4().hex, actor_id, MemoryScope.OWNER, actor_id,
                              MemoryType.NOTE, content, source_name, now, expires_at, True)
        OwnerKnowledgeStore().retain(record, now=now)
        return self.inspect(record.id, actor_id=actor_id, scope=MemoryScope.OWNER,
                            scope_id=actor_id, now=now)

    def import_v3code_brain(self, plan, actor_id, *, expires_at, retention_opt_in, now):
        from app.knowledge.v3code_import import V3CodeBrainPlan
        if not isinstance(plan, V3CodeBrainPlan):
            raise TypeError("Expected a validated v3code Brain plan")
        if retention_opt_in is not True:
            raise ValueError("Explicit retention consent is required")
        _time(now)
        if not isinstance(expires_at, datetime) or expires_at.tzinfo is None or expires_at.utcoffset() is None:
            raise ValueError("Expiry must be timezone-aware")
        if not timedelta(minutes=1) <= expires_at - now <= timedelta(days=30):
            raise ValueError("Expiry must be between 1 minute and 30 days from now")
        records = tuple(MemoryRecord(note.id, actor_id, MemoryScope.OWNER, actor_id,
                                     MemoryType.NOTE, note.content, note.source_reference,
                                     now, expires_at, True) for note in plan.notes)
        try:
            created, skipped = OwnerKnowledgeStore().retain_import_batch(records, now=now)
        except ValueError as exc:
            if "identity conflicts" in str(exc) or "conflicts with existing" in str(exc):
                from app.memory.management import MemoryConflictError
                raise MemoryConflictError(str(exc)) from None
            raise
        return {"digest": plan.digest, "chunk_count": plan.chunk_count,
                "source_count": plan.source_count, "note_count": len(plan.notes),
                "created_count": created, "skipped_count": skipped,
                "ignored_embeddings": True}
