import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from app.database.connection import get_connection
from app.database.init import CURRENT_CONFIGURATION_VERSION, initialize_database
from app.application.services.owned_chat import ChatConflict, ChatNotFound
from app.resources import ModelLimit, ProviderLimit, ResourceLimits
from app.runtime.factory import create_corporation_runtime


def test_positions_and_resource_limits_survive_application_reconstruction():
    first = create_corporation_runtime()
    position = first.application_service.create_position(
        "Architect", ["Review durable operator state"],
    )
    limits = ResourceLimits(
        2,
        (ProviderLimit("ollama", 2),),
        (ModelLimit("ollama", "llama3.2:3b", 2),),
    )
    manager = first.application_service.resource_manager(limits)
    manager.allocate("transient-before-restart", provider_id="ollama", model_id="llama3.2:3b")

    second = create_corporation_runtime()
    restored = second.application_service.get_position(position.id)
    assert restored == position
    resource = second.application_service.resource_manager()
    assert resource.snapshot().global_capacity.allocated == 0
    assert resource.snapshot().global_capacity.limit == 2
    assert resource.snapshot().allocations == ()


def test_retained_employee_conversation_recovers_read_only_and_owner_scoped():
    first = create_corporation_runtime()
    chat = first.application_service.owned_employee_chat()
    snapshot = chat.start("owner-a", "local_employee", history_opt_in=True)
    identifier = snapshot.conversation.id

    second = create_corporation_runtime()
    recovered = second.application_service.owned_employee_chat()
    assert recovered.list("owner-b") == ()
    items = recovered.list("owner-a")
    assert len(items) == 1
    assert items[0].conversation_id == identifier
    assert items[0].history_retained is True
    assert items[0].read_only is True
    loaded = recovered.get("owner-a", identifier)
    assert loaded.read_only is True
    assert loaded.conversation == snapshot.conversation
    try:
        recovered.send("owner-a", identifier, "must not execute")
        assert False, "recovered chat must be read-only"
    except ChatConflict:
        pass
    try:
        recovered.delete_history("owner-b", identifier)
        assert False, "another owner must not delete this history"
    except ChatNotFound:
        pass
    recovered.delete_history("owner-a", identifier)
    assert recovered.list("owner-a") == ()


def test_unretained_employee_conversation_is_not_written_to_database():
    runtime = create_corporation_runtime()
    chat = runtime.application_service.owned_employee_chat()
    chat.start("owner-a", "local_employee")
    connection = get_connection()
    try:
        assert connection.execute("SELECT COUNT(*) FROM operator_conversations").fetchone()[0] == 0
    finally:
        connection.close()


def test_task_184_schema_is_additive_and_migration_versioned():
    runtime = create_corporation_runtime()
    del runtime
    connection = get_connection()
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == CURRENT_CONFIGURATION_VERSION
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert {
            "operator_positions", "operator_resource_limits",
            "operator_task_proposals", "operator_conversations",
        } <= tables
    finally:
        connection.close()


def test_task_184_migration_failure_rolls_back_additive_schema():
    create_corporation_runtime()
    connection = get_connection()
    try:
        connection.execute("DROP TABLE operator_positions")
        connection.execute("DROP TABLE operator_resource_limits")
        connection.execute("DROP INDEX operator_proposals_owner_expiry")
        connection.execute("DROP INDEX operator_conversations_owner_expiry")
        connection.execute("DROP TABLE operator_task_proposals")
        connection.execute("DROP TABLE operator_conversations")
        connection.execute("CREATE TABLE operator_task_proposals (invalid TEXT)")
        connection.execute("PRAGMA user_version = 2")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(sqlite3.OperationalError):
        initialize_database()

    connection = get_connection()
    try:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert version == 2
        assert "operator_positions" not in tables
        assert "operator_resource_limits" not in tables
        assert "operator_conversations" not in tables
        assert "tasks" in tables
    finally:
        connection.close()


def test_task_184_state_survives_a_real_python_process_restart(tmp_path):
    """Exercise a new interpreter against isolated app data, not just new services."""
    repository = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(repository), environment.get("PYTHONPATH", "")) if value
    )
    setup = r'''
import json
from app.runtime.factory import create_corporation_runtime
from app.resources import ModelLimit, ProviderLimit, ResourceLimits
runtime = create_corporation_runtime()
position = runtime.application_service.create_position("Architect", ["Process restart check"])
runtime.application_service.resource_manager(ResourceLimits(
    2, (ProviderLimit("ollama", 2),), (ModelLimit("ollama", "llama3.2:3b", 2),)
))
chat = runtime.application_service.owned_employee_chat().start(
    "owner-a", "local_employee", history_opt_in=True
)
print(json.dumps({"position_id": position.id, "conversation_id": chat.conversation.id}))
'''
    created = subprocess.run(
        [sys.executable, "-c", setup], cwd=tmp_path, env=environment,
        check=True, capture_output=True, text=True, timeout=30,
    )
    identifiers = json.loads(created.stdout)
    verify = r'''
from app.runtime.factory import create_corporation_runtime
runtime = create_corporation_runtime()
service = runtime.application_service
assert service.get_position(POSITION_ID).title == "Architect"
manager = service.resource_manager()
assert manager.snapshot().global_capacity.limit == 2
assert manager.snapshot().global_capacity.allocated == 0
chat = service.owned_employee_chat()
assert [item.conversation_id for item in chat.list("owner-a")] == [CONVERSATION_ID]
assert chat.list("owner-b") == ()
history = chat.get("owner-a", CONVERSATION_ID)
assert history.read_only is True
'''.replace("POSITION_ID", repr(identifiers["position_id"])).replace(
        "CONVERSATION_ID", repr(identifiers["conversation_id"])
    )
    subprocess.run(
        [sys.executable, "-c", verify], cwd=tmp_path, env=environment,
        check=True, capture_output=True, text=True, timeout=30,
    )
    assert (tmp_path / "projects" / "ai_corporation.db").is_file()
