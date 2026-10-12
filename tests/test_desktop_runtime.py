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
            assert client.get(asset).status_code == 200


def test_desktop_owner_setup_creates_only_through_existing_credential_api():
    store = MemoryCredentialStore()
    assert _prepare_owner({"password": PASSWORD, "confirmation": PASSWORD}, store) == PASSWORD
    assert store.created == 1
    assert _prepare_owner({"password": PASSWORD, "confirmation": ""}, store) == PASSWORD
    assert store.created == 1
    with pytest.raises(DesktopStartupError, match="did not match"):
        _prepare_owner({"password": "different-owner-password", "confirmation": ""}, store)


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
