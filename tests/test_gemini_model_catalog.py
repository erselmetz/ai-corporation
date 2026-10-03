from __future__ import annotations

import json
from contextlib import AbstractContextManager
from datetime import timezone

import httpx
import pytest

from app.integrations.gemini_catalog import (
    GEMINI_MODELS_ENDPOINT,
    GEMINI_REQUEST_TIMEOUT_SECONDS,
    MAX_GEMINI_MODELS_PER_PAGE,
    MAX_GEMINI_PAGES_PER_REQUEST,
    MAX_GEMINI_RESPONSE_BYTES,
    GeminiAPIConfiguration,
    GeminiCatalogAuditStatus,
    GeminiCatalogFailureCode,
    GeminiModelCapability,
    GeminiModelCatalogAdapter,
    GeminiModelCatalogError,
)

API_KEY = "unit-test-api-key"


class FakeResponse(AbstractContextManager["FakeResponse"]):
    def __init__(
        self,
        body: bytes,
        *,
        status_code: int = 200,
        content_type: str = "application/json; charset=utf-8",
        content_length: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        if content_length is not None:
            self.headers["content-length"] = content_length
        self.body = body
        self.iterated = False

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def iter_bytes(self):
        self.iterated = True
        for offset in range(0, len(self.body), 4096):
            yield self.body[offset : offset + 4096]


class FakeClient(AbstractContextManager["FakeClient"]):
    def __init__(
        self,
        response: FakeResponse | Exception,
        calls: list[tuple[str, str, dict[str, str], dict[str, str]]],
    ) -> None:
        self.response = response
        self.calls = calls

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def stream(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> FakeResponse:
        self.calls.append((method, url, params, headers))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def install_fake_responses(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[FakeResponse | Exception],
) -> tuple[
    list[dict[str, object]],
    list[tuple[str, str, dict[str, str], dict[str, str]]],
]:
    configurations: list[dict[str, object]] = []
    calls: list[tuple[str, str, dict[str, str], dict[str, str]]] = []
    response_index = 0

    def create_client(**kwargs: object) -> FakeClient:
        nonlocal response_index
        configurations.append(kwargs)
        if response_index >= len(responses):
            raise AssertionError("Unexpected extra HTTP request")
        response = responses[response_index]
        response_index += 1
        return FakeClient(response, calls)

    monkeypatch.setattr("app.integrations.gemini_catalog.httpx.Client", create_client)
    return configurations, calls


def json_response(payload: object) -> FakeResponse:
    return FakeResponse(json.dumps(payload).encode("utf-8"))


def test_model_listing_returns_only_allowlisted_metadata_and_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configurations, calls = install_fake_responses(
        monkeypatch,
        [
            json_response(
                {
                    "models": [
                        {
                            "name": "models/gemini-test",
                            "displayName": "Not returned",
                            "inputTokenLimit": 12345,
                            "supportedGenerationMethods": [
                                "generateContent",
                                "countTokens",
                                "unknownMethod",
                            ],
                        },
                        {"name": "models/embedding-test"},
                    ]
                }
            )
        ],
    )
    configuration = GeminiAPIConfiguration(api_key=API_KEY)
    result = GeminiModelCatalogAdapter(configuration).list_models()

    assert repr(configuration) == "GeminiAPIConfiguration()"
    assert configurations == [
        {
            "timeout": GEMINI_REQUEST_TIMEOUT_SECONDS,
            "follow_redirects": False,
            "trust_env": False,
        }
    ]
    assert calls == [
        (
            "GET",
            GEMINI_MODELS_ENDPOINT,
            {"pageSize": str(MAX_GEMINI_MODELS_PER_PAGE)},
            {"Accept": "application/json", "x-goog-api-key": API_KEY},
        )
    ]
    assert API_KEY not in calls[0][1]
    assert result.models[0].model_id == "models/gemini-test"
    assert result.models[0].capabilities == (
        GeminiModelCapability.COUNT_TOKENS,
        GeminiModelCapability.GENERATE_CONTENT,
    )
    assert result.models[1].model_id == "models/embedding-test"
    assert result.models[1].capabilities is None
    assert result.has_more is False
    assert result.retrieved_at.tzinfo == timezone.utc
    assert result.audit_event.status is GeminiCatalogAuditStatus.SUCCEEDED
    assert result.audit_event.service == "gemini"
    assert result.audit_event.operation == "list_models"
    assert result.audit_event.pages_requested == 1
    assert result.audit_event.model_count == 2
    assert result.audit_event.failure_code is None
    assert API_KEY not in repr(result)
    with pytest.raises((AttributeError, TypeError)):
        result.models[0].model_id = "changed"


def test_pagination_is_on_demand_bounded_and_does_not_expose_page_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = [
        json_response(
            {
                "models": [{"name": f"models/model-{index}"}],
                "nextPageToken": f"page-token-{index}",
            }
        )
        for index in range(MAX_GEMINI_PAGES_PER_REQUEST)
    ]
    configurations, calls = install_fake_responses(monkeypatch, responses)

    result = GeminiModelCatalogAdapter(
        GeminiAPIConfiguration(api_key=API_KEY)
    ).list_models()

    assert len(calls) == MAX_GEMINI_PAGES_PER_REQUEST
    assert len(configurations) == MAX_GEMINI_PAGES_PER_REQUEST
    assert calls[0][2] == {"pageSize": str(MAX_GEMINI_MODELS_PER_PAGE)}
    assert calls[1][2] == {
        "pageSize": str(MAX_GEMINI_MODELS_PER_PAGE),
        "pageToken": "page-token-0",
    }
    assert result.has_more is True
    assert len(result.models) == MAX_GEMINI_PAGES_PER_REQUEST
    assert result.audit_event.pages_requested == MAX_GEMINI_PAGES_PER_REQUEST
    assert result.audit_event.has_more is True
    assert "page-token" not in repr(result)


def test_network_failures_are_sanitized_and_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_fake_responses(
        monkeypatch,
        [
            httpx.ConnectError(
                f"key={API_KEY}",
                request=httpx.Request("GET", GEMINI_MODELS_ENDPOINT),
            )
        ],
    )
    adapter = GeminiModelCatalogAdapter(GeminiAPIConfiguration(api_key=API_KEY))

    with pytest.raises(GeminiModelCatalogError) as raised:
        adapter.list_models()

    assert str(raised.value) == "Gemini model listing failed"
    assert API_KEY not in str(raised.value)
    assert API_KEY not in repr(raised.value)
    assert API_KEY not in repr(raised.value.audit_event)
    assert raised.value.audit_event.status is GeminiCatalogAuditStatus.FAILED
    assert raised.value.audit_event.service == "gemini"
    assert raised.value.audit_event.failure_code is GeminiCatalogFailureCode.REQUEST_FAILED
    assert raised.value.audit_event.pages_requested == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"models": [{"name": f"models/{API_KEY}"}]},
        {"models": [], "nextPageToken": API_KEY},
        {"models": [], "nextPageToken": "unit%2Dtest%2Dapi%2Dkey"},
    ],
)
def test_service_metadata_cannot_echo_the_api_key(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
) -> None:
    _configurations, calls = install_fake_responses(
        monkeypatch,
        [json_response(payload)],
    )

    with pytest.raises(GeminiModelCatalogError) as raised:
        GeminiModelCatalogAdapter(
            GeminiAPIConfiguration(api_key=API_KEY)
        ).list_models()

    assert (
        raised.value.audit_event.failure_code
        is GeminiCatalogFailureCode.MALFORMED_RESPONSE
    )
    assert len(calls) == 1
    assert API_KEY not in calls[0][1]
    assert API_KEY not in repr(calls[0][2])
    assert API_KEY not in repr(raised.value)
    assert API_KEY not in repr(raised.value.audit_event)


