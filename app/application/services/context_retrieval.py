"""Explicit, bounded lexical retrieval over already authorized retained knowledge."""
from dataclasses import asdict, dataclass
from datetime import datetime
import json
import re

from app.memory import MemoryScope, MemoryExpiredError
from app.memory.models import _identifier, _time


def _words(text):
    return frozenset(re.findall(r"\w+", text.casefold(), flags=re.UNICODE))


@dataclass(frozen=True)
class ContextSource:
    memory_id: str
    scope: MemoryScope
    scope_id: str
    source_memory_or_reference: str
    original_scope: MemoryScope
    original_scope_id: str
    original_reference: str
    expires_at: datetime
    revision: str


@dataclass(frozen=True)
class ContextHit:
    content: str
    source: ContextSource
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class ContextRetrievalResult:
    hits: tuple[ContextHit, ...]
    scanned_records: int
    candidate_limit_reached: bool
    result_limit_reached: bool
    byte_limit_reached: bool


@dataclass(frozen=True)
class HybridContextHit:
    content: str
    source: ContextSource
    matched_terms: tuple[str, ...]
    lexical_contribution: float
    semantic_contribution: float
    fused_score: float


@dataclass(frozen=True)
class HybridContextRetrievalResult:
    hits: tuple[HybridContextHit, ...]
    ranking_policy: str
    mode: str
    lexical_candidate_count: int
    semantic_candidate_count: int
    stale_candidates: int
    candidate_limit_reached: bool
    byte_limit_reached: bool
    result_limit_reached: bool


