import sqlite3

from fastapi.testclient import TestClient
import pytest

from app.api.app import create_app
from app.database import connection as database_connection
from app.local import create_local_app
import app.portability.backups as backups_module
from app.portability.backups import BackupError, DataPortabilityService, MAGIC

PASSWORD = "test-owner-passphrase-168"
ORIGIN = "http://127.0.0.1:8000"
PASSPHRASE = "test-backup-passphrase-168"


def insert_task(title):
    with sqlite3.connect(database_connection.DATABASE_PATH) as connection:
        connection.execute(
            "INSERT INTO tasks (id,title,description,status) VALUES (?,?,?,?)",
            ("task-" + title, title, "private description", "pending"),
        )


def test_default_backup_is_encrypted_and_contains_only_allowlisted_configuration(tmp_path):
    service = DataPortabilityService(database_connection.DATABASE_PATH, recovery_directory=tmp_path / "recovery")
    insert_task("hidden")
    preview = service.preview()
    assert "tasks" not in preview["included_tables"]
    assert any("private app content" in item for item in preview["excluded"])
    payload = service.export(PASSPHRASE)
    assert payload.startswith(MAGIC)
    assert b"private description" not in payload
    assert service.inspect(payload, PASSPHRASE)["include_private_data"] is False


def test_private_backup_explicitly_includes_user_content_and_redacts_common_credentials(tmp_path):
    service = DataPortabilityService(database_connection.DATABASE_PATH, recovery_directory=tmp_path / "recovery")
    insert_task("included")
    with sqlite3.connect(database_connection.DATABASE_PATH) as connection:
        connection.execute("UPDATE tasks SET description=? WHERE id=?", ("api_key=sk-" + "A" * 24, "task-included"))
    preview = service.preview(include_private_data=True)
    assert "tasks" in preview["included_tables"]
    payload = service.export(PASSPHRASE, include_private_data=True)
    info = service.inspect(payload, PASSPHRASE)
    assert info["include_private_data"] is True
    assert info["row_counts"]["tasks"] == 1
    with pytest.raises(BackupError, match="passphrase"):
        service.inspect(payload, "wrong-passphrase")
    damaged = payload[:-1] + bytes([payload[-1] ^ 1])
    with pytest.raises(BackupError, match="verification"):
        service.inspect(damaged, PASSPHRASE)
    manifest, database = service._read_backup(payload, PASSPHRASE)
    assert b"[REDACTED]" in database
    assert b"sk-" + b"A" * 24 not in database


def test_private_export_fails_closed_on_credential_named_columns_and_size_bounds(tmp_path):
    service = DataPortabilityService(database_connection.DATABASE_PATH, recovery_directory=tmp_path / "recovery")
    with sqlite3.connect(database_connection.DATABASE_PATH) as connection:
        connection.execute("CREATE TABLE unsafe_connection (id TEXT PRIMARY KEY, api_key TEXT NOT NULL)")
        connection.execute("INSERT INTO unsafe_connection VALUES ('one','must-not-export')")
    with pytest.raises(BackupError, match="may contain credentials"):
        service.export(PASSPHRASE, include_private_data=True)
    with pytest.raises(BackupError, match="supported size"):
        service.inspect(b"x" * (72 * 1024 * 1024 + 1), PASSPHRASE)


def test_export_checks_database_size_before_copying(tmp_path, monkeypatch):
    service = DataPortabilityService(database_connection.DATABASE_PATH, recovery_directory=tmp_path / "recovery")
    monkeypatch.setattr(backups_module, "MAX_DATABASE_BYTES", 1)
    with pytest.raises(BackupError, match="supported backup size"):
        service.export(PASSPHRASE)


def test_private_restore_replaces_database_and_keeps_encrypted_pre_restore_copy(tmp_path):
    service = DataPortabilityService(database_connection.DATABASE_PATH, recovery_directory=tmp_path / "recovery")
    insert_task("old")
    with sqlite3.connect(database_connection.DATABASE_PATH) as connection:
        connection.execute("INSERT INTO task_logs (id,task_id,event,message) VALUES (100,'task-old','test','old')")
        connection.execute("DELETE FROM task_logs WHERE id=100")
    backup = service.export(PASSPHRASE, include_private_data=True)
    insert_task("new")
    with pytest.raises(BackupError, match="confirmation"):
        service.restore(backup, PASSPHRASE, confirmed=False)
    result = service.restore(backup, PASSPHRASE, confirmed=True)
    assert result["requires_restart"] == "true"
    assert result["recovery_copy"].endswith(".erselbackup")
    assert len(list((tmp_path / "recovery").glob("pre-restore-*.erselbackup"))) == 1
    with sqlite3.connect(database_connection.DATABASE_PATH) as connection:
        titles = [row[0] for row in connection.execute("SELECT title FROM tasks")]
        connection.execute("INSERT INTO task_logs (task_id,event,message) VALUES ('task-old','test','new')")
        next_log_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
    assert titles == ["old"]
    assert next_log_id > 100


