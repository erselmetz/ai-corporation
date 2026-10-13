from datetime import datetime, timedelta, timezone
import math
import sys
import types

import pytest

from app.api import AuthenticatedPrincipal, create_app
from app.api.memory import get_memory_now
from app.database import get_connection
from app.knowledge.chunking import chunk_text
from app.knowledge.service import SemanticCapabilityUnavailable, SemanticMemoryService
from app.memory import ConversationMemoryStore, MemoryRecord, MemoryScope, MemoryType
from app.runtime.factory import create_corporation_runtime
from fastapi.testclient import TestClient

NOW = datetime(2026, 10, 2, tzinfo=timezone.utc)


class FakeEmbeddingProvider:
    identity = "deterministic-test-model"
    groups = {"dog": "animal", "canine": "animal", "puppy": "animal",
              "invoice": "finance", "payment": "finance", "galaxy": "space"}
    dimensions = {"animal": 0, "finance": 1, "space": 2, "other": 3}

    def embed_one(self, text):
        return self.embed_batch((text,))[0]

    def embed_batch(self, texts):
        output = []
        for text in texts:
            vector = [0.0] * 4
            words = text.casefold().split()
            for word in words:
                group = self.groups.get(word, "other")
                vector[self.dimensions[group]] += 1.0
            magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
            output.append(tuple(value / magnitude for value in vector))
        return tuple(output)


class MemoryVectorStore:
    def __init__(self):
        self.items = {}
        self.search_filters = []

    def upsert(self, ids, vectors, metadata):
        for item_id, vector, data in zip(ids, vectors, metadata):
            self.items[item_id] = (tuple(vector), dict(data))

    def search(self, vector, where, limit):
        self.search_filters.append(where)
        conditions = where["$and"]
        results = []
        for item_id, (stored, metadata) in self.items.items():
            if any(metadata.get(key) != value for condition in conditions for key, value in condition.items()):
                continue
            distance = 1.0 - sum(a * b for a, b in zip(vector, stored))
            results.append((item_id, distance, dict(metadata)))
        results.sort(key=lambda item: (item[1], item[0]))
        return tuple(results[:limit])

    def delete_source(self, source_key):
        self.items = {key: value for key, value in self.items.items()
                      if value[1].get("source_key") != source_key}

    def delete_memory(self, scope, scope_id, memory_id):
        self.items = {key: value for key, value in self.items.items()
                      if (value[1].get("scope"), value[1].get("scope_id"), value[1].get("memory_id"))
                      != (scope, scope_id, memory_id)}

    def inspect_source(self, source_key, limit):
        return tuple(dict(metadata) for _, metadata in self.items.values()
                     if metadata.get("source_key") == source_key)[:limit]

    def stats(self):
        estimated = sum(len(vector) * 4 + len(str(metadata).encode("utf-8"))
                        for vector, metadata in self.items.values())
        return {"vector_count": len(self.items), "storage_bytes": estimated,
                "storage_complete": True, "storage_entries_scanned": len(self.items)}


def retained(memory_id, content, *, owner="owner", scope=MemoryScope.CONVERSATION, scope_id="chat"):
    record = MemoryRecord(memory_id, owner, scope, scope_id, MemoryType.NOTE, content,
                          "source-" + memory_id, NOW, NOW + timedelta(hours=1), True)
    ConversationMemoryStore().retain(record, now=NOW)
    return record


def service(runtime, vectors=None):
    vectors = vectors or MemoryVectorStore()
    semantic = SemanticMemoryService(runtime.application_service.memory_management(), FakeEmbeddingProvider(), vectors)
    runtime.application_service.configure_semantic_memory(semantic)
    return semantic, vectors


def test_chunking_is_deterministic_normalized_and_bounded():
    text = "Alpha  beta\r\n" + ("word " * 1500)
    chunks = chunk_text(text)
    assert chunks == chunk_text(text)
    assert len(chunks) <= 16
    assert all(0 < len(chunk) <= 1200 for chunk in chunks)
    assert "\r" not in "".join(chunks)
    with pytest.raises(ValueError):
        chunk_text(" ")
    with pytest.raises(ValueError):
        chunk_text("x" * 8193)


