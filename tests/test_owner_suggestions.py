from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.api.security import AuthenticatedPrincipal
from app.application.services.owner_suggestions import (
    OwnerSuggestionService,
    OwnerSuggestionsError,
    SuggestionPreferences,
)
from app.local import create_local_app
from app.database import connection as db

PASSWORD = "test-only-owner-passphrase"
ORIGIN = "http://127.0.0.1:8000"
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


class WorkflowSource:
    def __init__(self, reports):
        self.reports = reports
        self.calls = 0

    def list(self):
        self.calls += 1
        return self.reports


class Application:
    def __init__(self, reports):
        self.source = WorkflowSource(reports)

    def workflow_review(self):
        return self.source


def reports(states):
    items = [
        {"id": f"item-{index}", "state": state, "uncertain": uncertain,
         "reason": "api_key=DO_NOT_LEAK", "prompt": "private prompt", "output": "private output"}
        for index, (state, uncertain) in enumerate(states)
    ]
    return [{"id": "workflow-1", "title": "secret title", "created_at": NOW.isoformat(), "items": items,
             "events": [{"item_id": item["id"], "at": NOW.isoformat()} for item in items]}]


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "suggestions.sqlite3")


def test_suggestions_are_disabled_by_default_and_do_not_read_workflows(isolated_db):
    service = OwnerSuggestionService()
    source = WorkflowSource(reports([("blocked", False)]))
    assert service.get_preferences("owner") == SuggestionPreferences()
    result = service.list_suggestions("owner", source, now=NOW)
    assert result["enabled"] is False and result["suggestions"] == []
    assert source.calls == 0


def test_enabled_suggestions_use_only_bounded_current_workflow_state(isolated_db):
    service = OwnerSuggestionService()
    service.update_preferences("owner", {"enabled": True})
    source = WorkflowSource(reports([("blocked", False), ("failed", False),
                                     ("interrupted", False), ("running", True),
                                     ("review", False), ("approved", False), ("approved", True)]))
    result = service.list_suggestions("owner", source, now=NOW)
    assert source.calls == 1
    assert len(result["suggestions"]) == 5
    assert [item["state"] for item in result["suggestions"]] == [
        "blocked", "failed", "interrupted", "running", "review"]
    assert "unknown outcome" in result["suggestions"][3]["title"].lower()
    rendered = str(result)
    assert "DO_NOT_LEAK" not in rendered and "private prompt" not in rendered
    assert "private output" not in rendered and "secret title" not in rendered
    assert all(item["source"]["kind"] == "local workflow record" for item in result["suggestions"])
    assert all(item["observed_at"] == NOW.isoformat() for item in result["suggestions"])
    assert all(item["source"]["last_changed_at"] == NOW.isoformat() for item in result["suggestions"])
    assert all(item["href"] == "/ui/workflow-map" for item in result["suggestions"])


def test_suggestion_results_are_bounded(isolated_db):
    service = OwnerSuggestionService()
    service.update_preferences("owner", {"enabled": True})
    source = WorkflowSource(reports([("blocked", False)] * 15))
    assert len(service.list_suggestions("owner", source, now=NOW)["suggestions"]) == 10


def test_corrupt_dismissal_metadata_fails_open_to_current_suggestions_only(isolated_db):
    service = OwnerSuggestionService()
    service.update_preferences("owner", {"enabled": True})
    source = WorkflowSource(reports([("blocked", False)]))
    from app.database.connection import get_connection
    connection = get_connection()
    try:
        connection.execute("UPDATE owner_suggestion_preferences SET dismissed_json=? WHERE owner_id=?",
                           ('{"not":"a list"}', "owner"))
        connection.commit()
    finally:
        connection.close()
    assert len(service.list_suggestions("owner", source, now=NOW)["suggestions"]) == 1


def test_corrupt_dismissal_metadata_fails_open_to_current_suggestions_only(isolated_db):
    service = OwnerSuggestionService()
    service.update_preferences("owner", {"enabled": True})
    source = WorkflowSource(reports([("blocked", False)]))
    from app.database.connection import get_connection
    connection = get_connection()
    try:
        connection.execute("UPDATE owner_suggestion_preferences SET dismissed_json=? WHERE owner_id=?",
                           ('{"not":"a list"}', "owner"))
        connection.commit()
    finally:
        connection.close()
    assert len(service.list_suggestions("owner", source, now=NOW)["suggestions"]) == 1


