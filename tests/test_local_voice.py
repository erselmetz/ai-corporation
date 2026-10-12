from __future__ import annotations

from io import BytesIO
import wave

import httpx
from fastapi.testclient import TestClient

from app.local import create_local_app

PASSWORD = "voice-test-owner-passphrase"
ORIGIN = "http://127.0.0.1:8000"
KEY = "AIza" + "V" * 35


def wav(seconds=1):
    buffer = BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16_000)
        output.writeframes(b"\0" * (seconds * 32_000))
    return buffer.getvalue()


class Connection:
    def __init__(self):
        self.active = False
        self.calls = 0

    def begin_voice_call(self):
        self.active = True
        self.calls += 1
        return KEY

    def end_voice_call(self):
        self.active = False


def signed_in(client):
    response = client.post("/api/local/login", json={"password": PASSWORD},
                           headers={"Origin": ORIGIN})
    assert response.status_code == 200
    session = client.get("/api/local/session").json()
    return {"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]}


def app_for(manager):
    return create_local_app(password=PASSWORD, origin=ORIGIN,
                            voice_connection_manager=manager)


def test_cloud_voice_requires_session_csrf_explicit_consent_and_budget(monkeypatch):
    manager = Connection()
    calls = []
    real_client = httpx.Client

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "Turn on the lights"}]}}]})

    def client_factory(**options):
        return real_client(transport=httpx.MockTransport(handler), **options)

    monkeypatch.setattr("app.integrations.gemini_voice.httpx.Client", client_factory)
    with TestClient(app_for(manager), base_url=ORIGIN, client=("127.0.0.1", 51000)) as client:
        headers = signed_in(client)
        status = client.get("/api/local/voice", headers=headers)
        assert status.status_code == 200
        assert status.json()["audio_retention"] == "none_by_application"
        assert status.json()["cloud_budget"]["configured"] is False

        assert client.post("/api/local/voice/cloud-budget", headers=headers,
                           json={"ceiling_cents": 1}).status_code == 200
        assert client.post("/api/local/voice/cloud-budget", headers=headers,
                           json={"ceiling_cents": 2}).status_code == 409

        # An origin and CSRF token are required even when cloud consent is absent.
        denied = client.post("/api/local/voice/transcribe", headers={**headers, "Content-Type": "audio/wav"},
                             content=wav())
        assert denied.status_code == 403
        assert "Explicit per-use consent" in denied.json()["detail"]
        assert manager.calls == 0
        assert calls == []

        # CSRF is checked before the request body can reach the provider.
        no_csrf = client.post("/api/local/voice/transcribe",
                              headers={"Origin": ORIGIN, "Content-Type": "audio/wav",
                                       "X-Cloud-Consent": "true"}, content=wav())
        assert no_csrf.status_code == 403
        assert manager.calls == 0

        response = client.post("/api/local/voice/transcribe",
                               headers={**headers, "Content-Type": "audio/wav",
                                        "X-Cloud-Consent": "true"}, content=wav())
        assert response.status_code == 200
        assert response.json() == {"transcript": "Turn on the lights", "reserved_cents": 1,
                                   "remaining_cents": 0, "audio_retained": False}
        assert KEY not in response.text
        assert len(calls) == 1
        assert calls[0].headers["x-goog-api-key"] == KEY
        assert manager.active is False

        exhausted = client.post("/api/local/voice/transcribe",
                                headers={**headers, "Content-Type": "audio/wav",
                                         "X-Cloud-Consent": "true"}, content=wav())
        assert exhausted.status_code == 409
        assert "ceiling is exhausted" in exhausted.json()["detail"]
        assert len(calls) == 1


def test_cloud_voice_rejects_audio_without_using_budget_or_provider():
    manager = Connection()
    with TestClient(app_for(manager), base_url=ORIGIN, client=("127.0.0.1", 51001)) as client:
        headers = signed_in(client)
        client.post("/api/local/voice/cloud-budget", headers=headers,
                    json={"ceiling_cents": 1})
        wrong_type = client.post("/api/local/voice/transcribe",
                                 headers={**headers, "Content-Type": "audio/webm",
                                          "X-Cloud-Consent": "true"}, content=b"fake")
        assert wrong_type.status_code == 415
        invalid = client.post("/api/local/voice/transcribe",
                              headers={**headers, "Content-Type": "audio/wav",
                                       "X-Cloud-Consent": "true"}, content=b"not wave")
        assert invalid.status_code == 422
        assert manager.calls == 0


def test_default_api_does_not_expose_owner_voice_route():
    from app.api.app import create_app

    with TestClient(create_app(), base_url=ORIGIN) as client:
        assert client.get("/api/local/voice").status_code == 404
