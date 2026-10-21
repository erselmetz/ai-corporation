"""End-to-end provider-body capture through authenticated Python chat routes."""
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest
from fastapi.testclient import TestClient

import app.database.connection as database_connection
from app.local import create_local_app
from app.runtime.factory import create_corporation_runtime


ORIGIN = "http://127.0.0.1:8000"
PASSWORD = "task194-capture-owner-pass"


class CapturedOllama:
    def __init__(self):
        self.requests = []
        self.lock = threading.Lock()


@pytest.fixture
def chat_capture(monkeypatch, tmp_path):
    capture = CapturedOllama()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            with capture.lock:
                capture.requests.append((self.path, raw.decode("utf-8")))
            request = json.loads(raw)
            if request.get("stream") is True:
                payloads = (
                    {"message": {"role": "assistant", "content": "captured "}, "done": False},
                    {"message": {"role": "assistant", "content": "stream"}, "done": True},
                )
                body = b"".join(
                    json.dumps(item, separators=(",", ":")).encode("utf-8") + b"\n"
                    for item in payloads
                )
                content_type = "application/x-ndjson"
            else:
                body = json.dumps({
                    "message": {"role": "assistant", "content": "Captured reply."},
                    "done": True,
                }).encode("utf-8")
                content_type = "application/json"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(
        database_connection, "DATABASE_PATH", tmp_path / "projects" / "chat-test.db"
    )
    runtime = create_corporation_runtime()
    runtime.providers.get("ollama").base_url = f"http://127.0.0.1:{server.server_port}"
    application = create_local_app(
        password=PASSWORD, origin=ORIGIN, application_service=runtime.application_service,
    )
    try:
        with TestClient(application, base_url=ORIGIN, client=("127.0.0.1", 50279)) as client:
            login = client.post(
                "/api/local/login", json={"password": PASSWORD}, headers={"Origin": ORIGIN},
            )
            assert login.status_code == 200
            session = client.get("/api/local/session", headers={"Origin": ORIGIN}).json()
            headers = {"Origin": ORIGIN, "X-Local-CSRF": session["csrf"]}
            yield client, headers, capture
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _start_coordinator(client, headers):
    response = client.post(
        "/api/chat/conversations", json={"agent_id": "local_worker"}, headers=headers,
    )
    assert response.status_code == 200
    return response.json()["conversation"]["id"]


def _assert_no_request_envelope(path, raw_body, *, stream):
    assert path == "/api/chat"
    body = json.loads(raw_body)
    assert body["model"] == "llama3.2:3b"
    assert body["stream"] is stream
    assert isinstance(body["messages"], list)
    assert body["messages"][0]["role"] == "system"
    assert len(body["messages"][0]["content"].splitlines()) in range(3, 6)
    assert all(message["role"] in {"system", "user", "assistant"} for message in body["messages"])
    encoded = json.dumps(body, ensure_ascii=False)
    for forbidden in (
        '"corporation_id"', '"context"', '"history"', '"request"',
        '"presentation_preferences"', '"boundary"',
        "They do not change provider/model selection",
    ):
        assert forbidden not in encoded
    return body


def test_authenticated_coordinator_route_sends_chat_messages_and_prior_history(chat_capture):
    client, headers, capture = chat_capture
    identifier = _start_coordinator(client, headers)
    first = client.post(
        f"/api/chat/conversations/{identifier}/messages", json={"text": "hello"}, headers=headers,
    )
    assert first.status_code == 200
    first_path, first_raw = capture.requests[-1]
    first_body = _assert_no_request_envelope(first_path, first_raw, stream=False)
    assert [message["role"] for message in first_body["messages"]] == ["system", "user"]
    assert first_body["messages"][-1]["content"] == "hello"

    second = client.post(
        f"/api/chat/conversations/{identifier}/messages", json={"text": "follow up"}, headers=headers,
    )
    assert second.status_code == 200
    _, second_raw = capture.requests[-1]
    second_body = _assert_no_request_envelope(capture.requests[-1][0], second_raw, stream=False)
    assert [message["role"] for message in second_body["messages"]] == ["system", "user", "assistant", "user"]
    assert second_body["messages"][-1]["content"] == "follow up"
    assert second_body["messages"][-2]["content"] == "Captured reply."