def test_explicit_index_and_semantic_search_return_live_provenance_only():
    runtime = create_corporation_runtime()
    retained("dogs", "canine")
    retained("billing", "invoice payment information")
    semantic, vectors = service(runtime)
    indexed = semantic.index("dogs", actor_id="owner", scope=MemoryScope.CONVERSATION,
                             scope_id="chat", now=NOW)
    semantic.index("billing", actor_id="owner", scope=MemoryScope.CONVERSATION,
                   scope_id="chat", now=NOW)
    semantic.index("dogs", actor_id="owner", scope=MemoryScope.CONVERSATION,
                   scope_id="chat", now=NOW)
    assert [item.position for item in indexed] == [0]
    assert len(vectors.items) == 2
    assert all("text" not in metadata and "content" not in metadata
               for _, metadata in vectors.items.values())
    results = semantic.search("dog puppy", actor_id="owner", scope=MemoryScope.CONVERSATION,
                              scope_id="chat", now=NOW)
    assert [hit.memory_id for hit in results.hits] == ["dogs"]
    assert results.hits[0].source_reference == "source-dogs"
    assert results.hits[0].relevance == pytest.approx(1.0)
    assert vectors.search_filters[-1] == {"$and": [
        {"scope": "conversation"}, {"scope_id": "chat"}, {"owner_id": "owner"},
        {"embedding_model": "deterministic-test-model"}
    ]}


def test_context_retrieval_delegates_only_when_semantic_search_is_explicit_and_rag_is_bounded():
    runtime = create_corporation_runtime()
    retained("context-note", "canine")
    semantic, _ = service(runtime)
    semantic.index("context-note", actor_id="owner", scope=MemoryScope.CONVERSATION,
                   scope_id="chat", now=NOW)
    context = runtime.application_service.context_retrieval()
    # Existing lexical lookup remains deterministic and no embedding is required for it.
    assert [hit.source.memory_id for hit in context.retrieve(
        "canine", actor_id="owner", scope=MemoryScope.CONVERSATION, scope_id="chat", now=NOW).hits] == ["context-note"]
    result = context.retrieve_semantic("dog", actor_id="owner", scope=MemoryScope.CONVERSATION,
                                       scope_id="chat", now=NOW)
    from app.knowledge.rag_context import RagContextBuilder
    prepared = RagContextBuilder().build(result)
    assert len(prepared.items) == 1
    assert prepared.items[0].source_reference == "source-context-note"
    assert "untrusted reference data" in prepared.notice
    assert prepared.encoded_bytes <= 8192
    with pytest.raises(ValueError):
        RagContextBuilder().build(result, max_bytes=100)


def test_project_knowledge_uses_verified_project_scope_without_task_execution():
    runtime = create_corporation_runtime()
    project_a = runtime.application_service.create_project("Project A", "")
    project_b = runtime.application_service.create_project("Project B", "")
    task = runtime.application_service.create_task("Reference note", "", project_a.id, agent_id="local_worker")
    from app.memory.scoped_store import ProjectKnowledgeStore
    record = MemoryRecord("project-a-note", "owner", MemoryScope.PROJECT, project_a.id,
                          MemoryType.NOTE, "canine", task.id, NOW, NOW + timedelta(hours=1), True)
    runtime.application_service.project_knowledge().retain(record, now=NOW)
    semantic, _ = service(runtime)
    semantic.index(record.id, actor_id="owner", scope=MemoryScope.PROJECT, scope_id=project_a.id, now=NOW)
    project_context = runtime.application_service.context_retrieval()
    result = project_context.retrieve_semantic("dog", actor_id="owner", scope=MemoryScope.PROJECT,
                                               scope_id=project_a.id, now=NOW)
    assert [hit.memory_id for hit in result.hits] == [record.id]
    assert result.hits[0].source_reference == task.id
    assert project_context.retrieve_semantic("dog", actor_id="owner", scope=MemoryScope.PROJECT,
                                             scope_id=project_b.id, now=NOW).hits == ()
    assert runtime.application_service.get_task(task.id).status == "pending"
    assert ProjectKnowledgeStore().retrieve(record.id, owner_id="owner", project_id=project_a.id, now=NOW) == record


