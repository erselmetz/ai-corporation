from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import math
from urllib.parse import urlencode
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient
import pytest

from app.api.chat import get_chat_now
from app.api.memory import get_memory_now
from app.api.security import AuthenticatedPrincipal
from app.database import connection as database_connection
from app.knowledge.intake import extract_upload
from app.knowledge.service import SemanticMemoryService
from app.local import create_local_app
from app.memory import MemoryScope
from app.portability.backups import DataPortabilityService
from app.providers import OllamaProvider
from app.runtime.factory import create_corporation_runtime

ORIGIN = "http://127.0.0.1:8000"
PASSWORD = "test-only-owner-passphrase"
NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)


class FakeEmbedding:
    identity = "task177-deterministic-model"

    def embed_one(self, text):
        return self.embed_batch((text,))[0]

    def embed_batch(self, texts):
        output = []
        for text in texts:
            words = set(text.casefold().split())
            vector = [float(sum(word in words for word in group)) for group in
                      ({"project", "server", "orion"}, {"port", "8123", "service"}, {"other"})]
            size = math.sqrt(sum(value * value for value in vector)) or 1.0
            output.append(tuple(value / size for value in vector))
        return tuple(output)


class FakeVectors:
    def __init__(self): self.rows = {}
    def upsert(self, ids, vectors, metadata):
        self.rows.update({item_id: (vector, data) for item_id, vector, data in zip(ids, vectors, metadata)})
    def search(self, vector, where, limit):
        conditions = [entry for item in where["$and"] for entry in item.items()]
        selected = [(key, row) for key, row in self.rows.items() if all(row[1].get(k) == v for k, v in conditions)]
        selected.sort(key=lambda item: item[0])
        return tuple((key, 0.0, dict(row[1])) for key, row in selected[:limit])
    def delete_source(self, source_key):
        self.rows = {key: row for key, row in self.rows.items() if row[1].get("source_key") != source_key}
    def delete_memory(self, scope, scope_id, memory_id):
        self.rows = {key: row for key, row in self.rows.items()
                     if (row[1].get("scope"), row[1].get("scope_id"), row[1].get("memory_id")) != (scope, scope_id, memory_id)}
    def inspect_source(self, source_key, limit):
        return tuple(dict(row[1]) for row in self.rows.values() if row[1].get("source_key") == source_key)[:limit]
    def stats(self): return {"vector_count": len(self.rows), "storage_bytes": 0, "storage_complete": True, "storage_entries_scanned": len(self.rows)}


