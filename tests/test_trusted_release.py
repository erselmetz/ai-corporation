import hashlib
import base64
import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.updates.trusted_release import (
    RELEASES_API,
    TrustedReleaseError,
    TrustedReleaseService,
    _compare_versions,
)


class UpdateAuth:
    def __init__(self, permissions):
        self.permissions = permissions

    def authenticate(self, _request):
        if self.permissions is None:
            return None
        from app.api import AuthenticatedPrincipal
        return AuthenticatedPrincipal("owner-test", frozenset(self.permissions))

    def require_csrf(self, request):
        if request.headers.get("x-local-csrf") != "owner-token":
            raise HTTPException(403, "Invalid request verification")


def signed_release(installer: bytes = b"test installer", *, config_from: int = 1, config_to: int = 1):
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    name = "ERSELMETZ-AI-Setup-0.2.0-win-x64.exe"
    manifest = json.dumps({
        "version": "0.2.0",
        "releaseNotes": "Verified test release notes.",
        "artifact": {"name": name, "sha256": hashlib.sha256(installer).hexdigest()},
        "configuration": {"fromVersion": config_from, "toVersion": config_to, "preview": "Existing app records remain unchanged."},
    }, separators=(",", ":")).encode()
    signature = base64.b64encode(private.sign(manifest))
    release = {"tag_name": "v0.2.0", "assets": [
        {"name": "erselmetz-release.json", "url": "https://api.github.com/repos/erselmetz/ai-corporation/releases/assets/1"},
        {"name": "erselmetz-release.sig", "url": "https://api.github.com/repos/erselmetz/ai-corporation/releases/assets/2"},
        {"name": name, "url": "https://api.github.com/repos/erselmetz/ai-corporation/releases/assets/3"},
    ]}
    assets = {1: manifest, 2: signature, 3: installer}

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == RELEASES_API:
            return httpx.Response(200, json=release, request=request)
        asset_id = request.url.path.rsplit("/", 1)[-1]
        if request.url.host == "api.github.com" and asset_id.isdigit() and int(asset_id) in assets:
            return httpx.Response(200, content=assets[int(asset_id)], request=request)
        return httpx.Response(404, request=request)

    return httpx.MockTransport(handler), public, release


def make_database(path: Path, *, version: int = 1):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS owner_data (id TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT OR REPLACE INTO owner_data VALUES ('preserve-me', 'durable')")
        connection.execute(f"PRAGMA user_version = {version}")


def test_release_check_verifies_pinned_key_and_returns_bounded_preview(tmp_path: Path):
    transport, public, _release = signed_release()
    service = TrustedReleaseService(tmp_path, database_path=tmp_path / "db.sqlite3", public_key_der=base64.b64encode(public).decode(), transport=transport)

    result = service.check()

    assert result.available is True
    assert result.version == "0.2.0"
    assert result.release_notes == "Verified test release notes."
    assert result.from_configuration == result.to_configuration == 1
    assert len(result.response()["installer_sha256"]) == 64


def test_tampered_signature_wrong_origin_and_tag_mismatch_fail_closed(tmp_path: Path):
    transport, public, release = signed_release()
    public_text = base64.b64encode(public).decode()
    manifest_service = TrustedReleaseService(tmp_path, database_path=tmp_path / "db.sqlite3", public_key_der=public_text, transport=transport)
    assert manifest_service.check().available
    with pytest.raises(TrustedReleaseError, match="signature verification failed"):
        manifest_service._verify_manifest(b"{}", "A" * 88)

    bad_release = {**release, "tag_name": "v9.9.9"}

    def mismatch(request):
        if str(request.url) == RELEASES_API:
            return httpx.Response(200, json=bad_release, request=request)
        return transport.handle_request(request)

    with pytest.raises(TrustedReleaseError, match="does not match"):
        TrustedReleaseService(tmp_path, database_path=tmp_path / "db.sqlite3", public_key_der=public_text, transport=httpx.MockTransport(mismatch)).check()

    def wrong_origin(request):
        if str(request.url) == RELEASES_API:
            return httpx.Response(200, json={"tag_name": "v0.2.0", "assets": [{"name": "erselmetz-release.json", "url": "https://evil.example/manifest"}]}, request=request)
        return transport.handle_request(request)

    with pytest.raises(TrustedReleaseError, match="outside the trusted GitHub"):
        TrustedReleaseService(tmp_path, database_path=tmp_path / "db.sqlite3", public_key_der=public_text, transport=httpx.MockTransport(wrong_origin)).check()


def test_prepare_stages_only_matching_installer_and_sqlite_recovery_backup(tmp_path: Path):
    installer = b"release installer bytes"
    transport, public, _release = signed_release(installer)
    database = tmp_path / "projects" / "ai_corporation.db"
    make_database(database)
    service = TrustedReleaseService(tmp_path / "profile", database_path=database, public_key_der=base64.b64encode(public).decode(), transport=transport)

    prepared = service.prepare("0.2.0")

    assert Path(prepared["installer_path"]).read_bytes() == installer
    backup = Path(prepared["backup_path"])
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT value FROM owner_data WHERE id='preserve-me'").fetchone() == ("durable",)
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)


