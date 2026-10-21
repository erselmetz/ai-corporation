import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.api.app import create_app
from app.application.services.owner_preferences import (
    OwnerPreferences,
    OwnerPreferencesError,
    OwnerPreferencesService,
)
from app.local import create_local_app

PASSWORD = "test-only-owner-passphrase"
ORIGIN = "http://127.0.0.1:8000"


def _login(client):
    return client.post("/api/local/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN})


def test_preferences_are_owner_scoped_persistent_versioned_resettable_and_exportable():
    service = OwnerPreferencesService()
    assert service.get("owner-a") == OwnerPreferences()
    saved = service.update("owner-a", {"response_mode": "concise", "locale": "fil-PH",
                                        "detail_level": "detailed", "voice_mode": "local",
                                        "voice_language": "fil-PH", "voice_id": "Local Voice (English):device 1"})
    assert saved.response_mode == "concise"
    assert service.get("owner-b") == OwnerPreferences()
    assert service.get("owner-a") == saved
    exported = service.export("owner-a")
    assert exported["preferences"]["locale"] == "fil-PH"
    assert "until you reset" in exported["retention"]
    assert service.reset("owner-a") == OwnerPreferences()
    assert service.get("owner-a") == OwnerPreferences()


def test_preferences_reject_unknown_values_fields_and_unbounded_voice_ids():
    service = OwnerPreferencesService()
    for changes in ({"response_mode": "admin"}, {"capability": "desktop:act"}, {"voice_id": "x" * 161}, {"autonomy_level": "unrestricted"}):
        with pytest.raises(OwnerPreferencesError):
            service.update("owner", changes)


def test_local_preferences_require_owner_session_csrf_and_default_api_is_closed():
    app = create_local_app(password=PASSWORD)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50100)) as client:
        assert client.get("/api/local/preferences").status_code == 401
        assert _login(client).status_code == 200
        assert client.put("/api/local/preferences", json={"response_mode": "concise"},
                          headers={"Origin": ORIGIN}).status_code == 403
        csrf = client.get("/api/local/session").json()["csrf"]
        headers = {"Origin": ORIGIN, "X-Local-CSRF": csrf}
        saved = client.put("/api/local/preferences", json={"response_mode": "friendly", "locale": "fil-PH"}, headers=headers)
        assert saved.status_code == 200
        assert saved.json()["preferences"]["response_mode"] == "friendly"
        autonomy = client.put("/api/local/preferences", json={"autonomy_level": "ask_every_action"}, headers=headers)
        assert autonomy.status_code == 200
        assert autonomy.json()["preferences"]["autonomy_level"] == "ask_every_action"
        assert client.get("/api/local/preferences/export").json()["preferences"]["locale"] == "fil-PH"
        reset = client.post("/api/local/preferences/reset", json={}, headers=headers)
        assert reset.json()["preferences"]["locale"] == "en-US"
    with TestClient(create_app()) as client:
        assert client.get("/api/local/preferences").status_code == 404
        assert client.get("/api/chat/conversations").status_code == 401


def test_preference_schema_migration_is_additive_and_defaults_are_not_saved():
    from app.database.connection import get_connection
    OwnerPreferencesService().get("migration-setup")
    connection = get_connection()
    try:
        before = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert OwnerPreferencesService().get("migration-owner") == OwnerPreferences()
        after = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert before.issubset(after)
        assert "owner_preferences" in after
        assert connection.execute("SELECT 1 FROM owner_preferences WHERE owner_id='migration-owner'").fetchone() is None
    finally:
        connection.close()


def test_v1_preference_rows_migrate_with_safe_autonomy_default():
    import json
    from app.database.connection import get_connection
    OwnerPreferencesService().get("migration-setup")
    connection = get_connection()
    try:
        connection.execute("DELETE FROM owner_preferences")
        connection.execute("UPDATE owner_preferences_schema SET version=1")
        connection.execute("INSERT INTO owner_preferences(owner_id, preferences_json, version) VALUES (?, ?, ?)",
                           ("legacy", json.dumps({"response_mode": "concise", "version": 1}), 1))
        connection.commit()
    finally:
        connection.close()
    preferences = OwnerPreferencesService().get("legacy")
    assert preferences.response_mode == "concise"
    assert preferences.autonomy_level == "auto_safe"
    connection = get_connection()
    try:
        row = connection.execute("SELECT preferences_json, version FROM owner_preferences WHERE owner_id='legacy'").fetchone()
        assert row["version"] == 2
        assert json.loads(row["preferences_json"])["autonomy_level"] == "auto_safe"
    finally:
        connection.close()