def test_exact_owner_and_scope_isolation_and_corporation_reader_authorization():
    runtime = create_corporation_runtime()
    retained("private-owner", "canine animal", owner="other")
    retained("private-elsewhere", "canine animal", scope_id="another-chat")
    published = retained("published-source", "canine animal")
    held_knowledge_service = runtime.application_service.corporation_knowledge()
    held_knowledge_service.publish(
        "corp-note", actor_id="owner", source_scope=MemoryScope.CONVERSATION,
        source_scope_id="chat", source_memory_id=published.id,
        readers=["reader"], now=NOW, publication_opt_in=True)
    semantic, _ = service(runtime)
    semantic.index("private-owner", actor_id="other", scope=MemoryScope.CONVERSATION,
                   scope_id="chat", now=NOW)
    semantic.index("private-elsewhere", actor_id="owner", scope=MemoryScope.CONVERSATION,
                   scope_id="another-chat", now=NOW)
    semantic.index("corp-note", actor_id="owner", scope=MemoryScope.CORPORATION,
                   scope_id="corp_local", now=NOW)
    assert semantic.search("dog", actor_id="owner", scope=MemoryScope.CONVERSATION,
                           scope_id="chat", now=NOW).hits == ()
    results = semantic.search("dog", actor_id="reader", scope=MemoryScope.CORPORATION,
                              scope_id="corp_local", now=NOW)
    assert [hit.memory_id for hit in results.hits] == ["corp-note"]
    with pytest.raises(PermissionError):
        semantic.index("corp-note", actor_id="reader", scope=MemoryScope.CORPORATION,
                       scope_id="corp_local", now=NOW)
    assert semantic.search("dog", actor_id="outsider", scope=MemoryScope.CORPORATION,
                           scope_id="corp_local", now=NOW).hits == ()


def test_indexing_requires_owner_and_invalid_inputs_or_missing_capability_fail_closed():
    runtime = create_corporation_runtime()
    record = retained("owned", "canine animal")
    semantic, _ = service(runtime)
    with pytest.raises(KeyError):
        semantic.index(record.id, actor_id="stranger", scope=record.scope, scope_id=record.scope_id, now=NOW)
    disabled = SemanticMemoryService(runtime.application_service.memory_management())
    assert disabled.status()["state"] == "disabled"
    with pytest.raises(SemanticCapabilityUnavailable):
        disabled.search("dog", actor_id="owner", scope=record.scope, scope_id=record.scope_id, now=NOW)
    with pytest.raises(ValueError):
        semantic.search("", actor_id="owner", scope=record.scope, scope_id=record.scope_id, now=NOW)
    with pytest.raises(ValueError):
        semantic.search("dog", actor_id="owner", scope=record.scope, scope_id=record.scope_id, now=NOW, limit=11)


