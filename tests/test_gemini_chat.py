from __future__ import annotations

import json
from contextlib import AbstractContextManager

import httpx
import pytest

from app.integrations.gemini_catalog import (
    GeminiModel,
    GeminiModelCapability,
    GeminiModelCatalogResult,
)
from app.integrations.gemini_chat import (
    GeminiCallLimit,
    GeminiConnectionError,
    GeminiConnectionManager,
    GeminiProvider,
)

KEY = "test-only-gemini-key"
MODEL = "gemini-test-flash"


def catalog_result():
    from datetime import datetime, timezone
    from app.integrations.gemini_catalog import GeminiCatalogAuditEvent, GeminiCatalogAuditStatus
    return GeminiModelCatalogResult(
        (GeminiModel(MODEL, (GeminiModelCapability.GENERATE_CONTENT,)),), False,
        datetime.now(timezone.utc), GeminiCatalogAuditEvent(
            "gemini", "list_models", GeminiCatalogAuditStatus.SUCCEEDED,
            datetime.now(timezone.utc), 1, 1, False, None))


class Response(AbstractContextManager):
    def __init__(self, body: bytes, status_code=200):
        self.body = body
        self.status_code = status_code

    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("private response detail", request=httpx.Request("POST", "https://example.test"), response=httpx.Response(self.status_code))
    def iter_bytes(self): yield self.body


class Client(AbstractContextManager):
    def __init__(self, response, calls, options): self.response, self.calls, self.options = response, calls, options
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def stream(self, method, url, *, headers, json):
        self.calls.append((method, url, headers, json))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def setup(monkeypatch, response=None):
    from app.integrations import gemini_catalog, gemini_chat
    monkeypatch.setattr(gemini_catalog.GeminiModelCatalogAdapter, "list_models", lambda self: catalog_result())
    calls, options = [], []
    if response is None:
        response = Response(b'{"candidates":[{"content":{"parts":[{"text":"deterministic reply"}]}}]}')
    def client_factory(**kwargs):
        options.append(kwargs)
        return Client(response, calls, kwargs)
    monkeypatch.setattr(gemini_chat.httpx, "Client", client_factory)
    manager = GeminiConnectionManager()
    manager.discover(KEY)
    provider = manager.provider(KEY, MODEL)
    return manager, provider, calls, options


def test_generate_uses_fixed_https_header_bounded_body_and_no_credential_retention(monkeypatch):
    manager, provider, calls, options = setup(monkeypatch)
    assert provider.generate(MODEL, "hello") == "deterministic reply"
    method, url, headers, payload = calls[0]
    assert method == "POST"
    assert url == f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    assert KEY not in url and headers["x-goog-api-key"] == KEY
    assert payload["generationConfig"]["maxOutputTokens"] == 1024
    assert options[0] == {"timeout": 20.0, "follow_redirects": False, "trust_env": False}
    assert KEY not in repr(provider) and KEY not in repr(manager.connection())
    assert manager.calls_used(manager.connection()) == 1


def test_request_cap_counts_failures_and_does_not_retry(monkeypatch):
    manager, provider, calls, _ = setup(monkeypatch, Response(b"{}", status_code=503))
    for _ in range(5):
        with pytest.raises(RuntimeError) as failure:
            provider.generate(MODEL, "hello")
        assert KEY not in str(failure.value)
    assert len(calls) == 5
    with pytest.raises(GeminiCallLimit):
        provider.generate(MODEL, "hello")
    assert len(calls) == 5
    assert manager.connection() is not None


def test_timeout_failure_is_bounded_sanitized_and_not_retried(monkeypatch):
    _manager, provider, calls, _ = setup(monkeypatch, httpx.ReadTimeout(f"private {KEY}"))
    with pytest.raises(RuntimeError) as failure:
        provider.generate(MODEL, "hello")
    assert KEY not in str(failure.value)
    assert len(calls) == 1


def test_disconnected_provider_cannot_use_cleared_credential(monkeypatch):
    manager, provider, _calls, _ = setup(monkeypatch)
    manager.clear_staged()
    with pytest.raises(GeminiConnectionError, match="disconnected"):
        provider.generate(MODEL, "hello")


