from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import sqlite3

from fastapi.testclient import TestClient
import pytest

from app.api.chat_history import get_history_now
from app.api.security import AuthenticatedPrincipal
from app.application.services import chat_history as history_module
from app.database.connection import get_connection
from app.local import create_local_app
from app.providers import OllamaProvider
from app.runtime.factory import create_corporation_runtime

ORIGIN = "http://127.0.0.1:8000"
PASSWORD = "test-only-owner-passphrase"


@pytest.fixture
def replies(monkeypatch):
    calls = []

    def generate(self, *args, **kwargs):
        calls.append(1)
        return "Durable reply."

    monkeypatch.setattr(OllamaProvider, "generate", generate)
    return calls


@contextmanager
def process(clock=None):
    """One application run; a new call simulates a restart over the same database."""
    runtime = create_corporation_runtime()
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    clock = clock if clock is not None else {"now": datetime.now(timezone.utc)}
    app.dependency_overrides[get_history_now] = lambda: clock["now"]
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50300)) as client:
        client.post("/api/local/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN})
        csrf = client.get("/api/local/session").json()["csrf"]
        yield client, {"Origin": ORIGIN, "X-Local-CSRF": csrf}, clock, app


def start(client, headers):
    return client.post("/api/chat/conversations", json={"agent_id": "local_worker"},
                       headers=headers).json()["conversation"]["id"]


def say(client, headers, cid, text="remember this"):
    return client.post(f"/api/chat/conversations/{cid}/messages", json={"text": text}, headers=headers)


def enable(client, headers, clock, cid, days=7, opt_in=True):
    return client.post("/api/chat/history", headers=headers, json={
        "conversation_id": cid, "history_opt_in": opt_in,
        "expires_at": (clock["now"] + timedelta(days=days)).isoformat()})


def remove(client, headers, path):
    return client.request("DELETE", path, headers=headers, json={})


def test_history_is_off_by_default_and_needs_consent_and_bounded_expiry(replies):
    with process() as (client, headers, clock, _):
        cid = start(client, headers)
        say(client, headers, cid)
        assert client.get("/api/chat/history").json()["items"] == []
        assert enable(client, headers, clock, cid, opt_in=False).status_code == 422
        assert enable(client, headers, clock, cid, days=91).status_code == 422
        assert enable(client, headers, clock, "missing").status_code == 404
        assert enable(client, headers, clock, cid).status_code == 200
        assert enable(client, headers, clock, cid).status_code == 422
    with process() as (client, headers, clock, _):
        assert client.get("/api/chat/history").json()["items"][0]["id"] == cid


def test_restart_recovers_read_only_history_without_replay(replies):
    with process() as (client, headers, clock, _):
        cid = start(client, headers)
        enable(client, headers, clock, cid)
        assert say(client, headers, cid).status_code == 200
        live = client.get(f"/api/chat/history/{cid}").json()
        assert live["live"] is True and live["read_only"] is False
        calls_before = len(replies)
    with process() as (client, headers, clock, _):
        recovered = client.get(f"/api/chat/history/{cid}").json()
        assert recovered["read_only"] is True and "read-only" in recovered["recovery_notice"]
        assert [m["role"] for m in recovered["messages"]] == ["user", "assistant"]
        assert all(m["status"] == "completed" for m in recovered["messages"])
        assert say(client, headers, cid).status_code == 404
        assert len(replies) == calls_before


def test_interrupted_turn_is_uncertain_needs_review_and_is_never_replayed(replies):
    with process() as (client, headers, clock, _):
        cid = start(client, headers)
        enable(client, headers, clock, cid)
        say(client, headers, cid, "first")
    connection = get_connection()
    with connection:
        connection.execute("UPDATE chat_history_messages SET status = 'pending' WHERE role = 'user'")
    connection.close()
    calls = len(replies)
    with process() as (client, headers, clock, _):
        listed = client.get("/api/chat/history").json()["items"][0]
        assert listed["needs_review"] == 1
        detail = client.get(f"/api/chat/history/{cid}").json()
        pending = detail["messages"][0]
        assert pending["status"] == "uncertain" and pending["needs_review"] is True
        url = f"/api/chat/history/{cid}/messages/{pending['id']}/review"
        assert client.post(url, json={"acknowledge_uncertain": False}, headers=headers).status_code == 422
        reviewed = client.post(url, json={"acknowledge_uncertain": True}, headers=headers).json()
        assert reviewed["messages"][0]["status"] == "interrupted"
        assert reviewed["messages"][0]["review"] == "owner-reviewed"
        assert client.post(url, json={"acknowledge_uncertain": True}, headers=headers).status_code == 422
        assert client.get("/api/chat/history").json()["items"][0]["needs_review"] == 0
    assert len(replies) == calls


def test_expiry_purges_stored_messages(replies):
    clock = {"now": datetime.now(timezone.utc)}
    with process(clock) as (client, headers, clock, _):
        cid = start(client, headers)
        enable(client, headers, clock, cid, days=1)
        say(client, headers, cid)
        clock["now"] += timedelta(days=2)
        assert client.get("/api/chat/history").json()["items"] == []
        assert client.get(f"/api/chat/history/{cid}").status_code == 404
    connection = get_connection()
    assert connection.execute("SELECT COUNT(*) FROM chat_history_messages").fetchone()[0] == 0
    connection.close()


def test_deletion_is_scoped_to_one_conversation_and_to_the_owner(replies):
    with process() as (client, headers, clock, app):
        a, b = start(client, headers), start(client, headers)
        for cid in (a, b):
            enable(client, headers, clock, cid)
            say(client, headers, cid)
        assert remove(client, headers, f"/api/chat/history/{a}").status_code == 200
        assert [i["id"] for i in client.get("/api/chat/history").json()["items"]] == [b]
        assert remove(client, headers, f"/api/chat/history/{a}").status_code == 404
        connection = get_connection()
        connection.execute("UPDATE chat_history SET owner_id = 'someone-else' WHERE id = ?", (b,))
        connection.commit()
        connection.close()
        assert client.get("/api/chat/history").json()["items"] == []
        assert client.get(f"/api/chat/history/{b}").status_code == 404
        assert remove(client, headers, f"/api/chat/history/{b}").status_code == 404
        assert remove(client, headers, "/api/chat/history").json()["deleted"] == 0
        connection = get_connection()
        assert connection.execute("SELECT COUNT(*) FROM chat_history").fetchone()[0] == 1
        connection.close()


def test_non_durable_conversations_store_nothing_and_close_is_recorded(replies):
    with process() as (client, headers, clock, _):
        plain, durable = start(client, headers), start(client, headers)
        say(client, headers, plain)
        enable(client, headers, clock, durable)
        client.post(f"/api/chat/conversations/{durable}/close", json={}, headers=headers)
        assert client.get(f"/api/chat/history/{durable}").json()["status"] == "closed"
    connection = get_connection()
    assert connection.execute("SELECT COUNT(*) FROM chat_history_messages WHERE conversation_id = ?", (plain,)).fetchone()[0] == 0
    connection.close()


def test_persistence_failure_before_provider_call_fails_closed(replies, monkeypatch):
    with process() as (client, headers, clock, app):
        cid = start(client, headers)
        enable(client, headers, clock, cid)

        def broken(self, *args, **kwargs):
            raise sqlite3.OperationalError("disk full")

        monkeypatch.setattr(history_module, "get_connection", lambda: (_ for _ in ()).throw(sqlite3.OperationalError("disk full")))
        before = len(replies)
        response = say(client, headers, cid)
        assert response.status_code == 503 and "could not be saved" in response.json()["detail"]
        assert len(replies) == before


def test_post_call_persistence_failure_leaves_turn_uncertain(replies, monkeypatch):
    with process() as (client, headers, clock, _):
        cid = start(client, headers)
        enable(client, headers, clock, cid)
        original = history_module.ChatHistoryService.record_message
        state = {"n": 0}

        def flaky(self, *args, **kwargs):
            state["n"] += 1
            if state["n"] == 2:
                raise history_module.ChatHistoryError("Chat history could not be saved")
            return original(self, *args, **kwargs)

        monkeypatch.setattr(history_module.ChatHistoryService, "record_message", flaky)
        assert say(client, headers, cid).status_code == 503
    with process() as (client, headers, clock, _):
        r = client.get(f"/api/chat/history/{cid}")
        user = r.json()["messages"][0]
        assert user["status"] == "uncertain" and user["needs_review"] is True


def test_migration_from_v1_preserves_rows_and_adds_provenance():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    history_module.apply_migrations(connection, up_to=1)
    connection.execute("INSERT INTO chat_history VALUES ('c','corp','owner','agent','open','t','t2')")
    connection.execute("INSERT INTO chat_history_messages VALUES ('c',0,'m','user','hello','pending','t')")
    connection.commit()
    history_module.apply_migrations(connection)
    row = connection.execute("SELECT * FROM chat_history").fetchone()
    assert (row["owner_id"], row["origin"]) == ("owner", "owned-chat")
    assert connection.execute("SELECT status, review FROM chat_history_messages").fetchone()[:] == ("pending", None)
    assert connection.execute("SELECT version FROM chat_history_schema").fetchone()[0] == 2
    history_module.apply_migrations(connection)
    connection.execute("UPDATE chat_history_schema SET version = 99")
    with pytest.raises(history_module.ChatHistoryError):
        history_module.apply_migrations(connection)


def test_permissions(replies):
    with process() as (client, headers, clock, app):
        cid = start(client, headers)
        app.state.authentication_backend.principal = AuthenticatedPrincipal("local-owner", frozenset({"chat:read"}))
        assert enable(client, headers, clock, cid).status_code == 403
        assert remove(client, headers, f"/api/chat/history/{cid}").status_code == 403
        assert client.get("/api/chat/history").status_code == 200