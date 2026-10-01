from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.database import get_connection, initialize_database
from app.memory import MemoryRecord, MemoryScope, MemoryType, MemoryExpiredError
from app.runtime.factory import create_corporation_runtime

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


@pytest.fixture
def setup():
    runtime = create_corporation_runtime()
    project = runtime.application_service.create_project("Project", "")
    other = runtime.application_service.create_project("Other", "")
    task = runtime.application_service.create_task("Work", "Relevant work", project.id, agent_id="local_worker")
    record = MemoryRecord("knowledge", "owner", MemoryScope.PROJECT, project.id,
                        MemoryType.NOTE, "Explicit project note", task.id, NOW,
                        NOW + timedelta(hours=1), True)
    return runtime, project, other, task, record


def test_durable_knowledge_and_work_link_round_trip(setup):
    runtime, project, _, task, record = setup
    runtime.application_service.project_knowledge().retain(record, now=NOW)
    reloaded = create_corporation_runtime()
    assert reloaded.tasks.get(task.id).project_id == project.id
    loaded = reloaded.application_service.project_knowledge().retrieve("knowledge", owner_id="owner", project_id=project.id, now=NOW)
    assert loaded == record
    assert loaded.source_id == task.id
    reloaded.tasks.update(reloaded.tasks.get(task.id))
    assert create_corporation_runtime().tasks.get(task.id).project_id == project.id


def test_cross_project_owner_and_conversation_denial(setup):
    runtime, project, other, _, record = setup
    service = runtime.application_service.project_knowledge()
    with pytest.raises(ValueError, match="verified association"):
        service.retain(replace(record, scope_id=other.id), now=NOW)
    service.retain(record, now=NOW)
    for owner, scope in [("other", project.id), ("owner", other.id)]:
        with pytest.raises(KeyError):
            service.retrieve("knowledge", owner_id=owner, project_id=scope, now=NOW)
    with pytest.raises(ValueError, match="project scope"):
        service.retain(replace(record, id="conversation", scope=MemoryScope.CONVERSATION), now=NOW)


def test_missing_resources_expiry_and_withdrawal(setup):
    runtime, project, _, _, record = setup
    service = runtime.application_service.project_knowledge()
    with pytest.raises(ValueError, match="Task not found"):
        service.retain(replace(record, source_id="missing"), now=NOW)
    with pytest.raises(ValueError, match="Project not found"):
        service.retain(replace(record, scope_id="missing"), now=NOW)
    service.retain(record, now=NOW)
    with pytest.raises(MemoryExpiredError):
        service.retrieve("knowledge", owner_id="owner", project_id=project.id, now=record.expires_at)
    service.forget("knowledge", owner_id="owner", project_id=project.id)
    with pytest.raises(KeyError):
        service.retrieve("knowledge", owner_id="owner", project_id=project.id, now=NOW)


def test_legacy_migration_preserves_data_and_unknown_project(tmp_path, monkeypatch):
    from app.database import connection as database_connection
    monkeypatch.setattr(database_connection, "DATABASE_PATH", tmp_path / "legacy.db")
    connection = get_connection()
    try:
        with connection:
            connection.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL, assigned_agent TEXT, status TEXT NOT NULL, result TEXT, error TEXT)")
            connection.execute("INSERT INTO tasks VALUES ('legacy', 'Preserved title', 'Preserved content', NULL, 'pending', NULL, NULL)")
    finally:
        connection.close()
    initialize_database()
    initialize_database()
    from app.orchestrator import TaskRegistry
    task = TaskRegistry().get("legacy")
    assert task.title == "Preserved title"
    assert task.description == "Preserved content"
    assert task.project_id is None
