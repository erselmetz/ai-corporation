import base64
import hashlib
import io
import json
import re
import time
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.desktop_runtime import DesktopStartupError, _prepare_owner, run_backend
from app.local import create_local_app
from app.local_owner_credential import OwnerCredentialError


PASSWORD = "desktop-test-owner-password"


class MemoryCredentialStore:
    def __init__(self, *, configured=False, password=None):
        self.configured = configured
        self.password = password
        self.created = 0

    def exists(self):
        return self.configured

    def create(self, password, confirmation):
        if password != confirmation:
            raise OwnerCredentialError("The password entries do not match")
        self.configured = True
        self.password = password
        self.created += 1

    def verify(self, password):
        return password == self.password


def test_desktop_static_export_uses_local_api_origin_and_hash_scoped_csp(tmp_path):
    html = """<!doctype html><html><head><script>window.__exported = true;</script></head>
      <body><a href='/ui/chat'>Chat</a></body></html>"""
    (tmp_path / "index.html").write_text(html, encoding="utf-8")
    app = create_local_app(password=PASSWORD, origin="http://127.0.0.1:8765", desktop_ui_dir=tmp_path)

    with TestClient(app, base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50100)) as client:
        page = client.get("/desktop/")
        assert page.status_code == 200
        assert "href='/ui/chat'" in page.text
        match = re.search(r"<script>(.*?)</script>", html)
        expected = base64.b64encode(hashlib.sha256(match.group(1).encode()).digest()).decode()
        assert f"'sha256-{expected}'" in page.headers["content-security-policy"]
        assert "'unsafe-inline'" not in page.headers["content-security-policy"]
        assert client.get("/ui/login").status_code == 200
        assert client.get("/health").status_code == 200
        assert client.get("/").status_code == 200


def test_local_web_runtime_keeps_original_routes_and_default_csp_without_desktop_ui():
    app = create_local_app(password=PASSWORD)
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50100)) as client:
        assert client.get("/ui/login").status_code == 200
        assert client.get("/desktop/").status_code == 404
        response = client.get("/ui/login")
        assert "script-src 'self'" in response.headers["content-security-policy"]
        assert "sha256-" not in response.headers["content-security-policy"]


def test_built_next_export_assets_are_served_from_the_local_api_origin():
    export = Path(__file__).resolve().parents[1] / "desktop-ui" / "out"
    if not (export / "index.html").is_file():
        pytest.skip("Build the Windows desktop Next.js export before checking packaged assets")
    app = create_local_app(password=PASSWORD, origin="http://127.0.0.1:8765", desktop_ui_dir=export)
    with TestClient(app, base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50100)) as client:
        response = client.get("/desktop/")
        assert response.status_code == 200
        assert "sha256-" in response.headers["content-security-policy"]
        assert "unsafe-inline" not in response.headers["content-security-policy"]
        assert "https://" not in response.text
        assets = re.findall(r'(?:src|href)="([^\"]+)"', response.text)
        local_assets = [asset for asset in assets if "/_next/static/" in asset]
        assert local_assets
        assert all(asset.startswith("/desktop/_next/static/") for asset in local_assets)
        for asset in local_assets:
            response = client.get(asset)
            assert response.status_code == 200
            if asset.endswith(".css"):
                assert "--ui-bg:#080c13" in response.text
                assert "rail-group-label" in response.text
                assert "prefers-reduced-motion" in response.text
        assert "PRIMARY" in response.text or any(
            asset.endswith(".js") and "PRIMARY" in client.get(asset).text
            for asset in local_assets
        )