def test_core_startup_and_health_work_without_optional_vector_capability(monkeypatch):
    monkeypatch.delenv("ERSELMETZ_KNOWLEDGE_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("ERSELMETZ_KNOWLEDGE_VECTOR_DIR", raising=False)
    runtime = create_corporation_runtime()
    app = create_app(runtime.application_service, Auth(frozenset({"memory:read"})))
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/memory/semantic/status").json()["state"] == "disabled"


def test_update_delete_expiry_and_reader_revocation_clear_or_filter_indexed_vectors():
    runtime = create_corporation_runtime()
    original = retained("mutable", "canine animal")
    manager = runtime.application_service.memory_management()
    semantic, vectors = service(runtime)
    semantic.index(original.id, actor_id="owner", scope=original.scope, scope_id=original.scope_id, now=NOW)
    detail = manager.inspect(original.id, actor_id="owner", scope=original.scope, scope_id=original.scope_id, now=NOW)
    manager.update(original.id, actor_id="owner", scope=original.scope, scope_id=original.scope_id,
                   revision=detail["revision"], content="invoice payment", expires_at=NOW + timedelta(hours=2),
                   retention_opt_in=True, now=NOW)
    assert vectors.items == {}
    semantic.index(original.id, actor_id="owner", scope=original.scope, scope_id=original.scope_id, now=NOW)
    assert semantic.search("dog", actor_id="owner", scope=original.scope, scope_id=original.scope_id, now=NOW).hits == ()
    manager.remove(original.id, actor_id="owner", scope=original.scope, scope_id=original.scope_id)
    assert vectors.items == {}

    expiring = retained("expiring", "canine animal")
    semantic.index(expiring.id, actor_id="owner", scope=expiring.scope, scope_id=expiring.scope_id, now=NOW)
    assert semantic.search("dog", actor_id="owner", scope=expiring.scope, scope_id=expiring.scope_id,
                           now=expiring.expires_at).hits == ()
    assert vectors.items == {}

    corp_source = retained("corp-source", "canine animal")
    knowledge = runtime.application_service.corporation_knowledge()
    knowledge.publish("corp-private", actor_id="owner", source_scope=corp_source.scope,
                      source_scope_id=corp_source.scope_id, source_memory_id=corp_source.id,
                      readers=["reader"], now=NOW, publication_opt_in=True)
    semantic.index("corp-private", actor_id="owner", scope=MemoryScope.CORPORATION,
                   scope_id="corp_local", now=NOW)
    knowledge.revoke_reader("corp-private", actor_id="owner", reader_id="reader")
    assert vectors.items == {}
    assert semantic.search("dog", actor_id="reader", scope=MemoryScope.CORPORATION,
                           scope_id="corp_local", now=NOW).hits == ()


class Auth:
    def __init__(self, permissions):
        self.permissions = permissions

    def authenticate(self, _request):
        return AuthenticatedPrincipal("owner", self.permissions)


def test_semantic_api_requires_existing_auth_and_separate_index_permission():
    runtime = create_corporation_runtime()
    retained("api-note", "canine animal")
    semantic, _ = service(runtime)
    app = create_app(runtime.application_service, semantic_memory_service=semantic)
    with TestClient(app) as client:
        assert client.get("/api/memory/semantic/status").status_code == 401
    app = create_app(runtime.application_service, Auth(frozenset({"memory:read"})), semantic_memory_service=semantic)
    with TestClient(app) as client:
        assert client.get("/api/memory/semantic/status").json()["state"] == "configured"
        body = {"scope": "conversation", "scope_id": "chat", "memory_id": "api-note"}
        assert client.post("/api/memory/semantic/index", json=body).status_code == 403
        assert client.post("/api/memory/semantic/search", json={
            "query": "dog", "scope": "conversation", "scope_id": "chat", "limit": 5
        }).json()["items"] == []
    app = create_app(runtime.application_service, Auth(frozenset({"memory:read", "memory:index"})), semantic_memory_service=semantic)
    app.dependency_overrides[get_memory_now] = lambda: NOW
    with TestClient(app) as client:
        indexed = client.post("/api/memory/semantic/index", json=body)
        assert indexed.status_code == 200
        assert indexed.json()["chunk_count"] == 1
        search = client.post("/api/memory/semantic/search", json={
            "query": "dog", "scope": "conversation", "scope_id": "chat", "limit": 5
        })
        assert search.status_code == 200
        assert search.json()["items"][0]["memory_id"] == "api-note"


def test_configured_but_missing_optional_dependencies_is_truthfully_unavailable(tmp_path, monkeypatch):
    runtime = create_corporation_runtime()
    model_dir = tmp_path / "local-model"
    model_dir.mkdir()
    monkeypatch.setenv("ERSELMETZ_KNOWLEDGE_EMBEDDING_MODEL", str(model_dir))
    monkeypatch.setenv("ERSELMETZ_KNOWLEDGE_VECTOR_DIR", str(tmp_path / "vector-store"))
    import importlib.util
    original = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec",
                        lambda name, *args, **kwargs: None if name in {"sentence_transformers", "chromadb"}
                        else original(name, *args, **kwargs))
    status = runtime.application_service.semantic_memory().status()
    assert status["state"] == "unavailable"
    assert "install" in status["detail"].lower()
    assert str(model_dir) not in str(status)


def test_index_failures_do_not_expose_provider_secrets():
    runtime = create_corporation_runtime()
    retained("secret-test", "canine")

    class BrokenEmbeddingProvider(FakeEmbeddingProvider):
        def embed_batch(self, texts):
            raise RuntimeError("Bearer API-SECRET-NEVER-RETURN")

    semantic = SemanticMemoryService(runtime.application_service.memory_management(),
                                     BrokenEmbeddingProvider(), MemoryVectorStore())
    app = create_app(runtime.application_service, Auth(frozenset({"memory:index"})),
                     semantic_memory_service=semantic)
    app.dependency_overrides[get_memory_now] = lambda: NOW
    with TestClient(app) as client:
        response = client.post("/api/memory/semantic/index", json={
            "scope": "conversation", "scope_id": "chat", "memory_id": "secret-test"
        })
        assert response.status_code == 503
        assert "API-SECRET-NEVER-RETURN" not in response.text
        assert response.json()["detail"] == "Local semantic indexing failed"


