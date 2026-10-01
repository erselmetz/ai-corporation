from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.database import get_connection, initialize_database
from app.memory import (ConversationMemoryStore, MemoryRecord, MemoryScope,
                        MemoryType, MemoryExpiredError, MemoryStore)

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


@pytest.fixture
def record():
    return MemoryRecord("memory", "owner", MemoryScope.CONVERSATION, "chat",
                        MemoryType.NOTE, "Explicit content", "message", NOW,
                        NOW + timedelta(hours=1), True)


def read(store, memory_id="memory", **overrides):
    request = dict(owner_id="owner", conversation_id="chat", now=NOW)
    request.update(overrides)
    return store.retrieve(memory_id, **request)


def test_round_trip_new_store_and_additive_initialization(record):
    MemoryStore().remember("legacy", "key", "Original")
    ConversationMemoryStore().retain(record, now=NOW)
    initialize_database()
    assert read(ConversationMemoryStore()) == record
    assert MemoryStore().recall("legacy", "key") == "Original"


@pytest.mark.parametrize("overrides", [{"owner_id": "other"}, {"conversation_id": "other"}])
def test_unauthorized_scope_cannot_read_or_delete(record, overrides):
    store = ConversationMemoryStore()
    store.retain(record, now=NOW)
    with pytest.raises(KeyError):
        read(store, **overrides)
    request = dict(owner_id="owner", conversation_id="chat")
    request.update(overrides)
    with pytest.raises(KeyError):
        store.forget("memory", **request)
    assert read(store) == record


def test_duplicate_and_wrong_scope_never_overwrite(record):
    store = ConversationMemoryStore()
    store.retain(record, now=NOW)
    with pytest.raises(ValueError):
        store.retain(replace(record, content="Changed"), now=NOW)
    with pytest.raises(ValueError):
        store.retain(replace(record, id="project", scope=MemoryScope.PROJECT), now=NOW)
    assert read(store) == record


def test_expiry_and_owner_scoped_cleanup(record):
    store = ConversationMemoryStore()
    store.retain(record, now=NOW)
    store.retain(replace(record, id="other", owner_id="other"), now=NOW)
    with pytest.raises(MemoryExpiredError):
        read(store, now=record.expires_at)
    assert store.purge_expired(owner_id="owner", conversation_id="chat", now=record.expires_at) == 1
    with pytest.raises(KeyError):
        read(store)
    assert read(store, "other", owner_id="other") == replace(record, id="other", owner_id="other")


def test_explicit_deletion_can_withdraw_consent_even_after_expiry(record):
    store = ConversationMemoryStore()
    store.retain(record, now=NOW)
    store.forget("memory", owner_id="owner", conversation_id="chat")
    with pytest.raises(KeyError):
        read(store)


def test_corrupt_storage_fails_loudly_without_cleanup(record):
    store = ConversationMemoryStore()
    store.retain(record, now=NOW)
    connection = get_connection()
    try:
        with connection:
            connection.execute("UPDATE conversation_memory SET type = 'unknown' WHERE id = 'memory'")
    finally:
        connection.close()
    with pytest.raises(ValueError):
        read(store)
    with pytest.raises(ValueError):
        store.purge_expired(owner_id="owner", conversation_id="chat", now=record.expires_at)
    connection = get_connection()
    try:
        assert connection.execute("SELECT COUNT(*) FROM conversation_memory").fetchone()[0] == 1
    finally:
        connection.close()


def test_chat_retention_is_explicit_and_survives_closure(monkeypatch):
    from app.providers import OllamaProvider
    from app.runtime.factory import create_corporation_runtime
    monkeypatch.setattr(OllamaProvider, "generate", lambda *_: "Reply")
    runtime = create_corporation_runtime()
    chat = runtime.application_service.corporation_chat()
    chat.start("chat", "local_worker")
    message = chat.send("chat", "User request").messages[0]
    with pytest.raises(KeyError):
        read(ConversationMemoryStore())
    with pytest.raises(ValueError, match="opt-in"):
        chat.retain_message("chat", message.id, memory_id="memory", owner_id="owner", expires_at=NOW + timedelta(hours=1), now=NOW)
    memory = chat.retain_message("chat", message.id, memory_id="memory", owner_id="owner", expires_at=NOW + timedelta(hours=1), now=NOW, retention_opt_in=True)
    chat.close("chat")
    assert read(ConversationMemoryStore()) == memory
    assert memory.source_id == message.id
    forbidden = MagicMock(side_effect=AssertionError("Unexpected provider execution"))
    monkeypatch.setattr(OllamaProvider, "generate", forbidden)
    ConversationMemoryStore().forget("memory", owner_id="owner", conversation_id="chat")
    forbidden.assert_not_called()