def test_download_interruption_or_digest_mismatch_does_not_leave_installer_or_backup(tmp_path: Path):
    transport, public, _release = signed_release(b"signed installer")
    database = tmp_path / "db.sqlite3"
    make_database(database)

    def interrupted(request):
        if request.url.path.endswith("/3"):
            return httpx.Response(200, content=b"partial", request=request)
        return transport.handle_request(request)

    service = TrustedReleaseService(tmp_path / "profile", database_path=database, public_key_der=base64.b64encode(public).decode(), transport=httpx.MockTransport(interrupted))
    with pytest.raises(TrustedReleaseError, match="integrity"):
        service.prepare("0.2.0")
    update_dir = tmp_path / "profile" / "updates"
    assert list(update_dir.glob("*.partial")) == []
    assert not list((update_dir / "backups").glob("*.sqlite3")) if (update_dir / "backups").exists() else True


def test_incompatible_configuration_version_is_rejected_before_download(tmp_path: Path):
    transport, public, _release = signed_release(config_from=0, config_to=2)
    database = tmp_path / "db.sqlite3"
    make_database(database, version=1)
    service = TrustedReleaseService(tmp_path / "profile", database_path=database, public_key_der=base64.b64encode(public).decode(), transport=transport)
    with pytest.raises(TrustedReleaseError, match="incompatible"):
        service.prepare("0.2.0")


def test_version_order_handles_equal_and_prerelease_versions():
    assert _compare_versions("1.2.0", "1.2.0") == 0
    assert _compare_versions("1.2.0", "1.1.9") > 0
    assert _compare_versions("1.2.0-beta.1", "1.2.0") < 0


def test_legacy_database_moves_to_version_one_and_newer_database_fails_before_mutation(tmp_path: Path, monkeypatch):
    from app.database import connection as database_connection
    from app.database.init import initialize_database

    database = tmp_path / "legacy.sqlite3"
    monkeypatch.setattr(database_connection, "DATABASE_PATH", database)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL, assigned_agent TEXT, status TEXT NOT NULL, result TEXT, error TEXT)")
        connection.execute("INSERT INTO tasks VALUES ('legacy', 'Keep', 'Keep data', NULL, 'pending', NULL, NULL)")
    initialize_database()
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (2,)
        assert connection.execute("SELECT title FROM tasks WHERE id='legacy'").fetchone() == ("Keep",)

    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError, match="newer than this release"):
        initialize_database()
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (99,)


def test_release_apis_keep_default_deny_and_require_manage_permission_and_csrf():
    from unittest.mock import MagicMock
    from app.api import create_app
    from app.application import CorporationApplicationService
    from app.orchestrator import Orchestrator

    service = MagicMock()
    service.check.return_value.response.return_value = {"version": "0.2.0", "available": True}
    service.prepare.return_value = {"version": "0.2.0", "message": "ready"}
    application_service = CorporationApplicationService(MagicMock(spec=Orchestrator))
    unauthenticated = create_app(application_service, UpdateAuth(None), trusted_release_service=service)
    read_only = create_app(application_service, UpdateAuth({"updates:read"}), trusted_release_service=service)
    owner = create_app(application_service, UpdateAuth({"updates:read", "updates:manage"}), trusted_release_service=service)

    with TestClient(unauthenticated) as client:
        assert client.get("/api/updates/release").status_code == 401
    with TestClient(read_only) as client:
        assert client.get("/api/updates/release").status_code == 200
        assert client.post("/api/updates/release/prepare", json={"version": "0.2.0"}).status_code == 403
    with TestClient(owner) as client:
        assert client.post("/api/updates/release/prepare", json={"version": "0.2.0"}, headers={"X-Local-CSRF": "owner-token"}).json() == {"version": "0.2.0", "message": "ready"}
    assert service.check.call_count == 1
    service.prepare.assert_called_once_with("0.2.0")