def test_semantic_lifecycle_is_explicit_bounded_and_preserves_authoritative_memory():
    runtime = create_corporation_runtime()
    owned = retained("lifecycle-owned", "owner retained source for recovery")
    private = retained("lifecycle-private", "another owner's source", owner="other")
    semantic, vectors = service(runtime)

    rebuilt = semantic.rebuild([owned.id, private.id], actor_id="owner",
                               scope=owned.scope, scope_id=owned.scope_id, now=NOW)
    assert rebuilt.operation == "rebuild"
    assert (rebuilt.completed, rebuilt.failed) == (1, 1)
    assert [item.completed for item in rebuilt.sources] == [1, 2]
    assert rebuilt.sources[0].state == "complete"
    assert rebuilt.sources[1].state == "failed"
    assert rebuilt.storage["vector_count"] == len(vectors.items)

    from app.knowledge.service import _source_key
    source_key = _source_key("owner", owned.scope, owned.scope_id, owned.id)
    for item_id, (vector, metadata) in list(vectors.items.items()):
        if metadata["source_key"] == source_key:
            changed_metadata = dict(metadata)
            changed_metadata["revision"] = "0" * 64
            vectors.items[item_id] = (vector, changed_metadata)

    inspected = semantic.inspect_lifecycle([owned.id], actor_id="owner",
                                          scope=owned.scope, scope_id=owned.scope_id, now=NOW)
    assert inspected.sources[0].state == "stale"
    assert inspected.stale_chunks == inspected.sources[0].indexed_chunks
    cleaned = semantic.cleanup_stale([owned.id], actor_id="owner",
                                    scope=owned.scope, scope_id=owned.scope_id, now=NOW)
    assert cleaned.sources[0].state == "cleaned"
    assert all(item[1]["memory_id"] != owned.id for item in vectors.items.items())
    assert runtime.application_service.memory_management().inspect(
        owned.id, actor_id="owner", scope=owned.scope, scope_id=owned.scope_id,
        now=NOW)["content"] == owned.content

    with pytest.raises(ValueError, match="Select 1 to 10"):
        semantic.rebuild([f"id-{i}" for i in range(11)], actor_id="owner",
                         scope=owned.scope, scope_id=owned.scope_id, now=NOW)


def test_semantic_lifecycle_vector_failure_does_not_remove_authoritative_memory():
    class FailingStore(MemoryVectorStore):
        def upsert(self, ids, vectors, metadata):
            raise RuntimeError("private backend diagnostic")

    runtime = create_corporation_runtime()
    source = retained("lifecycle-failure", "must remain available after vector failure")
    semantic = SemanticMemoryService(runtime.application_service.memory_management(),
                                     FakeEmbeddingProvider(), FailingStore())
    report = semantic.rebuild([source.id], actor_id="owner", scope=source.scope,
                              scope_id=source.scope_id, now=NOW)
    assert report.failed == 1
    assert "private backend diagnostic" not in str(report)
    assert "preserved" in report.sources[0].detail
    assert runtime.application_service.memory_management().inspect(
        source.id, actor_id="owner", scope=source.scope, scope_id=source.scope_id,
        now=NOW)["content"] == source.content


def test_semantic_lifecycle_routes_require_existing_memory_index_permission():
    runtime = create_corporation_runtime()
    source = retained("lifecycle-api", "explicitly retained API source")
    semantic, _ = service(runtime)
    body = {"scope": source.scope.value, "scope_id": source.scope_id,
            "memory_ids": [source.id]}
    app = create_app(runtime.application_service, Auth(frozenset({"memory:read"})),
                     semantic_memory_service=semantic)
    app.dependency_overrides[get_memory_now] = lambda: NOW
    with TestClient(app) as client:
        denied = client.post("/api/memory/semantic/rebuild", json=body)
    assert denied.status_code == 403
    app = create_app(runtime.application_service, Auth(frozenset({"memory:index"})),
                     semantic_memory_service=semantic)
    app.dependency_overrides[get_memory_now] = lambda: NOW
    with TestClient(app) as client:
        rebuilt = client.post("/api/memory/semantic/rebuild", json=body)
        inspected = client.post("/api/memory/semantic/inspect", json=body)
        cleaned = client.post("/api/memory/semantic/cleanup", json=body)
    assert rebuilt.status_code == inspected.status_code == cleaned.status_code == 200
    assert rebuilt.json()["execution"] == "synchronous-bounded"
    assert rebuilt.json()["sources"][0]["completed"] == 1
    assert inspected.json()["sources"][0]["state"] == "current"
    assert cleaned.json()["sources"][0]["state"] == "current"


