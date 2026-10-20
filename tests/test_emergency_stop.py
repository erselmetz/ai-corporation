from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.application.services.capability_authorization import (
    CapabilityAuthorizationService,
    CapabilityDefinition,
    DEFAULT_CAPABILITY_AUTHORIZATION,
)
from app.application.services.emergency_stop import EmergencyStopService
from app.local import create_local_app


PASSWORD = "emergency-stop-test-password"
ORIGIN = "http://127.0.0.1:8000"


def test_emergency_stop_blocks_new_actions_but_keeps_stop_status_revoke_and_resume():
    policy = CapabilityAuthorizationService((*DEFAULT_CAPABILITY_AUTHORIZATION.definitions,
        CapabilityDefinition("optional.inspect", "principal", frozenset({"optional:inspect"}),
                             "low", grant_modes=frozenset({"session"}))))
    stop_service = EmergencyStopService(clock=lambda: datetime(2035, 1, 1, tzinfo=timezone.utc))
    app = create_local_app(password=PASSWORD, application_service=MagicMock(),
                           capability_authorization_service=policy,
                           emergency_stop_service=stop_service)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50145)) as client:
        assert client.get("/api/local/emergency-stop").status_code == 401
        assert client.post("/api/local/login", json={"password": PASSWORD},
                           headers={"Origin": ORIGIN}).status_code == 200
        session = client.get("/api/local/session").json()
        headers = {"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]}

        assert client.put("/api/capabilities/grants/policy/optional.inspect", headers=headers,
                          json={"enabled": True}).status_code == 200
        grant_response = client.post("/api/capabilities/grants", headers=headers, json={
            "capability_id": "optional.inspect", "scope_type": "principal",
            "scope_id": "local-owner", "ttl_seconds": 120,
        })
        assert grant_response.status_code == 201
        grant_id = grant_response.json()["grant_id"]

        stopped = client.post("/api/local/emergency-stop/stop", headers=headers, json={})
        assert stopped.status_code == 200
        assert stopped.json()["stopped"] is True
        assert stopped.json()["persistence"] == "process_only"
        assert client.post("/api/local/voice/cloud-budget", headers=headers,
                           json={"ceiling_cents": 10}).status_code == 423
        status = client.get("/api/local/emergency-stop")
        assert status.status_code == 200
        assert status.json()["stopped"] is True
        assert "capability-emergency:manage" in status.json()["active_capabilities"]
        assert status.json()["capture"]["screen"] == "page-reported"
        assert any(item["grant_id"] == grant_id and item["expires_at"]
                   for item in status.json()["session_grants"])

        revoked = client.post(f"/api/capabilities/grants/{grant_id}/revoke",
                              headers=headers, json={})
        assert revoked.status_code == 200
        assert revoked.json()["status"] == "revoked"
        assert client.post("/api/local/emergency-stop/resume", headers=headers,
                           json={"confirmed": False}).status_code == 409
        resumed = client.post("/api/local/emergency-stop/resume", headers=headers,
                              json={"confirmed": True})
        assert resumed.status_code == 200
        assert resumed.json()["stopped"] is False
        assert client.post("/api/local/voice/cloud-budget", headers=headers,
                           json={"ceiling_cents": 10}).status_code == 200


def test_emergency_stop_is_process_local_and_idempotent():
    now = datetime(2035, 1, 1, tzinfo=timezone.utc)
    service = EmergencyStopService(clock=lambda: now)
    assert service.snapshot()["stopped"] is False
    first = service.stop()
    assert service.stop() == first
    assert service.snapshot()["stopped_at"] == now.isoformat()
    assert EmergencyStopService().snapshot()["stopped"] is False
    assert service.resume()["stopped"] is False


def test_capability_controls_are_in_settings_and_chat_stays_minimal():
    app = create_local_app(password=PASSWORD, application_service=MagicMock())
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50146)) as client:
        dashboard = client.get("/ui").text
        chat = client.get("/ui/chat").text
        settings = client.get("/ui/settings/capabilities").text
    assert 'id="emergency-stop"' not in dashboard
    for page in (settings,):
        assert 'id="emergency-stop"' in page
        assert 'id="emergency-resume"' in page
        assert 'id="emergency-activity"' in page
        assert 'id="capability-indicators"' in page
        assert 'id="capability-microphone-activity" role="status"' not in page
        assert 'id="capability-camera-activity" role="status"' not in page
        assert 'id="capability-screen-activity" role="status"' not in page
        assert 'id="capability-playback-activity" role="status"' not in page
        assert 'id="emergency-activity" role="status" aria-live="polite"' in page
        assert 'id="capability-microphone-activity"' in page
        assert 'id="capability-microphone-state"' in page
        assert 'id="capability-microphone-stop" type="button" hidden>Stop / cancel voice</button>' in page
        assert "Voice off; permission not checked. Capture limit: 10 seconds." in page
        assert 'id="capability-playback-state"' in page
        assert 'id="capability-playback-stop" type="button" hidden>Stop local playback and clear queue</button>' in page
        assert 'id="capability-camera-activity"' in page
        assert 'id="capability-screen-activity"' in page
        assert 'id="capability-playback-activity"' in page
        assert 'id="capability-automation-support"' in page
        assert "No in-app automation execution control is exposed" in page
        assert 'id="emergency-permissions"' in page
        assert 'id="emergency-grants"' in page
        assert "provider transfer requires per-turn consent" in page
        assert "Session permissions end at sign-out or session expiry" in page
        assert "/ui/static/emergency-stop.mjs" in page
    assert "Optional local media packs are managed in Capabilities" in dashboard
    assert 'id="emergency-stop"' not in chat
    assert 'id="capability-indicators"' not in chat
    assert 'id="chat-emergency-stop"' in chat
    assert 'id="chat-add-image-action"' in chat
    assert 'id="chat-camera-action"' in chat
    assert 'id="chat-screen-action"' in chat
    assert 'id="chat-knowledge-menu-toggle"' in chat
    assert 'id="chat-header-model"' in chat
    composer = chat[chat.index('<form id="chat-form"'):]
    composer = composer[:composer.index('</form>')]
    assert composer.index('id="chat-agent"') < composer.index('id="chat-mic"') < composer.index('id="chat-send"')
    assert "Capability controls" not in chat
    assert 'href="/ui/settings/capabilities"' in chat
    assert 'class="navigation shared-navigation"' not in chat
    assert 'aria-label="Advanced pages"' in chat
    assert chat.index('id="chat-refresh"') > chat.index('<summary>Advanced</summary>')
    assert chat.index('id="chat-close"') > chat.index('<summary>Advanced</summary>')
    assert 'id="voice-budget-form"' in chat
    assert 'id="emergency-permissions"' not in chat
    assert 'id="emergency-stop"' not in chat
    assert 'id="emergency-stop"' in settings
