"""Optional semantic indexing and retrieval for explicitly retained knowledge."""

from .models import KnowledgeChunk, SemanticHit, SemanticSearchResult
from .service import SemanticMemoryService

__all__ = ["KnowledgeChunk", "SemanticHit", "SemanticSearchResult", "SemanticMemoryService"]