@pytest.fixture
def env(monkeypatch):
    prompts = []
    def generate_chat(self, model, messages):
        prompts.append(messages)
        return "Verified fixture reply."
    monkeypatch.setattr(OllamaProvider, "generate_chat", generate_chat)
    runtime = create_corporation_runtime()
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    clock = {"now": NOW}
    app.dependency_overrides[get_chat_now] = lambda: clock["now"]
    app.dependency_overrides[get_memory_now] = lambda: clock["now"]
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50200)) as client:
        assert client.post("/api/local/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN}).status_code == 200
        session = client.get("/api/local/session").json()
        headers = {"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]}
        yield client, headers, prompts, clock, runtime, app


def add_note(client, headers, *, name="field-notes.md", content="Orion project server runs on port 8123.", now=NOW):
    return client.post("/api/memory/owner", headers=headers, json={
        "content": content, "source_name": name,
        "expires_at": (now + timedelta(days=5)).isoformat(), "retention_opt_in": True,
    })


def start(client, headers):
    response = client.post("/api/chat/conversations", json={"agent_id": "local_worker"}, headers=headers)
    assert response.status_code == 200
    return response.json()["conversation"]["id"]


def preview(client, headers, conversation, query="Which port does the Orion project server use?", scopes=None):
    return client.post(f"/api/chat/conversations/{conversation}/knowledge-preview", headers=headers, json={
        "query": query, "scopes": scopes or [{"scope": "owner"}],
    })


def test_private_note_intake_requires_consent_expires_and_is_owner_scoped(env):
    client, headers, _, clock, _, app = env
    missing = client.post("/api/memory/owner", headers=headers, json={
        "content": "private note", "source_name": "note.txt",
        "expires_at": (NOW + timedelta(days=1)).isoformat(), "retention_opt_in": False,
    })
    assert missing.status_code == 422
    created = add_note(client, headers, name="../../local-note.md")
    assert created.status_code == 200
    body = created.json()
    assert body["scope"] == "owner" and body["scope_id"] == "local-owner"
    listed = client.get("/api/memory/owner").json()
    assert [item["id"] for item in listed["items"]] == [body["id"]]
    assert listed["items"][0]["source_reference"] == "local-note.md"
    restarted_runtime = create_corporation_runtime()
    persisted = restarted_runtime.application_service.memory_management().list(
        actor_id="local-owner", scope=MemoryScope.OWNER, scope_id="local-owner", limit=10, now=NOW)
    assert [item["id"] for item in persisted] == [body["id"]]
    portability = DataPortabilityService(database_connection.DATABASE_PATH)
    assert "owner_knowledge" not in portability.preview(include_private_data=False)["included_tables"]
    private_preview = portability.preview(include_private_data=True)
    assert private_preview["included_row_counts"]["owner_knowledge"] == 1
    app.state.authentication_backend.principal = AuthenticatedPrincipal(
        "other-owner", frozenset({"memory:read", "memory:manage", "memory:index", "chat:read", "chat:send"}))
    assert client.get("/api/memory/owner").json()["items"] == []
    clock["now"] += timedelta(days=6)
    app.state.authentication_backend.principal = AuthenticatedPrincipal(
        "local-owner", frozenset({"memory:read", "memory:manage", "memory:index", "chat:read", "chat:send", "chat:start"}))
    assert client.get("/api/memory/owner").json()["items"][0]["expired"] is True
    cid = start(client, headers)
    expired_preview = preview(client, headers, cid, "Which project note?").json()
    assert expired_preview["items"] == []


def test_upload_accepts_bounded_utf8_notes_data_code_and_docx(env):
    client, headers, _, _, _, _ = env
    query = urlencode({"expires_at": (NOW + timedelta(days=2)).isoformat(), "retention_opt_in": "true"})
    accepted = client.post("/api/memory/owner/upload?" + query,
                           headers=headers,
                           files={"file": ("notes.md", b"Project Orion uses local inference.", "text/markdown")})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["content"] == "Project Orion uses local inference."
    for filename, content, media_type in (
        ("notes.csv", b"city,port\nOrion,8123\n", "text/csv"),
        ("script.py", b"print('Orion')", "text/x-python"),
    ):
        added = client.post("/api/memory/owner/upload?" + query, headers=headers,
                            files={"file": (filename, content, media_type)})
        assert added.status_code == 200, added.text
        assert added.json()["content"] == content.decode()
    document = BytesIO()
    with ZipFile(document, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>Orion launch note</w:t></w:r></w:p></w:body></w:document>'
        ))
    added_docx = client.post("/api/memory/owner/upload?" + query, headers=headers,
                             files={"file": ("brief.docx", document.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert added_docx.status_code == 200, added_docx.text
    assert added_docx.json()["content"].strip() == "Orion launch note"
    unsupported = client.post("/api/memory/owner/upload?" + query,
                              headers=headers,
                              files={"file": ("notes.bin", b"x", "application/octet-stream")})
    assert unsupported.status_code == 422
    assert extract_upload("C:\\private\\notes.TXT", b"hello")[1] == "notes.TXT"


def test_docx_extraction_rejects_malformed_or_declared_xml():
    with pytest.raises(ValueError, match="DOCX text could not be extracted"):
        extract_upload("broken.docx", b"not-a-zip")
    payload = BytesIO()
    with ZipFile(payload, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", (
            '<!DOCTYPE x [<!ENTITY e "expanded">]><w:document '
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>&e;</w:t></w:r></w:p></w:body></w:document>'
        ))
    with pytest.raises(ValueError, match="declarations are not supported"):
        extract_upload("declared.docx", payload.getvalue())


def test_brain_faiss_pack_routes_are_authenticated_owner_confirmed_and_digest_bound(env):
    client, headers, _, _, _, app = env

    class Pack:
        state = "not-installed"
        calls = []
        def preview(self):
            return {"pack_id": "faiss-cpu", "state": self.state, "supported": True,
                    "files": ["faiss.whl"], "download_bytes": 12,
                    "manifest_digest": "a" * 64, "source": "Official PyPI",
                    "install_action": "Owner confirmation required"}
        @property
        def site_packages(self): return "unused"
        def install(self, *, confirmed, manifest_digest):
            self.calls.append((confirmed, manifest_digest))
            self.state = "installed"
            return {"state": self.state, "already_installed": False, "pack_id": "faiss-cpu"}

    pack = Pack()
    app.state.faiss_pack_installer = pack
    assert client.get("/api/memory/brain/faiss/preview", headers=headers).json()["state"] == "not-installed"
    denied = client.post("/api/memory/brain/faiss/install", json={
        "confirmed": True, "manifest_digest": "a" * 64,
    }, headers={"Origin": ORIGIN})
    assert denied.status_code == 403
    incomplete = client.post("/api/memory/brain/faiss/install", json={
        "confirmed": False, "manifest_digest": "b" * 64,
    }, headers=headers)
    assert incomplete.status_code == 409
    installed = client.post("/api/memory/brain/faiss/install", json={
        "confirmed": True, "manifest_digest": "a" * 64,
    }, headers=headers)
    assert installed.status_code == 200, installed.text
    assert pack.calls == [(True, "a" * 64)]


def test_brain_embedding_model_download_is_previewed_confirmed_and_does_not_change_agent_route(env):
    client, headers, _, _, runtime, app = env

    class ModelInstaller:
        calls = []
        def status(self):
            return {"state": "available", "service_running": True,
                    "model_id": "nomic-embed-text:latest", "model_installed": False,
                    "source": "local Ollama", "reason": None}
        def preview_model(self):
            return {"model_id": "nomic-embed-text:latest", "manifest_digest": "sha256:" + "c" * 64,
                    "manifest_bytes": 100, "registry_url": "https://registry.ollama.ai/fake"}
        def pull(self, *, expected_digest, expected_bytes):
            self.calls.append((expected_digest, expected_bytes))
            yield json.dumps({"event": "complete", "message": "Ollama confirmed the model."}) + "\n"

    model_installer = ModelInstaller()
    app.state.brain_embedding_model_service = model_installer
    before = runtime.application_service.get_agent("local_worker")
    status = client.get("/api/memory/brain/embedding/status", headers=headers)
    assert status.status_code == 200 and status.json()["model_installed"] is False
    preview = client.get("/api/memory/brain/embedding/preview", headers=headers)
    assert preview.status_code == 200 and preview.json()["manifest_bytes"] == 100
    denied = client.post("/api/memory/brain/embedding/pull", json={
        "confirmed": False, "manifest_digest": "sha256:" + "c" * 64, "manifest_bytes": 100,
    }, headers=headers)
    assert denied.status_code == 409
    changed = client.post("/api/memory/brain/embedding/pull", json={
        "confirmed": True, "manifest_digest": "sha256:" + "d" * 64, "manifest_bytes": 100,
    }, headers=headers)
    assert changed.status_code == 409
    pulled = client.post("/api/memory/brain/embedding/pull", json={
        "confirmed": True, "manifest_digest": "sha256:" + "c" * 64, "manifest_bytes": 100,
    }, headers=headers)
    assert pulled.status_code == 200
    assert '"event":"complete"' in pulled.text
    assert model_installer.calls == [("sha256:" + "c" * 64, 100)]
    after = runtime.application_service.get_agent("local_worker")
    assert (after.provider, after.model) == (before.provider, before.model)


def test_disabled_toggle_never_retrieves_and_each_reply_has_real_trace(env):
    client, headers, prompts, _, _, _ = env
    assert add_note(client, headers).status_code == 200
    cid = start(client, headers)
    reply = client.post(f"/api/chat/conversations/{cid}/messages", headers=headers,
                        json={"text": "Which port is the Orion server?"})
    assert reply.status_code == 200
    prompt = prompts[-1]
    assert all("BEGIN UNTRUSTED RETRIEVED KNOWLEDGE" not in message["content"] for message in prompt)
    trace = reply.json()["context_trace"]
    assert trace["retrieval"] == {"enabled": False, "reason": "Use my knowledge was off."}
    assert trace["route"]["agent_id"] == "local_worker"
    assert trace["route"]["provider"] == "ollama"
    assert trace["actions"] == {"tools_run": False, "tasks_created": False}
    assert trace["timing"]["turn_elapsed_ms"] >= 0


def test_exact_prompt_is_explicit_one_turn_local_only_and_never_in_trace(env):
    client, headers, prompts, _, _, _ = env
    cid = start(client, headers)
    response = client.post(f"/api/chat/conversations/{cid}/messages", headers=headers,
                           json={"text": "show exact local prompt", "capture_local_prompt": True})
    assert response.status_code == 200
    payload = response.json()
    assert payload["advanced_prompt"] == json.dumps(prompts[-1], ensure_ascii=True, separators=(",", ":"))
    assert "show exact local prompt" in payload["advanced_prompt"]
    assert payload["context_trace"]["advanced_prompt_retained"] is False
    assert payload["advanced_prompt"] not in client.get(f"/api/chat/conversations/{cid}").text
    rejected = client.post(f"/api/chat/conversations/{cid}/messages/stream", headers=headers,
                           json={"text": "capture prompt", "capture_local_prompt": True})
    assert rejected.status_code == 422


def test_exact_prompt_capture_rejects_non_loopback_ollama(env):
    client, headers, prompts, _, runtime, _ = env
    runtime.providers.remove("ollama")
    runtime.providers.register("ollama", OllamaProvider("https://provider.example"))
    cid = start(client, headers)
    response = client.post(f"/api/chat/conversations/{cid}/messages", headers=headers,
                           json={"text": "keep prompt private", "capture_local_prompt": True})
    assert response.status_code == 422
    assert prompts == []


def test_provider_failure_trace_is_sanitized_and_outcome_is_explicit(env, monkeypatch):
    client, headers, _, _, _, _ = env
    cid = start(client, headers)

    def fail_with_secret(self, model, messages):
        raise RuntimeError("api_key=NEVER_EXPOSE_THIS")

    monkeypatch.setattr(OllamaProvider, "generate_chat", fail_with_secret)
    failed = client.post(f"/api/chat/conversations/{cid}/messages", headers=headers,
                         json={"text": "try one reply"})
    assert failed.status_code == 502
    conversation = client.get(f"/api/chat/conversations/{cid}").json()
    user_message = conversation["conversation"]["messages"][-1]
    trace = conversation["context_traces"][user_message["id"]]
    assert trace["outcome"] == "failed"
    assert trace["steps"][-1]["step"] == "answer"
    assert trace["steps"][-1]["status"] == "failed"
    assert trace["steps"][-1]["duration_ms"] >= 0
    assert "raw diagnostics are omitted" in trace["failure"]
    assert "NEVER_EXPOSE_THIS" not in failed.text + json.dumps(conversation)


def test_explicit_preview_and_auto_retrieval_are_untrusted_cited_and_bounded(env):
    client, headers, prompts, _, runtime, _ = env
    note = add_note(client, headers).json()
    cid = start(client, headers)
    tasks_before = len(runtime.tasks.all())
    before_calls = len(prompts)
    viewed = preview(client, headers, cid, "Which port does Orion use?")
    assert viewed.status_code == 200
    data = viewed.json()
    assert len(prompts) == before_calls
    assert len(data["items"]) == 1
    assert data["items"][0]["source"] == "field-notes.md"
    assert data["items"][0]["chunk_reference"] == f"{note['id']}#1"
    assert data["trace"]["context_bytes"] <= 1800
    response = client.post(f"/api/chat/conversations/{cid}/messages", headers=headers, json={
        "text": "Which port does Orion use?", "knowledge_enabled": True,
        "knowledge_scopes": [{"scope": "owner"}], "knowledge_preview_digest": data["digest"],
    })
    assert response.status_code == 200
    payload = prompts[-1]
    context = next(message["content"] for message in payload if "BEGIN UNTRUSTED RETRIEVED KNOWLEDGE" in message["content"])
    assert "untrusted" in context.casefold()
    assert "[1]" in context
    assert "Source: field-notes.md" in context
    assert "8123" in context
    trace = response.json()["context_trace"]
    assert trace["retrieval"]["mode"] == "lexical-only"
    assert trace["sources"][0]["source"] == "field-notes.md"
    assert trace["sources"][0]["score"] > 0
    assert [(step["step"], step["status"]) for step in trace["steps"]] == [
        ("plan", "completed"), ("retrieve", "completed"), ("tools", "skipped"), ("answer", "completed")]
    assert trace["steps"][1]["source"] == "field-notes.md"
    assert trace["steps"][1]["result_count"] == 1
    assert all(step["duration_ms"] >= 0 for step in trace["steps"])
    assert len(runtime.tasks.all()) == tasks_before


def test_empty_brain_search_tells_provider_to_abstain_without_inserting_empty_retrieval_block(env):
    client, headers, prompts, _, _, _ = env
    cid = start(client, headers)
    data = preview(client, headers, cid, "What is the retention period?").json()
    assert data["items"] == []
    calls = len(prompts)
    response = client.post(f"/api/chat/conversations/{cid}/messages", headers=headers, json={
        "text": "What is the retention period?", "knowledge_enabled": True,
        "knowledge_scopes": [{"scope": "owner"}], "knowledge_preview_digest": data["digest"],
    })
    assert response.status_code == 200
    assert len(prompts) == calls
    payload = response.json()
    assert payload["conversation"]["messages"][-1]["content"] == "I couldn't find relevant information about that in your Brain."
    assert payload["context_trace"]["sources"] == []
    assert payload["context_trace"]["provider_called"] is False
    assert payload["context_trace"]["answer_source"] == "brain-empty-abstention"


def test_empty_brain_stream_abstains_without_provider_call(env):
    client, headers, prompts, _, _, _ = env
    cid = start(client, headers)
    data = preview(client, headers, cid, "What is the retention period?").json()
    calls = len(prompts)
    response = client.post(f"/api/chat/conversations/{cid}/messages/stream", headers=headers, json={
        "text": "What is the retention period?", "knowledge_enabled": True,
        "knowledge_scopes": [{"scope": "owner"}], "knowledge_preview_digest": data["digest"],
    })
    assert response.status_code == 200
    event = json.loads(response.text.splitlines()[-1])
    assert event["type"] == "complete"
    assert event["conversation"]["messages"][-1]["content"] == "I couldn't find relevant information about that in your Brain."
    assert event["context_trace"]["provider_called"] is False
    assert len(prompts) == calls


def test_brain_retrieval_matches_natural_language_to_snake_case_fields(env):
    client, headers, _, _, _, _ = env
    add_note(client, headers, name="settings.json",
             content='{"backup_window":"02:00 UTC","retention_days":14}')
    cid = start(client, headers)
    data = preview(client, headers, cid, "What is the backup window?").json()
    assert data["items"]
    assert data["items"][0]["source"] == "settings.json"
    assert "02:00 UTC" in data["items"][0]["content"]


def test_changed_note_invalidates_preview_before_provider_call(env):
    client, headers, prompts, _, runtime, _ = env
    note = add_note(client, headers).json()
    cid = start(client, headers)
    data = preview(client, headers, cid, "Which port does Orion use?").json()
    runtime.application_service.memory_management().update(
        note["id"], actor_id="local-owner", scope=MemoryScope.OWNER, scope_id="local-owner",
        revision=note["revision"], content="Orion project server now uses port 9443.",
        expires_at=NOW + timedelta(days=5), retention_opt_in=True, now=NOW)
    calls = len(prompts)
    response = client.post(f"/api/chat/conversations/{cid}/messages", headers=headers, json={
        "text": "Which port does Orion use?", "knowledge_enabled": True,
        "knowledge_scopes": [{"scope": "owner"}], "knowledge_preview_digest": data["digest"],
    })
    assert response.status_code == 409
    assert len(prompts) == calls
    assert client.get(f"/api/chat/conversations/{cid}").json()["conversation"]["messages"] == []


def test_withdrawn_note_is_not_retrieved_on_a_later_turn(env):
    client, headers, _, _, _, _ = env
    note = add_note(client, headers).json()
    cid = start(client, headers)
    params = {"scope": "owner", "scope_id": "local-owner", "memory_id": note["id"]}
    assert client.request("DELETE", "/api/memory/record", headers=headers, params=params, json={}).status_code == 204
    selected = preview(client, headers, cid).json()
    assert selected["items"] == []


def test_retrieval_reports_duplicate_result_and_context_byte_limits(env):
    client, headers, _, _, _, _ = env
    cid = start(client, headers)
    repeated = "Orion project server uses port 8123. "
    for index in range(3):
        assert add_note(client, headers, name=f"copy-{index}.md", content=repeated).status_code == 200
    duplicate_preview = preview(client, headers, cid, "Which port does Orion server use?").json()
    assert len(duplicate_preview["items"]) == 1
    assert duplicate_preview["trace"]["truncation"]["duplicates_removed"] == 2

    for index in range(6):
        unique_details = " ".join(f"record{index}detail{part}" for part in range(70))
        content = f"Orion project server port 8123 record {index}. {unique_details}"
        assert add_note(client, headers, name=f"record-{index}.md", content=content).status_code == 200
    limited = preview(client, headers, cid, "Which Orion server port is used?").json()
    assert len(limited["items"]) <= 5
    assert limited["trace"]["context_bytes"] <= 1800
    assert limited["trace"]["truncation"]["retrieval_results"] is True
    assert limited["trace"]["truncation"]["context_bytes"] is True


def test_cloud_knowledge_requires_existing_per_turn_consent_and_redacts_trace(env, monkeypatch):
    client, headers, prompts, _, _, app = env
    add_note(client, headers, name="api_key=SHOULD_NOT_APPEAR.txt")
    cid = start(client, headers)
    selected = preview(client, headers, cid, "Which port does Orion use?").json()
    monkeypatch.setattr(app.state.application_service, "provider_requires_explicit_cloud_consent", lambda provider: True)
    body = {"text": "Which port does Orion use?", "knowledge_enabled": True,
            "knowledge_scopes": [{"scope": "owner"}], "knowledge_preview_digest": selected["digest"]}
    denied = client.post(f"/api/chat/conversations/{cid}/messages", headers=headers, json=body)
    assert denied.status_code == 403
    assert prompts == []
    body["cloud_consent"] = True
    completed = client.post(f"/api/chat/conversations/{cid}/messages", headers=headers, json=body)
    assert completed.status_code == 200
    trace = completed.json()["context_trace"]
    assert trace["cloud"]["consent_given"] is True
    assert trace["cloud"]["private_knowledge_sent"] is True
    assert "SHOULD_NOT_APPEAR" not in json.dumps(trace)


def test_local_semantic_index_is_explicitly_built_inspected_and_deleted(env):
    client, headers, _, _, runtime, _ = env
    note = add_note(client, headers).json()
    vectors = FakeVectors()
    runtime.application_service.configure_semantic_memory(SemanticMemoryService(
        runtime.application_service.memory_management(), FakeEmbedding(), vectors))
    indexed = client.post("/api/memory/semantic/index", headers=headers, json={
        "scope": "owner", "scope_id": "local-owner", "memory_id": note["id"],
    })
    assert indexed.status_code == 200
    assert indexed.json()["chunk_count"] == 1 and indexed.json()["indexed_at"] == NOW.isoformat()
    inspected = client.post("/api/memory/semantic/inspect", headers=headers, json={
        "scope": "owner", "scope_id": "local-owner", "memory_ids": [note["id"]],
    })
    source = inspected.json()["sources"][0]
    assert source["state"] == "current" and source["indexed_chunks"] == 1
    assert source["indexed_at"] == NOW.isoformat()
    params = {"scope": "owner", "scope_id": "local-owner", "memory_id": note["id"]}
    removed = client.request("DELETE", "/api/memory/record", headers=headers, params=params, json={})
    assert removed.status_code == 204
    assert not vectors.rows


def _text_pdf_fixture(text):
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(bodies, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii") + body + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        output.extend(f"{offset:010} 00000 n \n".encode("ascii"))
    output.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii"))
    return bytes(output)


def test_pdf_intake_extracts_bounded_text_without_external_calls():
    content, name = extract_upload("meeting-notes.pdf", _text_pdf_fixture("Orion server uses port 8123."))
    assert "Orion server uses port 8123" in content
    assert name == "meeting-notes.pdf"
