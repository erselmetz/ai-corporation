import hashlib
import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api import AuthenticatedPrincipal, create_app
from app.api.memory import get_memory_now
from app.memory import MemoryScope
from app.runtime.factory import create_corporation_runtime

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)


class Authentication:
    def __init__(self, identity="owner", permissions=frozenset({"memory:read", "memory:manage"})):
        self.identity, self.permissions = identity, permissions

    def authenticate(self, _request):
        return AuthenticatedPrincipal(self.identity, self.permissions)


def make_app(runtime, auth=None):
    app = create_app(runtime.application_service, auth or Authentication())
    app.dependency_overrides[get_memory_now] = lambda: NOW
    return app


def brain_file():
    return json.dumps([
        {"source": "notes/a.md", "text": "Fact alpha", "vec": [0.1, 0.2]},
        {"source": "notes/a.md", "text": "Fact beta", "vec": [0.3, 0.4]},
        {"source": "notes/b.txt", "text": "Fact gamma", "vec": [0.5, 0.6]},
    ]).encode("utf-8")


def upload(client, path, payload, params=None):
    return client.post(path, params=params, files={"file": ("brain.json", payload, "application/json")})


def test_v3code_brain_preview_is_read_only_and_commit_is_owner_scoped_idempotent():
    runtime = create_corporation_runtime()
    payload = brain_file()
    digest = hashlib.sha256(payload).hexdigest()
    with TestClient(make_app(runtime)) as client:
        preview = upload(client, "/api/memory/owner/v3code/preview", payload)
        assert preview.status_code == 200
        assert preview.json() == {
            "digest": digest, "chunk_count": 3, "source_count": 2,
            "note_count": 2, "ignored_embeddings": True,
        }
        assert client.get("/api/memory/owner").json()["items"] == []

        params = {
            "expected_digest": digest,
            "expires_at": (NOW + timedelta(days=7)).isoformat(),
            "retention_opt_in": "true",
        }
        imported = upload(client, "/api/memory/owner/v3code/import", payload, params)
        assert imported.status_code == 200
        assert imported.json()["created_count"] == 2
        assert imported.json()["skipped_count"] == 0

        repeated = upload(client, "/api/memory/owner/v3code/import", payload, params)
        assert repeated.status_code == 200
        assert repeated.json()["created_count"] == 0
        assert repeated.json()["skipped_count"] == 2
        items = client.get("/api/memory/owner").json()["items"]
        assert len(items) == 2
        assert all(item["scope"] == MemoryScope.OWNER.value and item["scope_id"] == "owner" for item in items)
        details = [client.get("/api/memory/record", params={
            "scope": "owner", "scope_id": "owner", "memory_id": item["id"],
        }).json() for item in items]
        assert {detail["content"] for detail in details} == {"Fact alpha\n\nFact beta", "Fact gamma"}
        assert all("0.1" not in detail["content"] for detail in details)

    with TestClient(make_app(runtime, Authentication(identity="other"))) as client:
        assert client.get("/api/memory/owner").json()["items"] == []


def test_v3code_brain_import_requires_matching_preview_and_explicit_retention():
    runtime = create_corporation_runtime()
    payload = brain_file()
    with TestClient(make_app(runtime)) as client:
        changed_digest = "0" * 64
        params = {
            "expected_digest": changed_digest,
            "expires_at": (NOW + timedelta(days=7)).isoformat(),
            "retention_opt_in": "true",
        }
        mismatch = upload(client, "/api/memory/owner/v3code/import", payload, params)
        assert mismatch.status_code == 409
        params["expected_digest"] = hashlib.sha256(payload).hexdigest()
        params["retention_opt_in"] = "false"
        no_consent = upload(client, "/api/memory/owner/v3code/import", payload, params)
        assert no_consent.status_code == 422
        params["retention_opt_in"] = "true"
        params["expires_at"] = (NOW + timedelta(days=31)).isoformat()
        excessive_retention = upload(client, "/api/memory/owner/v3code/import", payload, params)
        assert excessive_retention.status_code == 422
        assert client.get("/api/memory/owner").json()["items"] == []


def test_v3code_brain_preview_and_import_require_memory_manage_permission():
    runtime = create_corporation_runtime()
    with TestClient(make_app(runtime, Authentication(permissions=frozenset({"memory:read"})))) as client:
        assert upload(client, "/api/memory/owner/v3code/preview", brain_file()).status_code == 403
        assert upload(client, "/api/memory/owner/v3code/import", brain_file(), {}).status_code == 403
