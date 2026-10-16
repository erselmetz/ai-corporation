from dataclasses import dataclass
from datetime import datetime

from app.memory import MemoryScope


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    owner_id: str
    scope: MemoryScope
    scope_id: str
    memory_id: str
    revision: str
    source_reference: str
    position: int
    total: int
    text: str
    indexed_at: datetime


@dataclass(frozen=True)
class SemanticHit:
    memory_id: str
    scope: MemoryScope
    scope_id: str
    source_reference: str
    revision: str
    excerpt: str
    chunk_position: int
    relevance: float
    expires_at: datetime


@dataclass(frozen=True)
class SemanticSearchResult:
    hits: tuple[SemanticHit, ...]
    capability: str
    stale_candidates: int
    candidate_limit_reached: bool
    result_limit_reached: bool