def test_configuration_restore_merges_only_configuration_and_preserves_tasks(tmp_path):
    service = DataPortabilityService(database_connection.DATABASE_PATH, recovery_directory=tmp_path / "recovery")
    insert_task("keep")
    with sqlite3.connect(database_connection.DATABASE_PATH) as connection:
        connection.execute("CREATE TABLE owner_preferences (owner_id TEXT PRIMARY KEY, preferences_json TEXT NOT NULL, version INTEGER NOT NULL)")
        connection.execute("INSERT INTO owner_preferences VALUES ('local-owner','{}',1)")
        connection.execute(
            "INSERT INTO operator_agent_profiles(corporation_id,agent_id,record_json) VALUES (?,?,?)",
            ("corp_local", "researcher", '{"name":"Researcher","system_prompt":"Use approved sources."}'),
        )
    backup = service.export(PASSPHRASE)
    with sqlite3.connect(database_connection.DATABASE_PATH) as connection:
        connection.execute("UPDATE owner_preferences SET preferences_json='changed'")
        connection.execute("DELETE FROM operator_agent_profiles")
    service.restore(backup, PASSPHRASE, confirmed=True)
    with sqlite3.connect(database_connection.DATABASE_PATH) as connection:
        assert connection.execute("SELECT preferences_json FROM owner_preferences").fetchone()[0] == "{}"
        assert connection.execute("SELECT title FROM tasks").fetchone()[0] == "keep"
        assert connection.execute(
            "SELECT record_json FROM operator_agent_profiles WHERE agent_id='researcher'"
        ).fetchone()[0] == '{"name":"Researcher","system_prompt":"Use approved sources."}'


def test_local_api_requires_owner_permission_csrf_and_keeps_default_api_closed(tmp_path):
    service = DataPortabilityService(database_connection.DATABASE_PATH, recovery_directory=tmp_path / "recovery")
    local = create_local_app(password=PASSWORD, data_portability_service=service)
    with TestClient(local, base_url=ORIGIN, client=("127.0.0.1", 50100)) as client:
        assert client.get("/api/local/backup/preview").status_code == 401
        assert client.get("/ui/login").status_code == 200
        assert client.get("/ui/backup").status_code == 200
        assert client.get("/ui/static/backup.mjs").status_code == 200
        assert client.get("/api/local/backup/diagnostics").status_code == 401
        assert client.post("/api/local/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN}).status_code == 200
        session = client.get("/api/local/session").json()
        assert {"backup:read", "backup:export", "backup:restore"}.issubset(session["permissions"])
        preview = client.get("/api/local/backup/preview")
        assert preview.status_code == 200
        diagnostics = client.get("/api/local/backup/diagnostics")
        assert diagnostics.status_code == 200
        assert "private description" not in diagnostics.text
        assert str(database_connection.DATABASE_PATH) not in diagnostics.text
        denied = client.post("/api/local/backup/export", json={"passphrase": PASSPHRASE})
        assert denied.status_code == 403
        headers = {"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]}
        exported = client.post("/api/local/backup/export", json={"passphrase": PASSPHRASE}, headers=headers)
        assert exported.status_code == 200
        assert exported.headers["content-type"] == "application/vnd.erselmetz.backup"
        assert exported.content.startswith(MAGIC)
    with TestClient(create_app(), base_url=ORIGIN) as default:
        assert default.get("/api/local/backup/preview").status_code == 404
        assert default.get("/ui/backup").status_code == 200
        assert default.get("/api/local/backup/diagnostics").status_code == 404


def test_restore_api_requires_inspection_and_gates_api_until_restart(tmp_path):
    service = DataPortabilityService(database_connection.DATABASE_PATH, recovery_directory=tmp_path / "recovery")
    backup = service.export(PASSPHRASE, include_private_data=True)
    local = create_local_app(password=PASSWORD, data_portability_service=service)
    with TestClient(local, base_url=ORIGIN, client=("127.0.0.1", 50100)) as client:
        client.post("/api/local/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN})
        csrf = client.get("/api/local/session").json()["csrf"]
        headers = {"Origin": ORIGIN, "X-Local-CSRF": csrf}
        files = {"file": ("backup.erselbackup", backup, "application/vnd.erselmetz.backup")}
        assert client.post("/api/local/backup/inspect", files=files, data={"passphrase": PASSPHRASE}, headers=headers).status_code == 200
        wrong_passphrase = client.post("/api/local/backup/restore", files=files,
                                       data={"passphrase": "wrong-backup-passphrase", "confirmation": "RESTORE"},
                                       headers=headers)
        assert wrong_passphrase.status_code == 400
        assert client.get("/api/local/backup/preview").status_code == 200
        denied = client.post("/api/local/backup/restore", files=files,
                             data={"passphrase": PASSPHRASE, "confirmation": "no"}, headers=headers)
        assert denied.status_code == 400
        restored = client.post("/api/local/backup/restore", files=files,
                               data={"passphrase": PASSPHRASE, "confirmation": "RESTORE"}, headers=headers)
        assert restored.status_code == 200
        assert restored.json()["requires_restart"] == "true"
        assert client.get("/api/local/backup/preview").status_code == 503
        assert client.get("/ui/backup").status_code == 200


def test_restore_failure_after_verified_inspection_keeps_restart_gate_closed(tmp_path):
    service = DataPortabilityService(database_connection.DATABASE_PATH, recovery_directory=tmp_path / "recovery")

    def fail_during_restore(*_args, **_kwargs):
        raise BackupError("simulated failure after verification")

    service.restore = fail_during_restore
    backup = DataPortabilityService(database_connection.DATABASE_PATH).export(PASSPHRASE)
    local = create_local_app(password=PASSWORD, data_portability_service=service)
    with TestClient(local, base_url=ORIGIN, client=("127.0.0.1", 50100)) as client:
        client.post("/api/local/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN})
        csrf = client.get("/api/local/session").json()["csrf"]
        headers = {"Origin": ORIGIN, "X-Local-CSRF": csrf}
        files = {"file": ("backup.erselbackup", backup, "application/vnd.erselmetz.backup")}
        result = client.post("/api/local/backup/restore", files=files,
                             data={"passphrase": PASSPHRASE, "confirmation": "RESTORE"}, headers=headers)
        assert result.status_code == 400
        assert client.get("/api/local/backup/preview").status_code == 503
