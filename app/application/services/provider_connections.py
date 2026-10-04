"""Explicit in-memory connections for supported local and online providers."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import re
from threading import RLock
import time
from urllib.parse import urlsplit

from app.integrations.gemini_chat import GeminiConnectionError, GeminiConnectionManager
from app.providers import AIProvider, OllamaProvider
from app.providers.base import ProviderCapacityError, ProviderCapacityUnknown


_CONNECTION_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


class ProviderConnectionConflict(ValueError):
    pass


class ProviderConnectionUnavailable(ValueError):
    pass


class ProviderRequestGate:
    """Process-local software request limits; not evidence of hardware fit."""

    MAX_CONNECTIONS = 32
    MAX_GLOBAL_SLOTS = 32
    MAX_CONNECTION_SLOTS = 16

    def __init__(self):
        self._limits: dict[str, int] = {}
        self._active: dict[str, int] = {}
        self._active_models: dict[tuple[str, str], int] = {}
        self._lock = RLock()

    def validate_configuration(self, provider_id: str, request_slots: int) -> None:
        if type(request_slots) is not int or not 1 <= request_slots <= self.MAX_CONNECTION_SLOTS:
            raise ValueError("Request slots must be an integer from 1 to 16")
        with self._lock:
            if provider_id not in self._limits and len(self._limits) >= self.MAX_CONNECTIONS:
                raise ProviderConnectionConflict("Provider connection limit reached for this app run")
            total = sum(self._limits.values()) + (
                request_slots if provider_id not in self._limits else 0
            )
            if total > self.MAX_GLOBAL_SLOTS:
                raise ProviderConnectionConflict("Configured global request-slot limit would be exceeded")

    def configure(self, provider_id: str, request_slots: int) -> None:
        self.validate_configuration(provider_id, request_slots)
        with self._lock:
            self._limits[provider_id] = request_slots

    @contextmanager
    def reserve(self, provider_id: str, model_id: str):
        with self._lock:
            slots = self._limits.get(provider_id)
            if slots is None:
                raise ProviderCapacityUnknown(
                    "UNKNOWN provider request capacity; configure this connection before sending"
                )
            total_slots = sum(self._limits.values())
            model_key = (provider_id, model_id)
            if (
                sum(self._active.values()) >= total_slots
                or self._active.get(provider_id, 0) >= slots
                or self._active_models.get(model_key, 0) >= slots
            ):
                raise ProviderCapacityError(
                    "Configured provider/model request-slot capacity is exhausted"
                )
            self._active[provider_id] = self._active.get(provider_id, 0) + 1
            self._active_models[model_key] = self._active_models.get(model_key, 0) + 1
        try:
            yield
        finally:
            with self._lock:
                self._active[provider_id] -= 1
                self._active_models[model_key] -= 1

    def remove(self, provider_id: str) -> None:
        with self._lock:
            if self._active.get(provider_id, 0):
                raise ProviderConnectionConflict("Provider has an active request")
            self._limits.pop(provider_id, None)
            self._active.pop(provider_id, None)
            for key in tuple(self._active_models):
                if key[0] == provider_id:
                    self._active_models.pop(key, None)

    def capacity(self, provider_id: str) -> dict[str, int | str]:
        with self._lock:
            slots = self._limits.get(provider_id)
            if slots is None:
                return {"state": "unknown"}
            return {
                "state": "configured",
                "global_slots": sum(self._limits.values()),
                "provider_slots": slots,
                "active_requests": self._active.get(provider_id, 0),
                "model_slots": slots,
            }


class _ConnectionProvider(AIProvider):
    def __init__(self, provider_id: str, provider: AIProvider, gate: ProviderRequestGate):
        self._provider_id = provider_id
        self._provider = provider
        self._gate = gate

    @property
    def requires_explicit_cloud_consent(self) -> bool:
        return getattr(self._provider, "requires_explicit_cloud_consent", False) is True

    def generate(self, model: str, prompt: str) -> str:
        with self._gate.reserve(self._provider_id, model):
            return self._provider.generate(model, prompt)

    def check_availability(self):
        return self._provider.check_availability()

    def local_model_inventory(self):
        return self._provider.local_model_inventory()


@dataclass(frozen=True, slots=True)
class _Connection:
    id: str
    name: str
    provider_type: str
    provider: AIProvider = field(repr=False, compare=False)
    request_slots: int
    models: tuple[str, ...] = ()
    state: str = "unknown"
    source: str = "unknown"
    checked_at: datetime | None = None
    manager: GeminiConnectionManager | None = field(
        default=None, repr=False, compare=False
    )
    expires_at: float | None = None


class ProviderConnectionsService:
    """Owner-configured connection records; credentials never leave process memory."""

    LOCAL_CATALOG_MAX_AGE_SECONDS = 300

    def __init__(
        self,
        application,
        *,
        ollama_factory=OllamaProvider,
        gemini_manager_factory=GeminiConnectionManager,
        clock=None,
    ):
        self._application = application
        self._ollama_factory = ollama_factory
        self._gemini_manager_factory = gemini_manager_factory
        self._clock = clock
        self._gate = ProviderRequestGate()
        self._connections: dict[str, _Connection] = {}
        self._lock = RLock()

    @staticmethod
    def _provider_id(provider_type: str, connection_id: str) -> str:
        if (
            not isinstance(connection_id, str)
            or not _CONNECTION_ID.fullmatch(connection_id)
        ):
            raise ValueError("Connection ID must be lowercase letters, numbers, hyphens or underscores")
        return f"{provider_type}-{connection_id}"

    @staticmethod
    def _validate_name(name: str) -> None:
        if (
            not isinstance(name, str)
            or not name.strip()
            or len(name.encode("utf-8")) > 256
        ):
            raise ValueError("Connection name must contain 1 to 256 UTF-8 bytes")

    @staticmethod
    def _validate_loopback_url(base_url: str) -> str:
        if not isinstance(base_url, str) or len(base_url.encode("utf-8")) > 2048:
            raise ValueError("Ollama URL is invalid")
        try:
            endpoint = urlsplit(base_url)
            port = endpoint.port
        except ValueError:
            raise ValueError("Ollama URL is invalid") from None
        if (
            endpoint.scheme != "http"
            or endpoint.hostname not in _LOOPBACK_HOSTS
            or endpoint.username is not None
            or endpoint.password is not None
            or endpoint.path
            or endpoint.query
            or endpoint.fragment
            or (port is not None and not 1 <= port <= 65535)
        ):
            raise ValueError("Ollama connections require a loopback HTTP URL without path or credentials")
        return base_url.rstrip("/")

    def _ensure_available_id(self, provider_id: str, request_slots: int) -> None:
        if self._application.provider_exists(provider_id):
            raise ProviderConnectionConflict("Provider ID is already configured")
        self._gate.validate_configuration(provider_id, request_slots)

    def _register(
        self,
        provider_id: str,
        provider: AIProvider,
        request_slots: int,
    ) -> None:
        self._gate.configure(provider_id, request_slots)
        try:
            self._application.register_local_provider(
                provider_id, _ConnectionProvider(provider_id, provider, self._gate)
            )
        except Exception:
            self._gate.remove(provider_id)
            raise

    def add_ollama(
        self,
        connection_id: str,
        name: str,
        base_url: str,
        request_slots: int,
    ) -> dict:
        self._validate_name(name)
        base_url = self._validate_loopback_url(base_url)
        provider_id = self._provider_id("ollama", connection_id)
        with self._lock:
            self._ensure_available_id(provider_id, request_slots)
            provider = self._ollama_factory(base_url)
            self._register(provider_id, provider, request_slots)
            record = _Connection(
                provider_id, name.strip(), "ollama", provider, request_slots
            )
            self._connections[provider_id] = record
        return self.refresh(provider_id)

    def add_gemini(
        self,
        connection_id: str,
        name: str,
        api_key: str,
        request_slots: int,
    ) -> dict:
        self._validate_name(name)
        provider_id = self._provider_id("gemini", connection_id)
        if request_slots != 1:
            raise ValueError("Gemini connections support one in-flight request per connection")
        with self._lock:
            self._ensure_available_id(provider_id, request_slots)
            manager = self._gemini_manager_factory(
                **({"clock": self._clock} if self._clock is not None else {})
            )
            try:
                connection = manager.discover(api_key)
                provider = manager.provider(api_key, None)
            except GeminiConnectionError as error:
                raise ProviderConnectionUnavailable(str(error)) from None
            self._register(provider_id, provider, request_slots)
            self._connections[provider_id] = _Connection(
                provider_id,
                name.strip(),
                "gemini",
                provider,
                request_slots,
                tuple(connection.models),
                "available",
                "gemini:/v1beta/models",
                connection.checked_at,
                manager,
                connection.expires_at,
            )
        return self.get(provider_id)

    def list(self) -> tuple[dict, ...]:
        with self._lock:
            return tuple(self._status(record) for record in self._connections.values())

    def get(self, provider_id: str) -> dict:
        with self._lock:
            record = self._connections.get(provider_id)
            if record is None:
                raise ProviderConnectionUnavailable("Provider connection is not configured")
            return self._status(record)

    def _status(self, record: _Connection) -> dict:
        state = record.state
        models = record.models
        checked_at = record.checked_at
        expires_in_seconds = None
        if record.manager is not None:
            current = record.manager.connection()
            if current is None:
                now = self._clock() if self._clock is not None else time.monotonic()
                state = "expired" if record.expires_at is not None and record.expires_at <= now else "unavailable"
                models = ()
            else:
                models = current.models
                checked_at = current.checked_at
                if not models:
                    state = "empty"
                expires_in_seconds = max(
                    0,
                    int(
                        current.expires_at
                        - (self._clock() if self._clock is not None else time.monotonic())
                    ),
                )
        elif state == "available":
            if checked_at is None:
                state = "unknown"
            else:
                checked_at_utc = (
                    checked_at.replace(tzinfo=timezone.utc)
                    if checked_at.tzinfo is None
                    else checked_at.astimezone(timezone.utc)
                )
                age_seconds = (datetime.now(timezone.utc) - checked_at_utc).total_seconds()
                if age_seconds < 0:
                    state = "unknown"
                elif age_seconds > self.LOCAL_CATALOG_MAX_AGE_SECONDS:
                    state = "stale"
                elif not models:
                    state = "empty"
        return {
            "provider_id": record.id,
            "name": record.name,
            "provider_type": record.provider_type,
            "state": state,
            "models": list(models),
            "source": record.source,
            "checked_at": checked_at.isoformat() if checked_at else None,
            "expires_in_seconds": expires_in_seconds,
            "request_capacity": self._gate.capacity(record.id),
            "hardware_feasibility": "unknown",
        }

    def refresh(self, provider_id: str) -> dict:
        with self._lock:
            record = self._connections.get(provider_id)
            if record is None:
                raise ProviderConnectionUnavailable("Provider connection is not configured")
        if record.manager is not None:
            try:
                connection = record.manager.refresh()
            except GeminiConnectionError as error:
                raise ProviderConnectionUnavailable(str(error)) from None
            updated = replace(
                record,
                models=connection.models,
                state="available" if connection.models else "unknown",
                checked_at=connection.checked_at,
                expires_at=connection.expires_at,
            )
        else:
            inventory = record.provider.local_model_inventory()
            updated = replace(
                record,
                models=inventory.models,
                state=inventory.state,
                source=inventory.source,
                checked_at=inventory.checked_at,
            )
        with self._lock:
            if self._connections.get(provider_id) is not record:
                raise ProviderConnectionConflict("Provider connection changed during refresh")
            self._connections[provider_id] = updated
            return self._status(updated)

    def assign(
        self,
        agent_id: str,
        provider_id: str,
        model_id: str,
        expected_provider_id: str,
        expected_model_id: str,
    ):
        status = self.refresh(provider_id)
        if status["state"] != "available":
            raise ProviderConnectionConflict(
                "Provider catalog is not freshly available; refresh and confirm a supported model"
            )
        with self._lock:
            record = self._connections.get(provider_id)
            if record is None:
                raise ProviderConnectionUnavailable("Provider connection is not configured")
            if self._status(record)["state"] != "available":
                raise ProviderConnectionConflict(
                    "Provider catalog is not freshly available; refresh and confirm a supported model"
                )
            if model_id not in record.models:
                raise ProviderConnectionConflict("Model is not in the current verified connection catalog")
            with self._application.agent_assignment_change(agent_id):
                agent = self._application.get_agent(agent_id)
                if (
                    agent.provider != expected_provider_id
                    or agent.model != expected_model_id
                ):
                    raise ProviderConnectionConflict("Agent assignment changed; refresh before confirming")
                result = self._application._replace_model_unchecked(
                    agent_id, provider_id, model_id
                )
                return {
                    "agent_id": result.agent_id,
                    "provider_id": result.provider_id,
                    "model_id": result.model_id,
                }

    def remove(self, provider_id: str) -> None:
        with self._lock:
            record = self._connections.get(provider_id)
            if record is None:
                raise ProviderConnectionUnavailable("Provider connection is not configured")
            if any(item.provider_id == provider_id for item in self._application.list_models()):
                raise ProviderConnectionConflict("Reassign Agents before removing this provider connection")
            self._gate.remove(provider_id)
            if record.manager is not None:
                try:
                    record.manager.clear_staged()
                except GeminiConnectionError as error:
                    self._gate.configure(provider_id, record.request_slots)
                    raise ProviderConnectionConflict(str(error)) from None
            self._application.remove_local_provider(provider_id)
            del self._connections[provider_id]
