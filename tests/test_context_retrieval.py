from dataclasses import FrozenInstanceError, asdict, replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from app.database import get_connection
from app.memory import ConversationMemoryStore, MemoryRecord, MemoryScope, MemoryType
from app.memory.models import MemoryDataError
from app.runtime.factory import create_corporation_runtime

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


def note(identifier, content, *, owner="owner", scope_id="chat", expiry=None):
    record = MemoryRecord(identifier, owner, MemoryScope.CONVERSATION, scope_id,
                          MemoryType.NOTE, content, "message-" + identifier,
                          NOW, expiry or NOW + timedelta(hours=1), True)
    ConversationMemoryStore().retain(record, now=NOW)
    return record


def retrieve(service, query="alpha beta", **kwargs):
    return service.retrieve(query, actor_id=kwargs.pop("actor_id", "owner"),
                            scope=kwargs.pop("scope", MemoryScope.CONVERSATION),
                            scope_id=kwargs.pop("scope_id", "chat"), now=kwargs.pop("now", NOW), **kwargs)


def test_deterministic_relevance_and_traceable_immutable_results():
    service = create_corporation_runtime().application_service.context_retrieval()
    note("z", "ALPHA beta"); note("b", "alpha"); note("a", "beta"); note("unrelated", "gamma")
    result = retrieve(service)
    assert [hit.source.memory_id for hit in result.hits] == ["z", "a", "b"]
    assert result.hits[0].matched_terms == ("alpha", "beta")
    assert result.hits[0].source.original_reference == "message-z"
    assert result.hits[0].source.scope_id == "chat"
    assert result.scanned_records == 4
    with pytest.raises(FrozenInstanceError):
        result.hits[0].content = "Changed"
    assert retrieve(service) == result


def test_exact_scope_owner_and_expiry_no_fallback():
    service = create_corporation_runtime().application_service.context_retrieval()
    note("own", "alpha"); note("private", "alpha secret", owner="other"); note("elsewhere", "alpha", scope_id="other-chat")
    result = retrieve(service)
    assert [hit.source.memory_id for hit in result.hits] == ["own"]
    assert retrieve(service, scope_id="missing").hits == ()
    assert retrieve(service, now=NOW + timedelta(hours=1)).hits == ()
    assert retrieve(service, "unmatched").hits == ()


def test_project_source_association_verified_before_matching():
    runtime = create_corporation_runtime()
    project = runtime.application_service.create_project("Project", "")
    task = runtime.application_service.create_task("Work", "Relevant", project.id, agent_id="local_worker")
    record = MemoryRecord("project", "owner", MemoryScope.PROJECT, project.id,
                          MemoryType.NOTE, "alpha beta", task.id, NOW, NOW + timedelta(hours=1), True)
    runtime.application_service.project_knowledge().retain(record, now=NOW)
    service = runtime.application_service.context_retrieval()
    hit = retrieve(service, scope=MemoryScope.PROJECT, scope_id=project.id).hits[0]
    assert hit.source.original_reference == task.id
    # Construct a replacement domain Task through its dataclass constructor and
    # persist it through the public registry API; the returned summary stays frozen.
    runtime.tasks.update(replace(runtime.tasks.get(task.id), project_id=None))
    assert task.project_id == project.id
    with pytest.raises(ValueError, match="verified association"):
        retrieve(service, scope=MemoryScope.PROJECT, scope_id=project.id)


def test_publication_grants_provenance_and_revocation_rechecked():
    runtime = create_corporation_runtime()
    source = note("private", "alpha beta")
    knowledge = runtime.application_service.corporation_knowledge()
    knowledge.publish("published", actor_id="owner", source_scope=source.scope,
                      source_scope_id=source.scope_id, source_memory_id=source.id,
                      readers=["reader"], now=NOW, publication_opt_in=True)
    service = runtime.application_service.context_retrieval()
    result = retrieve(service, actor_id="reader", scope=MemoryScope.CORPORATION, scope_id="corp_local")
    assert len(result.hits) == 1
    trace = result.hits[0].source
    assert trace.source_memory_or_reference == source.id
    assert trace.original_scope is MemoryScope.CONVERSATION
    assert trace.original_reference == source.source_id
    assert retrieve(service, actor_id="outsider", scope=MemoryScope.CORPORATION, scope_id="corp_local").hits == ()
    knowledge.revoke_reader("published", actor_id="owner", reader_id="reader")
    assert retrieve(service, actor_id="reader", scope=MemoryScope.CORPORATION, scope_id="corp_local").hits == ()
    # Already returned immutable copies remain snapshots, not revocable storage.
    assert result.hits[0].content == source.content


@pytest.mark.parametrize("query, options", [
    ("", {}), ("!!!", {}), ("x" * 1025, {}), (" ".join(str(i) for i in range(33)), {}),
    ("alpha", {"limit": 0}), ("alpha", {"limit": 11}), ("alpha", {"limit": True}),
    ("alpha", {"scope": "conversation"}), ("alpha", {"now": NOW.replace(tzinfo=None)}),
])
def test_invalid_requests_fail_before_storage(query, options):
    service = create_corporation_runtime().application_service.context_retrieval()
    with pytest.raises((ValueError, TypeError)):
        retrieve(service, query, **options)


def test_explicit_scan_result_and_byte_limits():
    service = create_corporation_runtime().application_service.context_retrieval()
    for i in range(101):
        note(f"note-{i:03d}", "alpha " + "x" * 8186)
    result = retrieve(service, limit=10)
    assert result.scanned_records == 100
    assert result.candidate_limit_reached is True
    assert result.result_limit_reached is True
    assert result.byte_limit_reached is True
    assert 1 <= len(result.hits) < 10
    assert sum(len(json.dumps(asdict(hit), ensure_ascii=False, default=str).encode("utf-8")) for hit in result.hits) <= service.MAX_RESULT_BYTES


def test_corrupt_authorized_data_is_not_empty_retrieval():
    service = create_corporation_runtime().application_service.context_retrieval()
    note("invalid", "alpha")
    connection = get_connection()
    try:
        with connection:
            connection.execute("UPDATE conversation_memory SET type='unknown'")
    finally:
        connection.close()
    with pytest.raises(MemoryDataError):
        retrieve(service)


def test_corrections_and_deletion_observed_on_new_retrieval():
    runtime = create_corporation_runtime()
    note("note", "alpha")
    service = runtime.application_service.context_retrieval()
    previous = retrieve(service)
    manager = runtime.application_service.memory_management()
    manager.update("note", actor_id="owner", scope=MemoryScope.CONVERSATION, scope_id="chat",
                   revision=previous.hits[0].source.revision, content="beta", expires_at=NOW + timedelta(hours=2),
                   retention_opt_in=True, now=NOW)
    assert retrieve(service, "alpha").hits == ()
    assert retrieve(service, "beta").hits[0].source.revision != previous.hits[0].source.revision
    manager.remove("note", actor_id="owner", scope=MemoryScope.CONVERSATION, scope_id="chat")
    assert retrieve(service).hits == ()