def test_navigation_is_present_after_transition_from_exported_home_to_python_chat():
    export = Path(__file__).resolve().parents[1] / "desktop-ui" / "out"
    app = create_local_app(password=PASSWORD, origin="http://127.0.0.1:8765",
                           desktop_ui_dir=export)
    with TestClient(app, base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50100)) as client:
        home = client.get("/desktop/")
        assert home.status_code == 200
        assert 'id="desktop-navigation"' in home.text
        assert 'href="/ui/chat"' in home.text or any(
            asset.endswith(".js") and 'href:"/ui/chat"' in client.get(asset).text
            for asset in re.findall(r'(?:src|href)="([^\"]+/_next/[^\"]+\.js)"', home.text)
        )

        chat = client.get("/ui/chat?conversation=previously-created")
        assert chat.status_code == 200
        assert 'id="chat-sidebar"' in chat.text
        assert 'id="shared-navigation-toggle"' in chat.text
        assert 'src="/ui/static/navigation.mjs"' in chat.text
        assert 'href="/ui/chat" aria-current="page"' in chat.text
        assert 'aria-label="Chat navigation"' in chat.text
        assert "script-src 'self'" in chat.headers["content-security-policy"]
        assert client.get("/ui/static/navigation.mjs").status_code == 200


def test_electron_design_tokens_are_generated_from_python_canonical_source():
    root = Path(__file__).resolve().parents[1]
    canonical = (root / "app" / "webui" / "static" / "design-tokens.css").read_text(encoding="utf-8")
    generated = (root / "desktop-ui" / "src" / "app" / "design-tokens.css").read_text(encoding="utf-8")
    assert generated == canonical


def test_desktop_owner_setup_creates_only_through_existing_credential_api():
    store = MemoryCredentialStore()
    assert _prepare_owner({"password": PASSWORD, "confirmation": PASSWORD}, store) == PASSWORD
    assert store.created == 1
    assert _prepare_owner({"password": PASSWORD, "confirmation": ""}, store) == PASSWORD
    assert store.created == 1
    with pytest.raises(DesktopStartupError, match="did not match"):
        _prepare_owner({"password": "different-owner-password", "confirmation": ""}, store)


def test_token_only_startup_is_desktop_scoped_and_password_lock_stays_enforced():
    token = "a" * 43
    assert _prepare_owner({"password": None, "session_token": token}, MemoryCredentialStore()) is None
    locked = MemoryCredentialStore(configured=True, password=PASSWORD)
    with pytest.raises(DesktopStartupError, match="password"):
        _prepare_owner({"password": None, "session_token": token}, locked)


def test_electron_session_token_authenticates_only_when_present_and_origin_is_valid():
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


def test_desktop_first_run_requires_matching_confirmation():
    with pytest.raises(DesktopStartupError, match="do not match"):
        _prepare_owner({"password": PASSWORD, "confirmation": "another-password"}, MemoryCredentialStore())


def test_desktop_sidecar_owns_only_loopback_backend_and_stops_through_parent_pipe(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><h1>test</h1>", encoding="utf-8")
    owner_store = MemoryCredentialStore()
    lease_state = {"held": False}

    class Lease:
        def acquire(self):
            assert not lease_state["held"]
            lease_state["held"] = True

        def release(self):
            lease_state["held"] = False

    class Server:
        should_exit = False
        started = False

        def run(self, sockets):
            assert sockets[0].getsockname()[0] == "127.0.0.1"
            assert sockets[0].getsockname()[1] != 0
            self.started = True
            deadline = time.monotonic() + 2
            while not self.should_exit and time.monotonic() < deadline:
                time.sleep(0.002)
            assert self.should_exit

    server = Server()
    class ParentPipe:
        first = True

        def readline(self, _limit):
            if self.first:
                self.first = False
                return (json.dumps({"password": PASSWORD, "confirmation": PASSWORD}) + "\n").encode()
            deadline = time.monotonic() + 2
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.002)
            return b'{"command":"shutdown"}\n'

    stream = ParentPipe()
    run_backend(port=0, ui_dir=tmp_path, stdin=stream, credential_store=owner_store,
                lease_factory=Lease, server_factory=lambda _app, _port: server)
    assert owner_store.created == 1
    assert lease_state["held"] is False


def test_invalid_startup_payload_cannot_start_backend_or_hold_single_instance(tmp_path):
    leases = []

    class Lease:
        def acquire(self):
            leases.append("acquired")

        def release(self):
            leases.append("released")

    with pytest.raises(DesktopStartupError, match="invalid"):
        run_backend(port=0, ui_dir=tmp_path, stdin=io.BytesIO(b"{\"password\":\"x\",\"extra\":1}\n"),
                    credential_store=MemoryCredentialStore(), lease_factory=Lease)
    assert leases == []