def test_authenticated_streaming_route_sends_native_chat_stream_body(chat_capture):
    client, headers, capture = chat_capture
    identifier = _start_coordinator(client, headers)
    response = client.post(
        f"/api/chat/conversations/{identifier}/messages/stream",
        json={"text": "hello"}, headers=headers,
    )
    assert response.status_code == 200
    assert [json.loads(line)["type"] for line in response.text.splitlines()] == ["status", "chunk", "chunk", "complete"]
    path, raw = capture.requests[-1]
    body = _assert_no_request_envelope(path, raw, stream=True)
    assert [message["role"] for message in body["messages"]] == ["system", "user"]


def test_retrieval_route_adds_only_selected_untrusted_excerpt(chat_capture):
    client, headers, capture = chat_capture
    identifier = _start_coordinator(client, headers)
    first = client.post(
        f"/api/chat/conversations/{identifier}/messages",
        json={"text": "Our staging service uses port 8142."}, headers=headers,
    )
    assert first.status_code == 200
    conversation = first.json()["conversation"]
    user_message = next(item for item in conversation["messages"] if item["role"] == "user")
    retained = client.post(
        f"/api/chat/conversations/{identifier}/retained", headers=headers,
        json={"message_id": user_message["id"], "retention_opt_in": True,
              "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()},
    )
    assert retained.status_code == 200

    response = client.post(
        f"/api/chat/conversations/{identifier}/messages", headers=headers,
        json={"text": "Which port?", "context": {
            "query": "port", "scope": "conversation", "scope_id": identifier,
        }},
    )
    assert response.status_code == 200
    path, raw = capture.requests[-1]
    body = _assert_no_request_envelope(path, raw, stream=False)
    reference = next(
        item["content"] for item in body["messages"]
        if "BEGIN UNTRUSTED RETRIEVED KNOWLEDGE" in item["content"]
    )
    assert "8142" in reference
    assert body["messages"][-1] == {"role": "user", "content": "Which port?"}


def test_individual_employee_chat_route_also_uses_native_chat_messages(chat_capture):
    client, headers, capture = chat_capture
    started = client.post(
        "/api/employee-chat/conversations", json={"employee_id": "local_employee"}, headers=headers,
    )
    assert started.status_code == 201
    identifier = started.json()["conversation"]["id"]
    response = client.post(
        f"/api/employee-chat/conversations/{identifier}/messages",
        json={"text": "hello"}, headers=headers,
    )
    assert response.status_code == 200
    path, raw = capture.requests[-1]
    body = _assert_no_request_envelope(path, raw, stream=False)
    assert [message["role"] for message in body["messages"]] == ["system", "user"]
    assert body["messages"][-1]["content"] == "hello"


def test_individual_employee_stream_route_also_uses_native_chat_messages(chat_capture):
    client, headers, capture = chat_capture
    started = client.post(
        "/api/employee-chat/conversations", json={"employee_id": "local_employee"}, headers=headers,
    )
    assert started.status_code == 201
    identifier = started.json()["conversation"]["id"]
    response = client.post(
        f"/api/employee-chat/conversations/{identifier}/messages/stream",
        json={"text": "hello"}, headers=headers,
    )
    assert response.status_code == 200
    assert [json.loads(line)["type"] for line in response.text.splitlines()] == ["chunk", "chunk", "complete"]
    path, raw = capture.requests[-1]
    body = _assert_no_request_envelope(path, raw, stream=True)
    assert [message["role"] for message in body["messages"]] == ["system", "user"]
    assert body["messages"][-1]["content"] == "hello"
