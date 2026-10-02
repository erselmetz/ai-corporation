from datetime import datetime

from app.memory import ConversationMemoryStore, MemoryScope
from app.memory.corporation_knowledge import CorporationKnowledgeStore
from app.memory.models import _identifier
from .project_knowledge import ProjectKnowledgeService


class CorporationKnowledgeService:
    """Trusted application callers supply identity; no automatic membership grants."""

    def __init__(self, corporation_id: str, orchestrator):
        _identifier(corporation_id, "corporation_id")
        self._corporation_id = corporation_id
        self._orchestrator = orchestrator
        self._store = CorporationKnowledgeStore()

    def publish(self, knowledge_id: str, *, actor_id: str, source_scope: MemoryScope,
                source_scope_id: str, source_memory_id: str, readers, now: datetime,
                publication_opt_in: bool = False):
        if publication_opt_in is not True:
            raise ValueError("Explicit owner publication consent is required")
        if source_scope is MemoryScope.CONVERSATION:
            source = ConversationMemoryStore().retrieve(source_memory_id, owner_id=actor_id,
                                                         conversation_id=source_scope_id, now=now)
        elif source_scope is MemoryScope.PROJECT:
            source = ProjectKnowledgeService(self._orchestrator).retrieve(
                source_memory_id, owner_id=actor_id, project_id=source_scope_id, now=now)
        else:
            raise ValueError("Only conversation/project memory can be published")
        return self._store.publish(source, knowledge_id=knowledge_id, actor_id=actor_id,
                                   corporation_id=self._corporation_id, readers=readers,
                                   now=now, publication_opt_in=publication_opt_in)

    def retrieve(self, knowledge_id: str, *, actor_id: str, now: datetime):
        return self._store.retrieve(knowledge_id, actor_id=actor_id,
                                    corporation_id=self._corporation_id, now=now)

    def revoke_reader(self, knowledge_id: str, *, actor_id: str, reader_id: str):
        self._store.revoke_reader(knowledge_id, actor_id=actor_id,
                                  corporation_id=self._corporation_id, reader_id=reader_id)

    def withdraw(self, knowledge_id: str, *, actor_id: str):
        self._store.withdraw(knowledge_id, actor_id=actor_id, corporation_id=self._corporation_id)
