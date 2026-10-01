from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.memory import MemoryRecord, MemoryScope, MemoryType, MemoryExpiredError, require_memory_access

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


@pytest.fixture
def record():
    return MemoryRecord("memory", "owner", MemoryScope.CONVERSATION, "chat",
                        MemoryType.NOTE, "Explicit note", "message", NOW,
                        NOW + timedelta(hours=1), retention_opt_in=True)


def test_immutable_record_and_valid_access(record):
    require_memory_access(record, owner_id="owner", scope=MemoryScope.CONVERSATION,
                          scope_id="chat", now=NOW)
    with pytest.raises(FrozenInstanceError):
        record.owner_id = "other"


@pytest.mark.parametrize("changes", [
    {"owner_id": "other"}, {"scope": MemoryScope.PROJECT}, {"scope_id": "other-chat"},
])
def test_access_is_exactly_owner_and_scope_bound(record, changes):
    request = dict(owner_id="owner", scope=MemoryScope.CONVERSATION, scope_id="chat", now=NOW)
    request.update(changes)
    with pytest.raises(PermissionError):
        require_memory_access(record, **request)


@pytest.mark.parametrize("changes", [
    {"retention_opt_in": False}, {"retention_opt_in": 1}, {"expires_at": NOW},
    {"expires_at": None}, {"created_at": NOW.replace(tzinfo=None)},
    {"id": ""}, {"source_id": ""}, {"owner_id": ""}, {"scope_id": ""},
    {"content": ""}, {"content": "x" * 8193}, {"scope": "conversation"}, {"type": "note"},
])
def test_invalid_records_fail_closed(record, changes):
    with pytest.raises((TypeError, ValueError)):
        replace(record, **changes)


def test_expiry_boundary_and_clock_validation(record):
    request = dict(owner_id="owner", scope=MemoryScope.CONVERSATION, scope_id="chat")
    require_memory_access(record, **request, now=record.expires_at - timedelta(microseconds=1))
    with pytest.raises(MemoryExpiredError):
        require_memory_access(record, **request, now=record.expires_at)
    with pytest.raises(ValueError):
        require_memory_access(record, **request, now=NOW - timedelta(seconds=1))
    with pytest.raises(ValueError):
        require_memory_access(record, **request, now=NOW.replace(tzinfo=None))


def test_project_scope_has_no_conversation_fallback(record):
    project = replace(record, scope=MemoryScope.PROJECT, scope_id="project")
    require_memory_access(project, owner_id="owner", scope=MemoryScope.PROJECT,
                          scope_id="project", now=NOW)
    with pytest.raises(PermissionError):
        require_memory_access(project, owner_id="owner", scope=MemoryScope.CONVERSATION,
                              scope_id="project", now=NOW)


def test_contracts_do_not_persist_or_execute(record, monkeypatch):
    from app.providers import OllamaProvider
    from app.orchestrator import Orchestrator
    forbidden = MagicMock(side_effect=AssertionError("Unexpected side effect"))
    monkeypatch.setattr("sqlite3.connect", forbidden)
    monkeypatch.setattr(OllamaProvider, "generate", forbidden)
    monkeypatch.setattr(Orchestrator, "create_task", forbidden)
    copy = replace(record, type=MemoryType.SUMMARY)
    require_memory_access(copy, owner_id="owner", scope=MemoryScope.CONVERSATION,
                          scope_id="chat", now=NOW)
    forbidden.assert_not_called()