def test_old_provider_cannot_use_a_later_staged_key(monkeypatch):
    from app.integrations import gemini_catalog
    monkeypatch.setattr(gemini_catalog.GeminiModelCatalogAdapter, "list_models", lambda self: catalog_result())
    from app.integrations import gemini_chat
    calls = []
    real_client = httpx.Client
    def client_factory(**kwargs):
        return real_client(transport=httpx.MockTransport(lambda request: calls.append(request)
            or httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "reply"}]}}]})), **kwargs)
    monkeypatch.setattr(gemini_chat.httpx, "Client", client_factory)
    manager = GeminiConnectionManager()
    manager.discover(KEY)
    old_provider = manager.provider(KEY, MODEL)
    manager.clear_staged()
    manager.discover("different-test-key")
    with pytest.raises(GeminiConnectionError, match="credential changed"):
        old_provider.generate(MODEL, "hello")
    assert calls == []


def test_manager_allows_only_one_generation_attempt_at_a_time(monkeypatch):
    import hashlib
    manager, provider, calls, _ = setup(monkeypatch)
    manager.begin_call(hashlib.sha256(KEY.encode()).digest(), MODEL)
    try:
        with pytest.raises(GeminiConnectionError, match="already active"):
            provider.generate(MODEL, "hello")
        assert calls == []
    finally:
        manager.end_call()


def test_expiry_erases_key_but_preserves_assignment_for_explicit_recovery(monkeypatch):
    from app.integrations import gemini_catalog
    monkeypatch.setattr(gemini_catalog.GeminiModelCatalogAdapter, "list_models", lambda self: catalog_result())
    now = [100.0]
    manager = GeminiConnectionManager(clock=lambda: now[0])
    manager.discover(KEY)
    provider = manager.provider(KEY, MODEL)
    manager.select_model("worker", "Worker", "ollama", "local", MODEL)
    now[0] += 3601
    assert manager.connection() is None
    assert manager.selected("worker") is not None
    assert KEY not in repr(provider)
    with pytest.raises(GeminiConnectionError, match="expired"):
        provider.generate(MODEL, "hello")


@pytest.mark.parametrize("prompt", ["", "界" * 11000], ids=["empty", "oversized-utf8"])
def test_empty_and_oversized_prompts_are_rejected_before_provider_request(monkeypatch, prompt):
    manager, provider, calls, _ = setup(monkeypatch)
    with pytest.raises(ValueError):
        provider.generate(MODEL, prompt)
    assert calls == []
    assert manager.calls_used(manager.connection()) == 0


def test_oversized_reply_is_sanitized(monkeypatch):
    body = json.dumps({"candidates": [{"content": {"parts": [{"text": "x" * 9000}]}}]}).encode()
    _manager, provider, _calls, _ = setup(monkeypatch, Response(body))
    with pytest.raises(RuntimeError) as failure:
        provider.generate(MODEL, "hello")
    assert "bounded text reply" not in str(failure.value)
    assert KEY not in str(failure.value)


def test_oversized_http_response_is_rejected_before_json_parsing(monkeypatch):
    _manager, provider, _calls, _ = setup(monkeypatch, Response(b"x" * (512 * 1024 + 1)))
    with pytest.raises(RuntimeError) as failure:
        provider.generate(MODEL, "hello")
    assert "response failed" in str(failure.value)
    assert KEY not in str(failure.value)


def test_distinct_key_budget_is_bounded_and_credential_does_not_survive_disconnect(monkeypatch):
    from app.integrations import gemini_catalog
    monkeypatch.setattr(gemini_catalog.GeminiModelCatalogAdapter, "list_models", lambda self: catalog_result())
    manager = GeminiConnectionManager()
    for index in range(32):
        manager.discover(f"key-{index:02d}")
    with pytest.raises(GeminiConnectionError, match="bounded number"):
        manager.discover("key-32")
    manager.clear_staged()
    assert manager.connection() is None
