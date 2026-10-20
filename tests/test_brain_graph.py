from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api import AuthenticatedPrincipal, create_app
from app.api.memory import get_memory_now
from app.runtime.factory import create_corporation_runtime

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)


class Authentication:
    def __init__(self, identity="owner", permissions=frozenset({"memory:read", "memory:manage"})):
        self.identity, self.permissions = identity, permissions

    def authenticate(self, _request):
        return AuthenticatedPrincipal(self.identity, self.permissions)


def make_app(runtime, auth=None, now=NOW):
    app = create_app(runtime.application_service, auth)
    app.dependency_overrides[get_memory_now] = lambda: now
    return app


def test_brain_graph_contains_only_owner_documents_chunks_and_source_links():
    runtime = create_corporation_runtime()
    with TestClient(make_app(runtime, Authentication())) as client:
        expiry = (NOW + timedelta(days=1)).isoformat()
        first = client.post("/api/memory/owner", json={
            "content": "alpha one. " + ("alpha detail. " * 100), "source_name": "alpha.md",
            "expires_at": expiry, "retention_opt_in": True,
        }).json()
        second = client.post("/api/memory/owner", json={
            "content": "beta source content", "source_name": "beta.py",
            "expires_at": expiry, "retention_opt_in": True,
        }).json()
        graph = client.get("/api/memory/brain/graph")
        assert graph.status_code == 200
        body = graph.json()
        assert body["basis"].startswith("Derived file-type/note groups")
        assert all("content" not in node for node in body["nodes"])
        documents = [node for node in body["nodes"] if node["kind"] == "document"]
        chunks = [node for node in body["nodes"] if node["kind"] == "chunk"]
        assert {node["source_id"] for node in documents} == {first["id"], second["id"]}
        assert {node["cluster"] for node in documents} == {"md", "py"}
        assert len(chunks) == first["chunk_count"] + second["chunk_count"]
        assert len(body["edges"]) == len(chunks)
        assert all(edge["kind"] == "same-source" for edge in body["edges"])
        assert all(edge["from"].startswith("document:") and edge["to"].startswith("chunk:")
                   for edge in body["edges"])
        detail = client.get("/api/memory/brain/node", params={"node_id": f"chunk:{first['id']}#1"})
        assert detail.status_code == 200
        assert detail.json()["content"].startswith("alpha one.")
        assert detail.json()["source_reference"] == "alpha.md"
        assert client.get("/api/memory/brain/node", params={"node_id": f"chunk:{first['id']}#999"}).status_code == 422


def test_brain_graph_fails_closed_and_never_allows_cross_owner_node_inspection():
    runtime = create_corporation_runtime()
    with TestClient(make_app(runtime)) as client:
        assert client.get("/api/memory/brain/graph").status_code == 401
    with TestClient(make_app(runtime, Authentication(permissions=frozenset()))) as client:
        assert client.get("/api/memory/brain/graph").status_code == 403
    with TestClient(make_app(runtime, Authentication(identity="other"))) as client:
        assert client.get("/api/memory/brain/graph").json()["nodes"] == []
        assert client.get("/api/memory/brain/node", params={"node_id": "document:unknown"}).status_code == 404