def test_agent_runtime_enforces_autonomy_for_tool_calls():
    from app.agent_runtime import AgentRuntime, AgentRuntimeApprovalRequired, AgentRuntimeError
    from app.tools.registry import ToolRegistry
    from app.tools.base import Tool

    class ReadTool(Tool):
        def __init__(self):
            super().__init__("read", "Read", "read-only test", risk_class="read",
                             input_schema={"type": "object", "properties": {}, "additionalProperties": False})
        def execute(self): return "ok"

    registry = ToolRegistry()
    registry.register(ReadTool())
    runtime = AgentRuntime()
    def planner(observations):
        if observations:
            return {"type": "answer", "text": "ok"}
        return {"type": "tool", "tool_id": "read", "arguments": {}}
    with pytest.raises(AgentRuntimeError, match="Chat-only"):
        runtime.run_agentic("coordinator", planner, registry, autonomy_level="chat_only")
    with pytest.raises(AgentRuntimeApprovalRequired) as error:
        runtime.run_agentic("coordinator", planner, registry, autonomy_level="ask_every_action")
    assert error.value.risk_class == "read"
    assert error.value.preview
    assert runtime.run_agentic("coordinator", planner, registry, autonomy_level="auto_safe") == "ok"


def test_corrupt_autonomy_policy_fails_closed_for_agent_actions():
    from types import SimpleNamespace
    from app.api.chat import _autonomy_level, _require_action_policy, SendRequest
    from app.database.connection import get_connection
    service = OwnerPreferencesService()
    service.update("corrupt-owner", {"response_mode": "concise"})
    connection = get_connection()
    try:
        connection.execute("UPDATE owner_preferences SET preferences_json=? WHERE owner_id=?", ("{bad", "corrupt-owner"))
        connection.commit()
    finally:
        connection.close()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(owner_preferences_service=service)))
    assert _autonomy_level(request, "corrupt-owner") == "chat_only"
    with pytest.raises(Exception, match="Chat-only mode"):
        _require_action_policy(request, "corrupt-owner", SendRequest(
            text="search", knowledge_enabled=True,
            knowledge_scopes=[{"scope": "owner", "scope_id": ""}],
            knowledge_preview_digest="0" * 64))
    no_store = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    assert _autonomy_level(no_store, "owner") == "auto_safe"


def test_local_chat_uses_saved_bounded_presentation_without_changing_agent_or_consent():
    service = MagicMock()
    conversation = MagicMock()
    conversation.messages = []
    service.owned_chat.return_value.get.return_value = {
        "coordinator": MagicMock(provider="ollama"),
        "image_input_supported": False,
    }
    service.owned_chat.return_value.send.return_value = {"conversation": conversation}
    service.provider_requires_explicit_cloud_consent.return_value = False
    app = create_local_app(password=PASSWORD, application_service=service)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50100)) as client:
        assert _login(client).status_code == 200
        csrf = client.get("/api/local/session").json()["csrf"]
        headers = {"Origin": ORIGIN, "X-Local-CSRF": csrf}
        assert client.put("/api/local/preferences", json={"response_mode": "concise", "locale": "fil-PH"},
                          headers=headers).status_code == 200
        sent = client.post("/api/chat/conversations/conversation/messages", json={"text": "Kumusta?"}, headers=headers)
        assert sent.status_code == 200
    kwargs = service.owned_chat.return_value.send.call_args.kwargs
    assert kwargs["presentation_preferences"]["locale"] == "fil-PH"
    assert kwargs["presentation_preferences"]["style"] == "Prefer concise answers while preserving necessary facts and safety details."
    assert "authority" in kwargs["presentation_preferences"]["boundary"]
    service.owned_chat.return_value.get.assert_called_once_with("local-owner", "conversation")
    service.provider_requires_explicit_cloud_consent.assert_called_once_with("ollama")
