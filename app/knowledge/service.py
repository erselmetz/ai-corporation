"""Explicit, owner-scoped semantic indexing over existing approved memory records."""
from datetime import datetime
import hashlib
import json
import math

from app.memory import MemoryExpiredError, MemoryScope
from app.memory.models import _identifier, _time
from .chunking import chunk_text
from .models import KnowledgeChunk, SemanticHit, SemanticSearchResult

MAX_INDEX_BYTES = 8192
MAX_SEARCH_QUERY_BYTES = 1024
MAX_RESULTS = 10
MAX_SEARCH_CANDIDATES = 40
MAX_RESULT_BYTES = 32768
MAX_BATCH = 32
MAX_EMBEDDING_DIMENSIONS = 16384
MIN_RELEVANCE = 0.05


class SemanticCapabilityUnavailable(RuntimeError):
    pass


def _source_key(owner_id, scope, scope_id, memory_id):
    payload = json.dumps([owner_id, scope.value, scope_id, memory_id], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validated_vector(vector):
    try:
        values = tuple(float(value) for value in vector)
    except (TypeError, ValueError, OverflowError):
        raise RuntimeError("Embedding provider returned an invalid vector") from None
    if not 1 <= len(values) <= MAX_EMBEDDING_DIMENSIONS or any(not math.isfinite(value) for value in values):
        raise RuntimeError("Embedding provider returned an invalid vector")
    return values


class SemanticMemoryService:
    def __init__(self, memory_manager, embedding_provider=None, vector_store=None, *, unavailable_reason=None):
        self._memory = memory_manager
        self._embeddings = embedding_provider
        self._vectors = vector_store
        self._unavailable_reason = unavailable_reason

    @property
    def enabled(self):
        return self._embeddings is not None and self._vectors is not None

    def status(self):
        if self.enabled:
            return {"state": "configured", "provider": "local", "model": self._safe_identity(),
                    "detail": "A local model and vector store are configured. The model loads locally on the first explicit indexing or search request."}
        return {"state": "unavailable" if self._unavailable_reason else "disabled",
                "provider": None, "model": None,
                "detail": self._unavailable_reason or
                "Optional local semantic dependencies and explicit model/store configuration are required."}

    def _safe_identity(self):
        # Do not expose arbitrary local paths or secrets through the UI/API.
        identity = str(getattr(self._embeddings, "identity", "local"))
        return identity.rsplit("/", 1)[-1].rsplit("\\", 1)[-1][:128] or "local"

    def _require_enabled(self):
        if not self.enabled:
            raise SemanticCapabilityUnavailable("Semantic retrieval is unavailable")

    def index(self, memory_id: str, *, actor_id: str, scope: MemoryScope,
              scope_id: str, now: datetime):
        self._require_enabled()
        _identifier(actor_id, "actor_id")
        _identifier(scope_id, "scope_id")
        _identifier(memory_id, "memory_id")
        _time(now)
        detail = self._memory.inspect(memory_id, actor_id=actor_id, scope=scope, scope_id=scope_id, now=now)
        if detail.get("can_manage") is not True:
            raise PermissionError("Only the knowledge owner may index this record")
        content = detail["content"]
        if len(content.encode("utf-8")) > MAX_INDEX_BYTES:
            raise ValueError("Knowledge source exceeds the indexing size limit")
        pieces = chunk_text(content)
        source_key = _source_key(actor_id, scope, scope_id, memory_id)
        ids = tuple(hashlib.sha256(f"{source_key}:{detail['revision']}:{position}".encode()).hexdigest()
                    for position in range(len(pieces)))
        vectors = []
        for start in range(0, len(pieces), MAX_BATCH):
            batch = tuple(pieces[start:start + MAX_BATCH])
            vectors.extend(_validated_vector(vector) for vector in self._embeddings.embed_batch(batch))
        if len(vectors) != len(pieces) or not vectors:
            raise RuntimeError("Embedding provider returned an invalid batch")
        dimension = len(vectors[0])
        if dimension > MAX_EMBEDDING_DIMENSIONS or any(len(vector) != dimension for vector in vectors):
            raise RuntimeError("Embedding provider returned invalid vectors")
        metadata = tuple({"owner_id": actor_id, "scope": scope.value, "scope_id": scope_id,
                          "memory_id": memory_id, "revision": detail["revision"],
                          "source_reference": detail["source_reference"], "position": position,
                          "total": len(pieces), "source_key": source_key,
                          "embedding_model": self._safe_identity()}
                         for position in range(len(pieces)))
        self._vectors.delete_source(source_key)
        self._vectors.upsert(ids, vectors, metadata)
        return tuple(KnowledgeChunk(chunk_id, actor_id, scope, scope_id, memory_id,
                                    detail["revision"], detail["source_reference"], position,
                                    len(pieces), pieces[position], now)
                     for position, chunk_id in enumerate(ids))

    def search(self, query: str, *, actor_id: str, scope: MemoryScope,
               scope_id: str, now: datetime, limit: int = 5):
        self._require_enabled()
        _identifier(actor_id, "actor_id")
        _identifier(scope_id, "scope_id")
        _time(now)
        if not isinstance(scope, MemoryScope):
            raise TypeError("Expected a MemoryScope")
        if not isinstance(query, str) or not query.strip() or len(query.encode("utf-8")) > MAX_SEARCH_QUERY_BYTES:
            raise ValueError("Semantic query must be nonempty text of at most 1024 UTF-8 bytes")
        if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
            raise ValueError("Semantic result limit must be 1 to 10")
        vector = _validated_vector(self._embeddings.embed_one(query))
        conditions = [{"scope": scope.value}, {"scope_id": scope_id}]
        if scope is not MemoryScope.CORPORATION:
            conditions.append({"owner_id": actor_id})
        conditions.append({"embedding_model": self._safe_identity()})
        candidate_limit = min(MAX_SEARCH_CANDIDATES, limit * 4)
        candidates = self._vectors.search(vector, {"$and": conditions}, candidate_limit)
        hits = []
        seen_chunks = set()
        stale = 0
        used_bytes = 0
        for chunk_id, distance, metadata in candidates:
            if (metadata.get("scope"), metadata.get("scope_id")) != (scope.value, scope_id):
                continue
            if metadata.get("embedding_model") != self._safe_identity():
                continue
            if scope is not MemoryScope.CORPORATION and metadata.get("owner_id") != actor_id:
                continue
            memory_id = metadata.get("memory_id")
            if not isinstance(memory_id, str) or chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk_id)
            try:
                detail = self._memory.inspect(memory_id, actor_id=actor_id, scope=scope, scope_id=scope_id, now=now)
            except (KeyError, MemoryExpiredError, PermissionError):
                self._delete_metadata_source(metadata)
                stale += 1
                continue
            if detail["revision"] != metadata.get("revision"):
                self._delete_metadata_source(metadata)
                stale += 1
                continue
            chunks = chunk_text(detail["content"])
            position = metadata.get("position")
            if type(position) is not int or not 0 <= position < len(chunks):
                self._delete_metadata_source(metadata)
                stale += 1
                continue
            distance = float(distance)
            if not math.isfinite(distance):
                continue
            relevance = max(0.0, min(1.0, 1.0 - distance))
            if relevance < MIN_RELEVANCE:
                continue
            hit = SemanticHit(memory_id, scope, scope_id, detail["source_reference"],
                              detail["revision"], chunks[position], position,
                              relevance, detail["expires_at"])
            encoded = len(json.dumps(hit.__dict__, ensure_ascii=False, default=str).encode("utf-8"))
            if used_bytes + encoded > MAX_RESULT_BYTES:
                break
            hits.append(hit)
            used_bytes += encoded
            if len(hits) == limit:
                break
        hits.sort(key=lambda hit: (-hit.relevance, hit.memory_id, hit.chunk_position))
        return SemanticSearchResult(tuple(hits), "local", stale, len(candidates) == candidate_limit)

    def _delete_metadata_source(self, metadata):
        source_key = metadata.get("source_key")
        if isinstance(source_key, str) and len(source_key) == 64:
            self._vectors.delete_source(source_key)

    def invalidate(self, memory_id: str, *, actor_id: str, scope: MemoryScope, scope_id: str):
        if not self.enabled:
            return
        self._vectors.delete_source(_source_key(actor_id, scope, scope_id, memory_id))

    def invalidate_all_owners(self, memory_id: str, *, scope: MemoryScope, scope_id: str):
        if not self.enabled:
            return
        self._vectors.delete_memory(scope.value, scope_id, memory_id)
