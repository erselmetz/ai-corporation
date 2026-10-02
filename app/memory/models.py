"""Explicit memory contracts; no storage, retrieval side effects, or sharing."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MemoryScope(str, Enum):
    CONVERSATION = "conversation"
    PROJECT = "project"
    CORPORATION = "corporation"


class MemoryType(str, Enum):
    NOTE = "note"
    SUMMARY = "summary"


def _identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 256:
        raise ValueError(f"{label} must be a nonempty identifier of at most 256 bytes")


def _time(value: datetime) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Memory timestamps must be timezone-aware")


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    owner_id: str
    scope: MemoryScope
    scope_id: str
    type: MemoryType
    content: str
    source_id: str
    created_at: datetime
    expires_at: datetime
    retention_opt_in: bool = False

    def __post_init__(self):
        for label in ("id", "owner_id", "scope_id", "source_id"):
            _identifier(getattr(self, label), label)
        if not isinstance(self.scope, MemoryScope) or not isinstance(self.type, MemoryType):
            raise TypeError("Memory scope and type must use their enums")
        if not isinstance(self.content, str) or not self.content.strip() or len(self.content.encode("utf-8")) > 8192:
            raise ValueError("Memory content must be nonempty text of at most 8192 bytes")
        _time(self.created_at)
        _time(self.expires_at)
        if self.expires_at <= self.created_at:
            raise ValueError("Memory expiry must follow creation")
        if self.retention_opt_in is not True:
            raise ValueError("Explicit memory retention opt-in is required")


class MemoryDataError(ValueError):
    """Malformed stored data; never treated as an empty retrieval result."""


class MemoryExpiredError(ValueError):
    pass


def require_memory_access(record: MemoryRecord, *, owner_id: str,
                          scope: MemoryScope, scope_id: str, now: datetime) -> None:
    """Exact owner/scope access; trusted caller supplies authenticated identity.

    There is no administrator bypass, cross-scope fallback, or implicit sharing.
    Expiry makes records unavailable even before physical storage cleanup.
    """
    if not isinstance(record, MemoryRecord):
        raise TypeError("Expected a MemoryRecord")
    _identifier(owner_id, "owner_id")
    _identifier(scope_id, "scope_id")
    if not isinstance(scope, MemoryScope):
        raise TypeError("Expected a MemoryScope")
    if (record.owner_id, record.scope, record.scope_id) != (owner_id, scope, scope_id):
        raise PermissionError("Memory access denied")
    _time(now)
    if now < record.created_at:
        raise ValueError("Memory access time precedes creation")
    if now >= record.expires_at:
        raise MemoryExpiredError("Memory has expired")