def test_owner_settings_are_isolated_persistent_and_validate_quiet_period(isolated_db):
    service = OwnerSuggestionService()
    saved = service.update_preferences("owner-a", {
        "enabled": True, "quiet_start": "22:00", "quiet_end": "07:30"})
    assert saved.enabled and saved.quiet_start == "22:00" and saved.quiet_end == "07:30"
    assert service.get_preferences("owner-b") == SuggestionPreferences()
    assert service.get_preferences("owner-a") == saved
    for invalid in ({"enabled": 1}, {"quiet_end": None},
                    {"quiet_start": "22:00", "quiet_end": "22:00"},
                    {"quiet_start": "24:00", "quiet_end": "07:00"},
                    {"capability": "task:dispatch"}):
        with pytest.raises(OwnerSuggestionsError):
            service.update_preferences("owner-a", invalid)
    cleared = service.update_preferences("owner-a", {"quiet_start": None, "quiet_end": None})
    assert cleared.quiet_start == cleared.quiet_end == ""


def test_dismissal_is_owner_scoped_and_state_change_creates_a_new_suggestion(isolated_db):
    service = OwnerSuggestionService()
    service.update_preferences("owner-a", {"enabled": True})
    source = WorkflowSource(reports([("blocked", False)]))
    first = service.list_suggestions("owner-a", source, now=NOW)["suggestions"][0]
    assert service.dismiss("owner-a", first["id"], source, now=NOW)
    assert service.list_suggestions("owner-a", source, now=NOW)["suggestions"] == []
    assert service.list_suggestions("owner-b", source, now=NOW)["suggestions"] == []
    with pytest.raises(OwnerSuggestionsError):
        service.dismiss("owner-a", first["id"], source, now=NOW)
    source.reports = reports([("failed", False)])
    updated = service.list_suggestions("owner-a", source, now=NOW)["suggestions"]
    assert len(updated) == 1 and updated[0]["id"] != first["id"]


def test_local_api_requires_session_csrf_and_workflow_read_and_default_api_has_no_routes(isolated_db):
    app = create_local_app(password=PASSWORD, application_service=Application(reports([("blocked", False)])))
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50100)) as client:
        assert client.get("/api/local/suggestions/preferences").status_code == 401
        assert client.get("/api/local/suggestions").status_code == 401
        client.post("/api/local/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN})
        assert client.get("/api/local/suggestions/preferences").json()["preferences"]["enabled"] is False
        assert client.get("/api/local/suggestions").json()["suggestions"] == []
        assert client.put("/api/local/suggestions/preferences", json={"enabled": True},
                          headers={"Origin": ORIGIN}).status_code == 403
        csrf = client.get("/api/local/session").json()["csrf"]
        headers = {"Origin": ORIGIN, "X-Local-CSRF": csrf}
        assert client.put("/api/local/suggestions/preferences", json={"enabled": True},
                          headers=headers).status_code == 200
        quiet = client.put("/api/local/suggestions/preferences",
                           json={"quiet_start": "22:00", "quiet_end": "07:00"}, headers=headers)
        assert quiet.status_code == 200
        cleared = client.put("/api/local/suggestions/preferences",
                             json={"quiet_start": "", "quiet_end": ""}, headers=headers)
        assert cleared.status_code == 200
        result = client.get("/api/local/suggestions")
        assert result.status_code == 200 and len(result.json()["suggestions"]) == 1
        suggestion_id = result.json()["suggestions"][0]["id"]
        assert client.post(f"/api/local/suggestions/{suggestion_id}/dismiss", json={},
                           headers=headers).json() == {"dismissed": True}
        assert client.get("/api/local/suggestions").json()["suggestions"] == []
        client.app.state.authentication_backend.principal = AuthenticatedPrincipal(
            "local-owner", frozenset({"chat:read"}))
        assert client.get("/api/local/suggestions").status_code == 403
    with TestClient(create_app()) as client:
        assert client.get("/api/local/suggestions").status_code == 404
