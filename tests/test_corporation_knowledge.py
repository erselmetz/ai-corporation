from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.database import get_connection, initialize_database
from app.memory import ConversationMemoryStore, MemoryRecord, MemoryScope, MemoryType, MemoryExpiredError
from app.application.services.corporation_knowledge import CorporationKnowledgeService
from app.runtime.factory import create_corporation_runtime

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


@pytest.fixture
def setup():
    runtime = create_corporation_runtime()
    source = MemoryRecord("source", "owner", MemoryScope.CONVERSATION, "chat",
                          MemoryType.NOTE, "Explicit private note", "message", NOW,
                          NOW + timedelta(hours=1), True)
    ConversationMemoryStore().retain(source, now=NOW)
    return runtime, source, runtime.application_service.corporation_knowledge()


def publish(service, **changes):
    values = dict(actor_id="owner", source_scope=MemoryScope.CONVERSATION,
                  source_scope_id="chat", source_memory_id="source", readers=["reader"],
                  now=NOW, publication_opt_in=True)
    values.update(changes)
    return service.publish("published", **values)


def test_explicit_publication_provenance_expiry_and_reload(setup):
    runtime, source, service = setup
    published = publish(service)
    assert published.record.content == source.content
    assert published.record.expires_at == source.expires_at
    assert published.record.source_id == source.id
    assert published.provenance.source_scope_id == source.scope_id
    assert published.provenance.source_reference == source.source_id
    with pytest.raises(FrozenInstanceError):
        published.record.owner_id = "reader"
    reloaded = create_corporation_runtime().application_service.corporation_knowledge()
    assert reloaded.retrieve("published", actor_id="reader", now=NOW) == published
    assert service.retrieve("published", actor_id="owner", now=NOW) == published
    with pytest.raises(MemoryExpiredError):
        service.retrieve("published", actor_id="reader", now=source.expires_at)
    with pytest.raises(KeyError):
        ConversationMemoryStore().retrieve("source", owner_id="reader", conversation_id="chat", now=NOW)


@pytest.mark.parametrize("changes", [
    {"publication_opt_in": False}, {"publication_opt_in": 1}, {"readers": []},
    {"readers": "reader"}, {"readers": ["*"]}, {"readers": [""]},
    {"readers": ["reader", "reader"]}, {"readers": [str(i) for i in range(101)]},
    {"source_scope": MemoryScope.CORPORATION},
])
def test_invalid_publications_have_no_storage_side_effects(setup, changes):
    _, _, service = setup
    with pytest.raises((TypeError, ValueError)):
        publish(service, **changes)
    with pytest.raises(KeyError):
        service.retrieve("published", actor_id="owner", now=NOW)


def test_other_owners_scopes_and_expired_sources_cannot_publish(setup):
    _, source, service = setup
    for changes in [{"actor_id": "other"}, {"source_scope_id": "other"}]:
        with pytest.raises(KeyError):
            publish(service, **changes)
    with pytest.raises(MemoryExpiredError):
        publish(service, now=source.expires_at)


def test_named_readers_only_and_corporation_isolation(setup):
    runtime, _, service = setup
    publish(service)
    for actor in ["other", "administrator", "employee", "*"]:
        with pytest.raises(KeyError):
            service.retrieve("published", actor_id=actor, now=NOW)
    other = CorporationKnowledgeService("other-corporation", runtime.orchestrator)
    with pytest.raises(KeyError):
        other.retrieve("published", actor_id="reader", now=NOW)


def test_only_owner_can_revoke_or_withdraw(setup):
    _, _, service = setup
    publish(service)
    with pytest.raises(KeyError):
        service.revoke_reader("published", actor_id="reader", reader_id="reader")
    with pytest.raises(KeyError):
        service.withdraw("published", actor_id="reader")
    service.revoke_reader("published", actor_id="owner", reader_id="reader")
    with pytest.raises(KeyError):
        service.retrieve("published", actor_id="reader", now=NOW)
    assert service.retrieve("published", actor_id="owner", now=NOW)
    service.withdraw("published", actor_id="owner")
    with pytest.raises(KeyError):
        service.retrieve("published", actor_id="owner", now=NOW)
    # Publication withdrawal never erases the private source.
    assert ConversationMemoryStore().retrieve("source", owner_id="owner", conversation_id="chat", now=NOW)


def test_transaction_rolls_back_record_provenance_and_grants(setup):
    _, _, service = setup
    connection = get_connection()
    try:
        with connection:
            connection.execute("CREATE TRIGGER reject_reader BEFORE INSERT ON corporation_knowledge_readers WHEN NEW.reader_id = 'reject' BEGIN SELECT RAISE(ABORT, 'Injected failure'); END")
    finally:
        connection.close()
    with pytest.raises(ValueError, match="conflicts"):
        publish(service, readers=["reader", "reject"])
    connection = get_connection()
    try:
        for table in ["corporation_knowledge", "corporation_knowledge_provenance", "corporation_knowledge_readers"]:
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    finally:
        connection.close()


def test_duplicate_does_not_replace_existing_publication(setup):
    _, _, service = setup
    original = publish(service)
    with pytest.raises(ValueError):
        publish(service, readers=["other"])
    assert service.retrieve("published", actor_id="reader", now=NOW) == original
    with pytest.raises(KeyError):
        service.retrieve("published", actor_id="other", now=NOW)


def test_corrupt_provenance_rejected_and_legacy_data_preserved(setup):
    _, _, service = setup
    publish(service)
    initialize_database()
    connection = get_connection()
    try:
        with connection:
            connection.execute("UPDATE corporation_knowledge_provenance SET source_scope = 'unknown'")
    finally:
        connection.close()
    with pytest.raises(ValueError):
        service.retrieve("published", actor_id="reader", now=NOW)
    assert ConversationMemoryStore().retrieve("source", owner_id="owner", conversation_id="chat", now=NOW)


def test_project_source_link_is_checked_and_no_provider_or_task_execution(setup, monkeypatch):
    runtime, _, service = setup
    from app.providers import OllamaProvider
    from app.orchestrator import Orchestrator
    project = runtime.application_service.create_project("Knowledge project", "")
    task = runtime.application_service.create_task("Work", "Description", project.id, agent_id="local_worker")
    source = MemoryRecord("project-source", "owner", MemoryScope.PROJECT, project.id,
                          MemoryType.SUMMARY, "User-supplied summary", task.id, NOW,
                          NOW + timedelta(hours=1), True)
    runtime.application_service.project_knowledge().retain(source, now=NOW)
    forbidden = MagicMock(side_effect=AssertionError("Unexpected side effect"))
    monkeypatch.setattr(OllamaProvider, "generate", forbidden)
    monkeypatch.setattr(Orchestrator, "create_task", forbidden)
    monkeypatch.setattr(Orchestrator, "execute_task", forbidden)
    publication = publish(service, source_scope=MemoryScope.PROJECT, source_scope_id=project.id, source_memory_id="project-source")
    assert publication.provenance.source_reference == task.id
    service.retrieve("published", actor_id="reader", now=NOW)
    service.withdraw("published", actor_id="owner")
    forbidden.assert_not_called()
