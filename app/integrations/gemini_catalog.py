"""Bounded, read-only Gemini API model discovery."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import NoReturn
from urllib.parse import unquote

import httpx

GEMINI_MODELS_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_REQUEST_TIMEOUT_SECONDS = 10.0
MAX_GEMINI_RESPONSE_BYTES = 512 * 1024
MAX_GEMINI_MODELS_PER_PAGE = 100
MAX_GEMINI_PAGES_PER_REQUEST = 5
MAX_GEMINI_MODELS_PER_REQUEST = (
    MAX_GEMINI_MODELS_PER_PAGE * MAX_GEMINI_PAGES_PER_REQUEST
)
MAX_GEMINI_PAGE_TOKEN_CHARACTERS = 4_096

_MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$")
_ALLOWED_CAPABILITIES = frozenset(
    {
        "batchGenerateContent",
        "countTokens",
        "createCachedContent",
        "embedContent",
        "generateContent",
    }
)


class GeminiModelCapability(str, Enum):
    BATCH_GENERATE_CONTENT = "batchGenerateContent"
    COUNT_TOKENS = "countTokens"
    CREATE_CACHED_CONTENT = "createCachedContent"
    EMBED_CONTENT = "embedContent"
    GENERATE_CONTENT = "generateContent"


class GeminiCatalogAuditStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class GeminiCatalogFailureCode(str, Enum):
    REQUEST_FAILED = "request_failed"
    HTTP_ERROR = "http_error"
    RESPONSE_TOO_LARGE = "response_too_large"
    UNSUPPORTED_RESPONSE = "unsupported_response"
    MALFORMED_RESPONSE = "malformed_response"


@dataclass(frozen=True, slots=True)
class GeminiAPIConfiguration:
    api_key: str = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.api_key, str)
            or not self.api_key
            or len(self.api_key) > 4_096
            or any(
                ord(character) < 33 or ord(character) > 126
                for character in self.api_key
            )
        ):
            raise ValueError("Gemini API key configuration is invalid")


@dataclass(frozen=True, slots=True)
class GeminiModel:
    model_id: str
    capabilities: tuple[GeminiModelCapability, ...] | None


@dataclass(frozen=True, slots=True)
class GeminiCatalogAuditEvent:
    service: str
    operation: str
    status: GeminiCatalogAuditStatus
    occurred_at: datetime
    pages_requested: int
    model_count: int | None
    has_more: bool | None
    failure_code: GeminiCatalogFailureCode | None


@dataclass(frozen=True, slots=True)
class GeminiModelCatalogResult:
    models: tuple[GeminiModel, ...]
    has_more: bool
    retrieved_at: datetime
    audit_event: GeminiCatalogAuditEvent


class GeminiModelCatalogError(Exception):
    """A sanitized model-listing failure with a metadata-only audit event."""

    def __init__(self, audit_event: GeminiCatalogAuditEvent) -> None:
        self.audit_event = audit_event
        super().__init__("Gemini model listing failed")


class _GeminiPageFailure(Exception):
    def __init__(self, code: GeminiCatalogFailureCode) -> None:
        self.code = code


def _read_response(response: httpx.Response) -> tuple[bytes, str]:
    if response.status_code != 200:
        raise _GeminiPageFailure(GeminiCatalogFailureCode.HTTP_ERROR)

    content_type = response.headers.get("content-type", "").split(
        ";", maxsplit=1
    )[0].strip().lower()
    if content_type != "application/json":
        raise _GeminiPageFailure(GeminiCatalogFailureCode.UNSUPPORTED_RESPONSE)

    content_length = response.headers.get("content-length")
    if content_length is not None:
        try:
            content_length_value = int(content_length)
            if content_length_value < 0:
                raise _GeminiPageFailure(
                    GeminiCatalogFailureCode.MALFORMED_RESPONSE
                )
            if content_length_value > MAX_GEMINI_RESPONSE_BYTES:
                raise _GeminiPageFailure(
                    GeminiCatalogFailureCode.RESPONSE_TOO_LARGE
                )
        except ValueError:
            raise _GeminiPageFailure(
                GeminiCatalogFailureCode.MALFORMED_RESPONSE
            ) from None

    body = bytearray()
    for chunk in response.iter_bytes():
        if len(body) + len(chunk) > MAX_GEMINI_RESPONSE_BYTES:
            raise _GeminiPageFailure(GeminiCatalogFailureCode.RESPONSE_TOO_LARGE)
        body.extend(chunk)
    return bytes(body), content_type


def _parse_page(
    response_body: bytes,
) -> tuple[tuple[GeminiModel, ...], str | None]:
    try:
        payload = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise _GeminiPageFailure(
            GeminiCatalogFailureCode.MALFORMED_RESPONSE
        ) from None
    if not isinstance(payload, dict):
        raise _GeminiPageFailure(GeminiCatalogFailureCode.MALFORMED_RESPONSE)

    raw_models = payload.get("models")
    if (
        not isinstance(raw_models, list)
        or len(raw_models) > MAX_GEMINI_MODELS_PER_PAGE
    ):
        raise _GeminiPageFailure(GeminiCatalogFailureCode.MALFORMED_RESPONSE)

    page_token = payload.get("nextPageToken")
    if page_token is not None and (
        not isinstance(page_token, str)
        or len(page_token) > MAX_GEMINI_PAGE_TOKEN_CHARACTERS
        or any(ord(character) < 32 for character in page_token)
        or not page_token.strip()
    ):
        raise _GeminiPageFailure(GeminiCatalogFailureCode.MALFORMED_RESPONSE)
    if not page_token:
        page_token = None

    models: list[GeminiModel] = []
    for raw_model in raw_models:
        if not isinstance(raw_model, dict):
            raise _GeminiPageFailure(GeminiCatalogFailureCode.MALFORMED_RESPONSE)
        name = raw_model.get("name")
        if (
            not isinstance(name, str)
            or not name.startswith("models/")
            or not _MODEL_ID_PATTERN.fullmatch(name.removeprefix("models/"))
        ):
            raise _GeminiPageFailure(GeminiCatalogFailureCode.MALFORMED_RESPONSE)

        raw_capabilities = raw_model.get("supportedGenerationMethods")
        if raw_capabilities is None:
            capabilities = None
        elif isinstance(raw_capabilities, list) and all(
            isinstance(capability, str) for capability in raw_capabilities
        ):
            advertised = set(raw_capabilities) & _ALLOWED_CAPABILITIES
            capabilities = tuple(
                capability
                for capability in GeminiModelCapability
                if capability.value in advertised
            )
        else:
            raise _GeminiPageFailure(GeminiCatalogFailureCode.MALFORMED_RESPONSE)
        models.append(GeminiModel(model_id=name, capabilities=capabilities))
    return tuple(models), page_token


class GeminiModelCatalogAdapter:
    """List Gemini model IDs and selected capability metadata on explicit calls."""

    def __init__(self, configuration: GeminiAPIConfiguration) -> None:
        if not isinstance(configuration, GeminiAPIConfiguration):
            raise TypeError("configuration must be a GeminiAPIConfiguration")
        self._configuration = configuration

    def list_models(self) -> GeminiModelCatalogResult:
        models: list[GeminiModel] = []
        seen_model_ids: set[str] = set()
        page_token: str | None = None
        seen_page_tokens: set[str] = set()
        pages_requested = 0
        has_more = False

        while pages_requested < MAX_GEMINI_PAGES_PER_REQUEST:
            params = {"pageSize": str(MAX_GEMINI_MODELS_PER_PAGE)}
            if page_token is not None:
                params["pageToken"] = page_token
            pages_requested += 1
            try:
                with httpx.Client(
                    timeout=GEMINI_REQUEST_TIMEOUT_SECONDS,
                    follow_redirects=False,
                    trust_env=False,
                ) as client:
                    with client.stream(
                        "GET",
                        GEMINI_MODELS_ENDPOINT,
                        params=params,
                        headers={
                            "Accept": "application/json",
                            "x-goog-api-key": self._configuration.api_key,
                        },
                    ) as response:
                        response_body, _content_type = _read_response(response)
                page_models, page_token = _parse_page(response_body)
            except _GeminiPageFailure as failure:
                self._raise_failure(failure.code, pages_requested)
            except httpx.RequestError:
                self._raise_failure(
                    GeminiCatalogFailureCode.REQUEST_FAILED,
                    pages_requested,
                )

            if page_token is not None and self._contains_api_key(page_token):
                self._raise_failure(
                    GeminiCatalogFailureCode.MALFORMED_RESPONSE,
                    pages_requested,
                )
            for model in page_models:
                if (
                    model.model_id in seen_model_ids
                    or self._contains_api_key(model.model_id)
                ):
                    self._raise_failure(
                        GeminiCatalogFailureCode.MALFORMED_RESPONSE,
                        pages_requested,
                    )
                seen_model_ids.add(model.model_id)
                models.append(model)

            if page_token is None:
                has_more = False
                break
            has_more = True
            if page_token in seen_page_tokens:
                self._raise_failure(
                    GeminiCatalogFailureCode.MALFORMED_RESPONSE,
                    pages_requested,
                )
            seen_page_tokens.add(page_token)

        if len(models) > MAX_GEMINI_MODELS_PER_REQUEST:
            self._raise_failure(
                GeminiCatalogFailureCode.MALFORMED_RESPONSE,
                pages_requested,
            )

        retrieved_at = datetime.now(timezone.utc)
        audit_event = GeminiCatalogAuditEvent(
            service="gemini",
            operation="list_models",
            status=GeminiCatalogAuditStatus.SUCCEEDED,
            occurred_at=retrieved_at,
            pages_requested=pages_requested,
            model_count=len(models),
            has_more=has_more,
            failure_code=None,
        )
        return GeminiModelCatalogResult(
            models=tuple(models),
            has_more=has_more,
            retrieved_at=retrieved_at,
            audit_event=audit_event,
        )

    def _contains_api_key(self, value: str) -> bool:
        decoded_value = unquote(value)
        return (
            self._configuration.api_key in value
            or self._configuration.api_key in decoded_value
        )

    @staticmethod
    def _raise_failure(
        code: GeminiCatalogFailureCode,
        pages_requested: int,
    ) -> NoReturn:
        audit_event = GeminiCatalogAuditEvent(
            service="gemini",
            operation="list_models",
            status=GeminiCatalogAuditStatus.FAILED,
            occurred_at=datetime.now(timezone.utc),
            pages_requested=pages_requested,
            model_count=None,
            has_more=None,
            failure_code=code,
        )
        raise GeminiModelCatalogError(audit_event) from None