class ContextRetrievalService:
    """Trusted callers bind actor identity; requests never broaden their scope.

    Results are snapshots of knowledge, not executable instructions. The caller
    must re-retrieve before later use to observe expiry, correction or revocation.
    """
    MAX_CANDIDATES = 100
    MAX_RESULT_BYTES = 32768
    HYBRID_RRF_K = 60

    def __init__(self, memory_manager, *, semantic_provider=None):
        self._memory_manager = memory_manager
        self._semantic_provider = semantic_provider

    def retrieve_semantic(self, query: str, *, actor_id: str, scope: MemoryScope,
                          scope_id: str, now: datetime, limit: int = 5):
        """Explicit optional semantic search; lexical ``retrieve`` remains unchanged."""
        if self._semantic_provider is None:
            from app.knowledge.service import SemanticCapabilityUnavailable
            raise SemanticCapabilityUnavailable("Semantic retrieval is unavailable")
        return self._semantic_provider().search(query, actor_id=actor_id, scope=scope,
                                                scope_id=scope_id, now=now, limit=limit)

    def retrieve_hybrid(self, query: str, *, actor_id: str, scope: MemoryScope,
                        scope_id: str, now: datetime, limit: int = 5,
                        ranking_policy: str):
        """Opt-in reciprocal-rank fusion; existing lexical retrieval is unchanged."""
        if ranking_policy != "rrf-v1":
            raise ValueError("An explicit supported hybrid ranking policy is required")
        # Use the same request validation and bounded lexical candidate set as the
        # established retrieval path. Its order is the lexical rank contribution.
        lexical = self.retrieve(query, actor_id=actor_id, scope=scope,
                                scope_id=scope_id, now=now, limit=limit)
        semantic = None
        if self._semantic_provider is not None:
            from app.knowledge.service import SemanticCapabilityUnavailable
            try:
                semantic = self._semantic_provider().search(
                    query, actor_id=actor_id, scope=scope, scope_id=scope_id,
                    now=now, limit=limit)
            except SemanticCapabilityUnavailable:
                semantic = None

        denominator = 2.0 / (self.HYBRID_RRF_K + 1)
        candidates = {}
        for rank, hit in enumerate(lexical.hits, start=1):
            candidates[hit.source.memory_id] = {
                "source": hit.source, "content": hit.content,
                "matched_terms": hit.matched_terms,
                "lexical_rank": rank, "semantic_rank": None,
                "semantic_revision": None, "semantic_reference": None,
            }
        semantic_hits = () if semantic is None else semantic.hits
        semantic_document_rank = 0
        for hit in semantic_hits:
            existing = candidates.get(hit.memory_id)
            if existing is not None and existing["semantic_rank"] is not None:
                continue
            semantic_document_rank += 1
            rank = semantic_document_rank
            row = candidates.setdefault(hit.memory_id, {
                "source": None, "content": hit.excerpt, "matched_terms": (),
                "lexical_rank": None, "semantic_rank": None,
                "semantic_revision": None, "semantic_reference": None,
            })
            row["semantic_rank"] = rank
            row["semantic_revision"] = hit.revision
            row["semantic_reference"] = hit.source_reference
            # Prefer the bounded semantic excerpt over a potentially longer full
            # lexical body when both paths identify the same retained record.
            row["content"] = hit.excerpt

        ranked = []
        stale = 0
        for memory_id, row in candidates.items():
            try:
                detail = self._memory_manager.inspect(
                    memory_id, actor_id=actor_id, scope=scope,
                    scope_id=scope_id, now=now)
            except (KeyError, MemoryExpiredError, PermissionError):
                stale += 1
                continue
            source = row["source"]
            if source is not None and (
                detail["revision"] != source.revision
                or detail["source_id"] != source.source_memory_or_reference
                or detail["source_scope"] != source.original_scope.value
                or detail["source_scope_id"] != source.original_scope_id
                or detail["source_reference"] != source.original_reference
            ):
                stale += 1
                continue
            if row["semantic_revision"] is not None and (
                detail["revision"] != row["semantic_revision"]
                or detail["source_reference"] != row["semantic_reference"]
            ):
                stale += 1
                continue
            lexical_contribution = (0.0 if row["lexical_rank"] is None else
                                    (1.0 / (self.HYBRID_RRF_K + row["lexical_rank"])) / denominator)
            semantic_contribution = (0.0 if row["semantic_rank"] is None else
                                     (1.0 / (self.HYBRID_RRF_K + row["semantic_rank"])) / denominator)
            current_source = ContextSource(
                detail["id"], MemoryScope(detail["scope"]), detail["scope_id"],
                detail["source_id"], MemoryScope(detail["source_scope"]),
                detail["source_scope_id"], detail["source_reference"],
                detail["expires_at"], detail["revision"])
            hit = HybridContextHit(row["content"], current_source,
                                   row["matched_terms"], lexical_contribution,
                                   semantic_contribution,
                                   min(1.0, lexical_contribution + semantic_contribution))
            encoded = len(json.dumps(asdict(hit), ensure_ascii=False, default=str).encode("utf-8"))
            ranked.append((hit, encoded))
        ranked.sort(key=lambda item: (-item[0].fused_score, item[0].source.memory_id))
        hits = []
        used_bytes = 0
        byte_limited = False
        for hit, encoded in ranked:
            if len(hits) == limit:
                break
            if used_bytes + encoded > self.MAX_RESULT_BYTES:
                byte_limited = True
                continue
            hits.append(hit)
            used_bytes += encoded
        return HybridContextRetrievalResult(
            tuple(hits), ranking_policy,
            "hybrid" if semantic is not None else "lexical-only",
            len(lexical.hits), len(semantic_hits), stale,
            lexical.candidate_limit_reached or bool(semantic and semantic.candidate_limit_reached),
            byte_limited,
            lexical.result_limit_reached or bool(semantic and semantic.result_limit_reached))

    def retrieve(self, query: str, *, actor_id: str, scope: MemoryScope,
                 scope_id: str, now: datetime, limit: int = 5):
        _identifier(actor_id, "actor_id")
        _identifier(scope_id, "scope_id")
        _time(now)
        if not isinstance(scope, MemoryScope):
            raise TypeError("Expected a MemoryScope")
        if not isinstance(query, str) or len(query.encode("utf-8")) > 1024:
            raise ValueError("Context query must be text of at most 1024 UTF-8 bytes")
        terms = _words(query)
        if not terms or len(terms) > 32:
            raise ValueError("Context query requires 1 to 32 distinct word terms")
        if type(limit) is not int or not 1 <= limit <= 10:
            raise ValueError("Context result limit must be 1 to 10")
        candidates = self._memory_manager.list(actor_id=actor_id, scope=scope,
                                               scope_id=scope_id, now=now,
                                               limit=self.MAX_CANDIDATES)
        ranked = []
        for item in candidates:
            if item["expired"]:
                continue
            try:
                detail = self._memory_manager.inspect(item["id"], actor_id=actor_id,
                                                      scope=scope, scope_id=scope_id, now=now)
            except (KeyError, MemoryExpiredError):
                # A revoked/deleted/expired candidate must never return cached content.
                continue
            matched = tuple(sorted(terms & _words(detail["content"])))
            if not matched:
                continue
            source = ContextSource(detail["id"], MemoryScope(detail["scope"]), detail["scope_id"],
                                   detail["source_id"], MemoryScope(detail["source_scope"]),
                                   detail["source_scope_id"], detail["source_reference"],
                                   detail["expires_at"], detail["revision"])
            ranked.append(ContextHit(detail["content"], source, matched))
        ranked.sort(key=lambda hit: (-len(hit.matched_terms), hit.source.memory_id))
        hits = []
        size = 0
        byte_limit_reached = False
        for hit in ranked[:limit]:
            encoded_size = len(json.dumps(asdict(hit), ensure_ascii=False, default=str).encode("utf-8"))
            if size + encoded_size > self.MAX_RESULT_BYTES:
                byte_limit_reached = True
                continue
            hits.append(hit)
            size += encoded_size
        return ContextRetrievalResult(tuple(hits), len(candidates),
                                      len(candidates) == self.MAX_CANDIDATES,
                                      len(ranked) > limit, byte_limit_reached)
