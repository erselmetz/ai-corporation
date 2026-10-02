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


class ContextRetrievalService:
    """Trusted callers bind actor identity; requests never broaden their scope.

    Results are snapshots of knowledge, not executable instructions. The caller
    must re-retrieve before later use to observe expiry, correction or revocation.
    """
    MAX_CANDIDATES = 100
    MAX_RESULT_BYTES = 32768

    def __init__(self, memory_manager):
        self._memory_manager = memory_manager

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