@pytest.mark.parametrize(
    ("response", "failure_code"),
    [
        (
            FakeResponse(
                b'{"error":"secret response body"}',
                status_code=403,
            ),
            GeminiCatalogFailureCode.HTTP_ERROR,
        ),
        (
            FakeResponse(
                b'{"error":"secret response body"}',
                content_length=str(MAX_GEMINI_RESPONSE_BYTES + 1),
            ),
            GeminiCatalogFailureCode.RESPONSE_TOO_LARGE,
        ),
        (
            FakeResponse(b"not json"),
            GeminiCatalogFailureCode.MALFORMED_RESPONSE,
        ),
        (
            FakeResponse(
                b'{"models":' + b"[" * 1_100 + b"]" * 1_100 + b"}"
            ),
            GeminiCatalogFailureCode.MALFORMED_RESPONSE,
        ),
        (
            json_response({"models": [{"name": "https://attacker.example"}]}),
            GeminiCatalogFailureCode.MALFORMED_RESPONSE,
        ),
    ],
)
def test_service_and_response_failures_are_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    response: FakeResponse,
    failure_code: GeminiCatalogFailureCode,
) -> None:
    install_fake_responses(monkeypatch, [response])

    with pytest.raises(GeminiModelCatalogError) as raised:
        GeminiModelCatalogAdapter(
            GeminiAPIConfiguration(api_key=API_KEY)
        ).list_models()

    assert str(raised.value) == "Gemini model listing failed"
    assert API_KEY not in str(raised.value)
    assert "secret response body" not in str(raised.value)
    assert raised.value.audit_event.failure_code is failure_code


@pytest.mark.parametrize("api_key", ["", " test-key", "test\r\nkey", "clé"])
def test_invalid_key_configuration_is_rejected_without_echoing_key(
    api_key: str,
) -> None:
    with pytest.raises(ValueError) as raised:
        GeminiAPIConfiguration(api_key=api_key)

    if api_key:
        assert api_key not in str(raised.value)
