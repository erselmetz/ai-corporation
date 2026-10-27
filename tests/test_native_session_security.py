"""Native session security retained from the retired Electron transport tests."""
from fastapi.testclient import TestClient
from app.local import create_local_app
from app.local_owner_credential import OwnerCredentialError

PASSWORD='desktop-test-owner-password'

def test_local_web_runtime_keeps_original_routes_and_default_csp_without_desktop_ui():
    app = create_local_app(password=PASSWORD)
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50100)) as client:
        assert client.get("/ui/login").status_code == 200
        assert client.get("/desktop/").status_code == 404
        response = client.get("/ui/login")
        assert "script-src 'self'" in response.headers["content-security-policy"]
        assert "sha256-" not in response.headers["content-security-policy"]


def test_native_session_token_authenticates_only_when_present_and_origin_is_valid():
    from starlette.testclient import TestClient
    token = "b" * 43
    app = create_local_app(password=None, desktop_session_token=token, origin="http://127.0.0.1:8765", desktop_mode=True)
    with TestClient(app, base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50100)) as client:
        assert client.get("/api/local/session", headers={"Origin": "http://127.0.0.1:8765"}).status_code == 401
        client.cookies.set("ersel_local_session", token)
        response = client.get("/api/local/session", headers={"Origin": "http://127.0.0.1:8765"})
        assert response.status_code == 200
        assert "owner-lock:manage" in response.json()["permissions"]
        assert client.get("/api/local/session", headers={"Origin": "http://evil.example"}).status_code == 403


def test_optional_desktop_password_lock_can_be_enabled_and_removed_with_owner_password(monkeypatch):
    class CredentialStore:
        enabled = False
        def __init__(self): pass
        def exists(self): return self.enabled
        def create(self, password, confirmation):
            if password != confirmation: raise OwnerCredentialError("The password entries do not match")
            self.enabled = True
        def remove(self, password):
            if password != PASSWORD: raise OwnerCredentialError("Owner password did not match")
            self.enabled = False
    monkeypatch.setattr("app.local_owner_credential.LocalOwnerCredentialStore", CredentialStore)
    app = create_local_app(password=PASSWORD, origin="http://127.0.0.1:8765", desktop_mode=True)
    app.state.restore_local_first_run = lambda _corporation: None
    with __import__("starlette.testclient", fromlist=["TestClient"]).TestClient(
        app, base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50100)) as client:
        session = client.post("/api/local/login", json={"password": PASSWORD}, headers={"Origin": "http://127.0.0.1:8765"})
        assert session.status_code == 200
        csrf = client.get("/api/local/session").json()["csrf"]
        headers = {"Origin": "http://127.0.0.1:8765", "X-Local-CSRF": csrf}
        assert client.get("/api/local/desktop-lock").json() == {"enabled": False}
        enabled = client.post("/api/local/desktop-lock", json={"enabled": True, "password": PASSWORD,
            "confirmation": PASSWORD}, headers=headers)
        assert enabled.status_code == 200 and enabled.json() == {"enabled": True}
        disabled = client.post("/api/local/desktop-lock", json={"enabled": False, "password": PASSWORD,
            "confirmation": None}, headers=headers)
        assert disabled.status_code == 200 and disabled.json() == {"enabled": False}