def test_chroma_lifecycle_stats_measure_only_configured_store_and_bound_walk(tmp_path, monkeypatch):
    collection = types.SimpleNamespace(
        count=lambda: 2,
        get=lambda where, limit, include: {
            "ids": ["chunk"], "metadatas": [{"source_key": where["source_key"]}]
        },
    )
    client = types.SimpleNamespace(get_or_create_collection=lambda *args, **kwargs: collection)
    chroma = types.ModuleType("chromadb")
    chroma.PersistentClient = lambda **kwargs: client
    config = types.ModuleType("chromadb.config")
    config.Settings = lambda **kwargs: object()
    chroma.config = config
    monkeypatch.setitem(sys.modules, "chromadb", chroma)
    monkeypatch.setitem(sys.modules, "chromadb.config", config)

    from app.knowledge.vector_store import ChromaVectorStore
    path = tmp_path / "configured-vectors"
    path.mkdir()
    (path / "index.db").write_bytes(b"12345")
    child = path / "segments"
    child.mkdir()
    (child / "segment.bin").write_bytes(b"abc")
    store = ChromaVectorStore(str(path))
    assert store.inspect_source("selected-key", 17) == ({"source_key": "selected-key"},)
    stats = store.stats()
    assert stats == {"vector_count": 2, "storage_bytes": 8,
                     "storage_complete": True, "storage_entries_scanned": 3}
    assert str(path) not in str(stats)


def test_optional_adapters_use_only_local_embeddings_and_external_vectors(tmp_path, monkeypatch):
    calls = {}

    class Model:
        def encode(self, texts, **kwargs):
            calls["encode"] = (texts, kwargs)
            return [[1.0, 0.0] for _ in texts]

    class SentenceTransformer:
        def __init__(self, path, **kwargs):
            calls["model"] = (path, kwargs)
            self.model = Model()

        def encode(self, *args, **kwargs):
            return self.model.encode(*args, **kwargs)

    monkeypatch.setitem(sys.modules, "sentence_transformers",
                        types.SimpleNamespace(SentenceTransformer=SentenceTransformer))
    from app.knowledge.providers import SentenceTransformerEmbeddingProvider
    model_path = tmp_path / "existing-model"
    model_path.mkdir()
    provider = SentenceTransformerEmbeddingProvider(str(model_path))
    assert provider.identity.startswith("local-embedding-")
    assert "existing-model" not in provider.identity
    assert provider.embed_one("dog") == (1.0, 0.0)
    assert calls["model"][1]["local_files_only"] is True
    assert calls["model"][1]["trust_remote_code"] is False
    assert calls["encode"][1]["normalize_embeddings"] is True

    chroma_calls = {}

    class Collection:
        def upsert(self, **kwargs): chroma_calls["upsert"] = kwargs
        def query(self, **kwargs):
            chroma_calls["query"] = kwargs
            return {"ids": [["chunk"]], "distances": [[0.1]], "metadatas": [[{"scope": "conversation"}]]}
        def delete(self, **kwargs): chroma_calls.setdefault("deletes", []).append(kwargs)

    collection = Collection()

    class PersistentClient:
        def __init__(self, **kwargs): chroma_calls["client"] = kwargs
        def get_or_create_collection(self, name, **kwargs):
            chroma_calls["collection"] = {"name": name, **kwargs}
            return collection

    class Settings:
        def __init__(self, **kwargs): chroma_calls["settings"] = kwargs

    chromadb = types.ModuleType("chromadb")
    chromadb.PersistentClient = PersistentClient
    config = types.ModuleType("chromadb.config")
    config.Settings = Settings
    monkeypatch.setitem(sys.modules, "chromadb", chromadb)
    monkeypatch.setitem(sys.modules, "chromadb.config", config)
    from app.knowledge.vector_store import ChromaVectorStore
    store = ChromaVectorStore(str(tmp_path / "vectors"))
    store.upsert(["chunk"], [[1.0, 0.0]], [{"scope": "conversation"}])
    store.search([1.0, 0.0], {"scope": "conversation"}, 1)
    assert chroma_calls["settings"] == {"anonymized_telemetry": False}
    assert chroma_calls["collection"]["embedding_function"] is None
    assert "documents" not in chroma_calls["upsert"]
    assert chroma_calls["query"]["query_embeddings"] == [[1.0, 0.0]]
