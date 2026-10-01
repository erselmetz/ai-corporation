from datetime import datetime

from app.memory import MemoryRecord, MemoryScope
from app.memory.scoped_store import ProjectKnowledgeStore
from app.orchestrator import Orchestrator


class ProjectKnowledgeService:
    """Private, explicitly retained project knowledge linked to an existing Task."""

    def __init__(self, orchestrator: Orchestrator):
        self._orchestrator = orchestrator
        self._store = ProjectKnowledgeStore()

    def _validate_link(self, record: MemoryRecord):
        if record.scope is not MemoryScope.PROJECT:
            raise ValueError("Project knowledge requires project scope")
        self._orchestrator.projects.get(record.scope_id)
        task = self._orchestrator.tasks.get(record.source_id)
        if task.project_id != record.scope_id:
            raise ValueError("Source Task does not have a verified association with this Project")

    def retain(self, record: MemoryRecord, *, now: datetime):
        if not isinstance(record, MemoryRecord):
            raise TypeError("Expected a MemoryRecord")
        self._validate_link(record)
        self._store.retain(record, now=now)
        return record

    def retrieve(self, memory_id: str, *, owner_id: str, project_id: str, now: datetime):
        record = self._store.retrieve(memory_id, owner_id=owner_id, project_id=project_id, now=now)
        self._validate_link(record)
        return record

    def forget(self, memory_id: str, *, owner_id: str, project_id: str):
        self._store.forget(memory_id, owner_id=owner_id, project_id=project_id)
