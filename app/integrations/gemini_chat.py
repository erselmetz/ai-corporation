"""Bounded Gemini text generation; no retries, tools, or stored credentials."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from app.integrations.gemini_catalog import (
    GeminiAPIConfiguration,
    GeminiModelCatalogAdapter,
    GeminiModelCatalogError,
    GeminiModelCapability,
)
from app.providers.base import AIProvider

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"
_MAX_INPUT_BYTES = 32_768
_MAX_OUTPUT_TOKENS = 1_024
_MAX_RESPONSE_BYTES = 512 * 1024
_TIMEOUT_SECONDS = 20.0
_MAX_ELAPSED_SECONDS = 20.0
_MAX_CALLS_PER_KEY_PER_RUN = 5
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,255}$")


@dataclass(frozen=True, slots=True)
class GeminiConnection:
    configuration: GeminiAPIConfiguration = field(repr=False, compare=False)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: float = field(default_factory=lambda: time.monotonic() + 3600)
    models: tuple[str, ...] = ()


class GeminiConnectionError(ValueError):
    """An operator-safe, credential-free connection/setup failure."""


class GeminiCallLimit(ValueError):
    pass


class GeminiConnectionManager:
    """One local owner connection, held in process memory for at most one hour."""

    def __init__(self, *, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.RLock()
        self._connection: GeminiConnection | None = None
        self._calls_by_key: dict[bytes, int] = {}
        self._pending_keys: dict[bytes, int] = {}
        self._active = False
        self._target: tuple[str, str, str, str, str] | None = None
        self._target_key_identity: bytes | None = None

    def discover(self, api_key: str) -> GeminiConnection:
        try:
            config = GeminiAPIConfiguration(api_key)
        except (ValueError, TypeError, GeminiModelCatalogError):
            raise GeminiConnectionError("Gemini could not list models. Check the restricted API key and Gemini API access.") from None
        key_identity = hashlib.sha256(api_key.encode("utf-8")).digest()
        with self._lock:
            self._expire_locked()
            if self._active:
                raise GeminiConnectionError("A Gemini provider operation is active; wait before changing setup.")
            if self._target is not None and key_identity != self._target_key_identity:
                raise GeminiConnectionError("Disconnect the existing Gemini coordinator before replacing its credential.")
            if self._pending_keys:
                raise GeminiConnectionError("A Gemini model check is already active; wait before changing setup.")
            if key_identity not in self._calls_by_key and key_identity not in self._pending_keys:
                pending_new_keys = sum(identity not in self._calls_by_key for identity in self._pending_keys)
                if len(self._calls_by_key) + pending_new_keys >= 32:
                    raise GeminiConnectionError("The local app has reached its bounded number of Gemini connections; restart it to clear in-memory credentials.")
            self._pending_keys[key_identity] = self._pending_keys.get(key_identity, 0) + 1
            self._active = True
        try:
            result = GeminiModelCatalogAdapter(config).list_models()
            models = tuple(model.model_id for model in result.models
                           if model.capabilities is not None
                           and GeminiModelCapability.GENERATE_CONTENT in model.capabilities)
            if not models:
                raise GeminiConnectionError("Gemini returned no models advertising text generation.")
            connection = GeminiConnection(config, expires_at=self._clock() + 3600, models=models)
            with self._lock:
                self._expire_locked()
                self._finish_discovery_locked(key_identity, success=True)
                self._connection = connection
            return connection
        except GeminiConnectionError:
            raise
        except Exception:
            raise GeminiConnectionError("Gemini could not list models. Check the restricted API key and Gemini API access.") from None
        finally:
            with self._lock:
                if key_identity in self._pending_keys:
                    self._finish_discovery_locked(key_identity)
                self._active = False

    def _finish_discovery_locked(self, key_identity: bytes, *, success: bool = False):
        pending = self._pending_keys.get(key_identity, 0)
        if pending <= 1:
            self._pending_keys.pop(key_identity, None)
        else:
            self._pending_keys[key_identity] = pending - 1
        if success:
            self._calls_by_key.setdefault(key_identity, 0)

    def connection(self) -> GeminiConnection | None:
        with self._lock:
            self._expire_locked()
            return self._connection

    def _expire_locked(self):
        if self._connection is not None and self._connection.expires_at <= self._clock():
            self._connection = None

    def selected(self, agent_id: str) -> tuple[str, str, str, str, str] | None:
        with self._lock:
            self._expire_locked()
            return self._target if self._target and self._target[0] == agent_id else None

    def provider(
        self, api_key: str, model_id: str | None = None
    ) -> "GeminiProvider":
        key_identity = hashlib.sha256(api_key.encode("utf-8")).digest()
        return GeminiProvider(model_id, key_identity, self)

    def refresh(self) -> GeminiConnection:
        with self._lock:
            self._expire_locked()
            connection = self._connection
            if connection is None:
                raise GeminiConnectionError("Enter a restricted Gemini API key to list available models.")
            if self._active:
                raise GeminiConnectionError("A Gemini provider operation is active; wait before refreshing.")
            self._active = True
        try:
            result = GeminiModelCatalogAdapter(connection.configuration).list_models()
            models = tuple(model.model_id for model in result.models
                           if model.capabilities is not None
                           and GeminiModelCapability.GENERATE_CONTENT in model.capabilities)
            updated = GeminiConnection(connection.configuration, connection.created_at,
                                       datetime.now(timezone.utc), connection.expires_at, models)
            with self._lock:
                self._expire_locked()
                if self._connection is not connection:
                    raise GeminiConnectionError("Gemini connection changed; refresh the local setup.")
                self._connection = updated
            return updated
        except GeminiConnectionError:
            raise
        except Exception:
            raise GeminiConnectionError("Gemini model refresh failed. Check provider access and limits.") from None
        finally:
            with self._lock:
                self._active = False

    def select_model(self, agent_id: str, agent_name: str, provider_id: str,
                     previous_model: str, model_id: str) -> None:
        with self._lock:
            self._expire_locked()
            connection = self._connection
            if connection is None or model_id not in connection.models:
                raise GeminiConnectionError("Gemini model is not in the current verified inventory; reconnect and refresh.")
            if self._active:
                raise GeminiConnectionError("Gemini chat is active; wait before changing its connection.")
            if self._target and self._target[0] != agent_id:
                raise GeminiConnectionError("Disconnect the current coordinator before selecting another.")
            self._target = (agent_id, agent_name, provider_id, previous_model, model_id)
            self._target_key_identity = hashlib.sha256(
                connection.configuration.api_key.encode("utf-8")
            ).digest()

    def begin_call(self, key_identity: bytes, model_id: str) -> str:
        with self._lock:
            self._expire_locked()
            if self._connection is None:
                if self._target is not None:
                    raise GeminiConnectionError("Gemini connection expired; disconnect and reconnect in local setup.")
                raise GeminiConnectionError("Gemini is disconnected; connect again in local setup.")
            if self._connection.expires_at <= self._clock():
                self._connection = None
                raise GeminiConnectionError("Gemini connection expired; reconnect in local setup.")
            active_identity = hashlib.sha256(
                self._connection.configuration.api_key.encode("utf-8")
            ).digest()
            if not hmac.compare_digest(key_identity, active_identity):
                raise GeminiConnectionError("Gemini credential changed; reconnect the selected coordinator.")
            if model_id not in self._connection.models:
                raise GeminiConnectionError("Gemini model is no longer selected; reconnect in local setup.")
            if self._active:
                raise GeminiConnectionError("A Gemini request is already active; wait for it to finish.")
            count = self._calls_by_key.get(key_identity, 0)
            if count >= _MAX_CALLS_PER_KEY_PER_RUN:
                raise GeminiCallLimit("Gemini request allowance is used for this app run; disconnect and reconnect after review.")
            self._calls_by_key[key_identity] = count + 1
            self._active = True
            return self._connection.configuration.api_key

    def calls_used(self, connection: GeminiConnection) -> int:
        identity = hashlib.sha256(connection.configuration.api_key.encode("utf-8")).digest()
        with self._lock:
            return self._calls_by_key.get(identity, 0)

    def end_call(self):
        with self._lock:
            self._active = False

    def disconnect(self, agent_id: str):
        with self._lock:
            self._expire_locked()
            if self._active:
                raise GeminiConnectionError("Gemini chat is active; wait before disconnecting.")
            if self._target and self._target[0] != agent_id:
                raise GeminiConnectionError("Only the connected coordinator can disconnect Gemini.")
            target = self._target
            if target is None:
                raise GeminiConnectionError("No Gemini coordinator is connected.")
            self._target = None
            self._target_key_identity = None
            self._connection = None
            return target

    def clear_staged(self):
        """Erase a discovered but not assigned key after explicit user action."""
        with self._lock:
            self._expire_locked()
            if self._active:
                raise GeminiConnectionError("Gemini chat is active; wait before erasing setup.")
            if self._target is not None:
                raise GeminiConnectionError("Disconnect the assigned coordinator to erase its credential.")
            self._connection = None


class GeminiProvider(AIProvider):
    """Bounded verified-model generateContent adapter with no fallback."""

    requires_explicit_cloud_consent = True

    def __init__(self, model_id: str | None, key_identity: bytes,
                 manager: GeminiConnectionManager):
        if model_id is not None and not _MODEL_ID.fullmatch(model_id):
            raise ValueError("Gemini model identifier is invalid")
        self._model_id = model_id
        self._key_identity = key_identity
        self._manager = manager

    def generate(self, model: str, prompt: str) -> str:
        if (
            (self._model_id is not None and model != self._model_id)
            or not isinstance(model, str)
            or not _MODEL_ID.fullmatch(model)
            or not isinstance(prompt, str)
            or not prompt.strip()
        ):
            raise ValueError("Gemini request configuration is invalid")
        if len(prompt.encode("utf-8")) > _MAX_INPUT_BYTES:
            raise ValueError("Gemini input exceeds the byte limit")
        api_key = self._manager.begin_call(self._key_identity, model)
        started_at = time.monotonic()
        endpoint = f"{_ENDPOINT}/{model}:generateContent"
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                   "generationConfig": {"maxOutputTokens": _MAX_OUTPUT_TOKENS}}
        try:
            with httpx.Client(timeout=_TIMEOUT_SECONDS, follow_redirects=False,
                               trust_env=False) as client:
                with client.stream("POST", endpoint, headers={
                    "Accept": "application/json", "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                }, json=payload) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        if time.monotonic() - started_at > _MAX_ELAPSED_SECONDS:
                            raise ValueError("Gemini response exceeded the elapsed-time limit")
                        if len(body) + len(chunk) > _MAX_RESPONSE_BYTES:
                            raise ValueError("Gemini response exceeds the byte limit")
                        body.extend(chunk)
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError("Gemini response root must be an object")
            candidates = data.get("candidates")
            parts = candidates[0]["content"]["parts"] if isinstance(candidates, list) and candidates else None
            reply = "".join(part["text"] for part in parts
                            if isinstance(part, dict) and isinstance(part.get("text"), str)) if isinstance(parts, list) else ""
            if not reply.strip() or len(reply.encode("utf-8")) > 8192:
                raise ValueError("Gemini returned no bounded text reply")
            return reply
        except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError, UnicodeError):
            raise RuntimeError("Gemini response failed; check provider status and limits. No automatic retry occurred.") from None
        finally:
            self._manager.end_call()
