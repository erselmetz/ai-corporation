from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import AuthenticatedPrincipal, create_app
from app.application.services.provider_connections import (
    ProviderConnectionConflict,
    ProviderConnectionsService,
    ProviderRequestGate,
)
from app.integrations.gemini_chat import GeminiConnectionError
from app.local import create_local_app
from app.providers import AIProvider
from app.providers.base import ProviderCapacityError, ProviderCapacityUnknown
from app.providers.inventory import LocalModelInventory
from app.runtime.factory import create_corporation_runtime


PASSWORD = "test-owner-passphrase"
ORIGIN = "http://127.0.0.1:8000"
API_KEY = "AIza" + "A" * 35


class FakeOllama(AIProvider):
    def __init__(self, base_url):
        self.base_url = base_url
        self.model = f"local-{base_url.rsplit(':', 1)[-1]}"
        self.calls = []

    def local_model_inventory(self):
        return LocalModelInventory(
            "available", (self.model,), True, source="deterministic-local"
        )

    def generate(self, model, prompt):
        self.calls.append((model, prompt))
        return "local fake reply"


class StaleFakeOllama(FakeOllama):
    def local_model_inventory(self):
        return LocalModelInventory(
            "available",
            (self.model,),
            True,
            checked_at=datetime.now(timezone.utc) - timedelta(
                seconds=ProviderConnectionsService.LOCAL_CATALOG_MAX_AGE_SECONDS + 1
            ),
            source="deterministic-stale",
        )


class EmptyFakeOllama(FakeOllama):
    def local_model_inventory(self):
        return LocalModelInventory(
            "available", (), True, source="deterministic-empty"
        )


class UnknownFakeOllama(FakeOllama):
    def local_model_inventory(self):
        return LocalModelInventory(
            "unknown",
            (),
            False,
            checked_at=datetime.now(timezone.utc) - timedelta(days=1),
            source="deterministic-unknown",
        )


class MissingTimestampFakeOllama(FakeOllama):
    def local_model_inventory(self):
        return LocalModelInventory(
            "available",
            (self.model,),
            True,
            checked_at=None,
            source="deterministic-missing-timestamp",
        )


class FakeGemini(AIProvider):
    requires_explicit_cloud_consent = True

    def __init__(self):
        self.calls = []
        self.entered = Event()
        self.release = Event()
        self.block = False

    def generate(self, model, prompt):
        self.calls.append((model, prompt))
        if self.block:
            self.entered.set()
            if not self.release.wait(5):
                raise RuntimeError("Test did not release fake provider")
        return "online fake reply"


class FakeGeminiManager:
    instances = []

    def __init__(self):
        self._connection = None
        self._provider = FakeGemini()
        self.api_key = None
        self.__class__.instances.append(self)

    def discover(self, api_key):
        self.api_key = api_key
        index = len(self.instances)
        self._connection = SimpleNamespace(
            models=(f"remote-model-{index}",),
            checked_at=datetime.now(timezone.utc),
            expires_at=time.monotonic() + 3600,
        )
        return self._connection

    def provider(self, api_key, _model_id):
        assert api_key == self.api_key
        assert _model_id is None
        return self._provider

    def connection(self):
        return self._connection

    def refresh(self):
        return self._connection

    def clear_staged(self):
        self.api_key = None
        self._connection = None


def make_connections(runtime):
    FakeGeminiManager.instances = []
    return ProviderConnectionsService(
        runtime.application_service,
        ollama_factory=FakeOllama,
        gemini_manager_factory=FakeGeminiManager,
    )


def sign_in(client):
    assert client.post(
        "/api/local/login",
        json={"password": PASSWORD},
        headers={"Origin": ORIGIN},
    ).status_code == 200
    return {
        "Origin": ORIGIN,
        "X-Local-CSRF": client.get("/api/local/session").json()["csrf"],
    }


def test_multiple_local_and_online_connections_catalogs_and_secret_boundaries():
    runtime = create_corporation_runtime()
    service = make_connections(runtime)
    service.add_ollama("workstation", "Workstation", "http://localhost:11434", 2)
    service.add_ollama("lab", "Lab", "http://127.0.0.1:11435", 1)
    secrets = [
        "AIza" + character * 35
        for character in ("A", "B", "C")
    ]
    for index, api_key in enumerate(secrets, start=1):
        service.add_gemini(f"account-{index}", f"Online {index}", api_key, 1)

    records = service.list()
    assert [record["provider_id"] for record in records] == [
        "ollama-workstation",
        "ollama-lab",
        "gemini-account-1",
        "gemini-account-2",
        "gemini-account-3",
    ]
    assert [record["models"] for record in records] == [
        ["local-11434"],
        ["local-11435"],
        ["remote-model-1"],
        ["remote-model-2"],
        ["remote-model-3"],
    ]
    assert all(record["state"] == "available" for record in records)
    assert all(record["source"] != "unknown" for record in records)
    assert all(record["hardware_feasibility"] == "unknown" for record in records)
    assert [record["request_capacity"]["provider_slots"] for record in records] == [
        2, 1, 1, 1, 1
    ]
    serialized = repr(records)
    assert all(api_key not in serialized for api_key in secrets)
    assert all(api_key not in repr(service) for api_key in secrets)

    original = runtime.application_service.get_model_assignment("local_worker")
    assigned = service.assign(
        "local_worker",
        "gemini-account-1",
        "remote-model-1",
        original.provider_id,
        original.model_id,
    )
    assert (assigned["provider_id"], assigned["model_id"]) == (
        "gemini-account-1",
        "remote-model-1",
    )
    with pytest.raises(ProviderConnectionConflict, match="assignment changed"):
        service.assign(
            "local_worker",
            "gemini-account-2",
            "remote-model-2",
            original.provider_id,
            original.model_id,
        )
    with pytest.raises(ProviderConnectionConflict, match="Reassign Agents"):
        service.remove("gemini-account-1")

    service.assign(
        "local_worker",
        "ollama-workstation",
        "local-11434",
        "gemini-account-1",
        "remote-model-1",
    )
    service.remove("gemini-account-1")
    assert [item["provider_id"] for item in service.list()] == [
        "ollama-workstation",
        "ollama-lab",
        "gemini-account-2",
        "gemini-account-3",
    ]


def test_loopback_validation_and_request_capacity_fail_closed():
    runtime = create_corporation_runtime()
    factory_urls = []

    def factory(url):
        factory_urls.append(url)
        return FakeOllama(url)

    service = ProviderConnectionsService(
        runtime.application_service,
        ollama_factory=factory,
        gemini_manager_factory=FakeGeminiManager,
    )
    for url in (
        "https://localhost:11434",
        "http://example.com:11434",
        "http://user:pass@localhost:11434",
        "http://localhost:11434/path",
    ):
        with pytest.raises(ValueError):
            service.add_ollama("bad", "Bad", url, 1)
    assert factory_urls == []

    gate = ProviderRequestGate()
    with pytest.raises(ValueError, match="integer"):
        gate.validate_configuration("boolean-slots", True)
    with pytest.raises(ProviderCapacityUnknown, match="UNKNOWN"):
        with gate.reserve("missing", "model"):
            pytest.fail("Unknown capacity must deny request admission")
    gate.configure("local-one", 1)
    with gate.reserve("local-one", "model"):
        with pytest.raises(ProviderCapacityError, match="capacity is exhausted"):
            with gate.reserve("local-one", "model"):
                pytest.fail("The configured request-slot limit must be enforced")
    assert gate.capacity("local-one")["active_requests"] == 0


def test_stale_and_empty_catalogs_are_truthful_and_cannot_be_assigned():
    runtime = create_corporation_runtime()
    stale_service = ProviderConnectionsService(
        runtime.application_service,
        ollama_factory=StaleFakeOllama,
    )
    stale = stale_service.add_ollama(
        "stale", "Stale", "http://localhost:11436", 1
    )
    assert stale["state"] == "stale"
    assert stale["models"] == ["local-11436"]
    original = runtime.application_service.get_model_assignment("local_worker")
    with pytest.raises(ProviderConnectionConflict, match="not freshly available"):
        stale_service.assign(
            "local_worker",
            "ollama-stale",
            "local-11436",
            original.provider_id,
            original.model_id,
        )

    empty_service = ProviderConnectionsService(
        runtime.application_service,
        ollama_factory=EmptyFakeOllama,
    )
    empty = empty_service.add_ollama(
        "empty", "Empty", "http://localhost:11437", 1
    )
    assert empty["state"] == "empty"
    assert empty["models"] == []

    unknown_service = ProviderConnectionsService(
        runtime.application_service,
        ollama_factory=UnknownFakeOllama,
    )
    unknown = unknown_service.add_ollama(
        "unknown", "Unknown", "http://localhost:11438", 1
    )
    assert unknown["state"] == "unknown"

    missing_timestamp_service = ProviderConnectionsService(
        runtime.application_service,
        ollama_factory=MissingTimestampFakeOllama,
    )
    missing_timestamp = missing_timestamp_service.add_ollama(
        "missing-time", "Missing timestamp", "http://localhost:11439", 1
    )
    assert missing_timestamp["state"] == "unknown"


def test_busy_credential_erasure_preserves_connection_capacity_state():
    runtime = create_corporation_runtime()
    service = make_connections(runtime)
    service.add_gemini("busy", "Busy", API_KEY, 1)
    manager = FakeGeminiManager.instances[0]

    def reject_clear():
        raise GeminiConnectionError("Gemini chat is active")

    manager.clear_staged = reject_clear
    with pytest.raises(ProviderConnectionConflict, match="chat is active"):
        service.remove("gemini-busy")
    status = service.get("gemini-busy")
    assert status["request_capacity"]["state"] == "configured"
    assert runtime.application_service.provider_exists("gemini-busy")


def test_local_owner_api_authorization_catalog_and_secret_non_disclosure():
    runtime = create_corporation_runtime()
    service = make_connections(runtime)
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)
    app.state.provider_connections_service = service

    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50000)) as client:
        assert client.get("/api/local/provider-connections").status_code == 401
        headers = sign_in(client)
        assert client.get("/api/local/provider-connections", headers=headers).json() == {
            "items": [],
            "capacity": {
                "global_request_slots": 0,
                "hardware_feasibility": "unknown",
            },
        }

        client.app.state.authentication_backend.principal = AuthenticatedPrincipal(
            "local-owner", frozenset({"provider-connection:read"})
        )
        denied = client.post(
            "/api/local/provider-connections/gemini",
            headers=headers,
            json={
                "id": "private",
                "name": "Private",
                "api_key": API_KEY,
                "request_slots": 1,
            },
        )
        assert denied.status_code == 403
        assert API_KEY not in denied.text

        client.app.state.authentication_backend.principal = AuthenticatedPrincipal(
            "local-owner",
            frozenset(
                {"provider-connection:read", "provider-connection:manage"}
            ),
        )
        added = client.post(
            "/api/local/provider-connections/gemini",
            headers=headers,
            json={
                "id": "private",
                "name": "Private",
                "api_key": API_KEY,
                "request_slots": 1,
            },
        )
        assert added.status_code == 201
        assert API_KEY not in added.text
        listed = client.get("/api/local/provider-connections", headers=headers)
        assert listed.status_code == 200
        assert API_KEY not in listed.text
        assert listed.json()["items"][0]["models"] == ["remote-model-1"]

        rejected = client.post(
            "/api/local/provider-connections/ollama",
            headers=headers,
            json={
                "id": "remote",
                "name": "Remote",
                "base_url": "http://example.com:11434",
                "request_slots": 1,
            },
        )
        assert rejected.status_code == 422
        assert factory_not_called(service)
        invalid_slots = client.post(
            "/api/local/provider-connections/ollama",
            headers=headers,
            json={
                "id": "invalid-slots",
                "name": "Invalid slots",
                "base_url": "http://localhost:11434",
                "request_slots": True,
            },
        )
        assert invalid_slots.status_code == 422
        assert factory_not_called(service)

    with TestClient(create_app(application_service=runtime.application_service)) as default:
        assert default.get("/api/local/provider-connections").status_code == 404


def test_new_gemini_connection_requires_consent_for_coordinator_and_employee_chat():
    runtime = create_corporation_runtime()
    service = make_connections(runtime)
    service.add_ollama("local", "Local", "http://localhost:11434", 1)
    service.add_gemini("work", "Work account", API_KEY, 1)
    original = runtime.application_service.get_model_assignment("local_worker")
    online_assignment = service.assign(
        "local_worker",
        "gemini-work",
        "remote-model-1",
        original.provider_id,
        original.model_id,
    )
    provider = FakeGeminiManager.instances[0]._provider
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)

    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50001)) as client:
        headers = sign_in(client)
        existing_employee = client.post(
            "/api/employee-chat/conversations",
            headers=headers,
            json={"employee_id": "local_employee"},
        )
        assert existing_employee.status_code == 201
        existing_path = (
            f"/api/employee-chat/conversations/"
            f"{existing_employee.json()['conversation']['id']}/messages"
        )
        service.assign(
            "local_worker",
            "ollama-local",
            "local-11434",
            online_assignment["provider_id"],
            online_assignment["model_id"],
        )
        stale = client.post(
            existing_path, headers=headers, json={"text": "must keep its snapshot"}
        )
        assert stale.status_code == 409
        assert provider.calls == []
        local_assignment = runtime.application_service.get_model_assignment(
            "local_worker"
        )
        service.assign(
            "local_worker",
            "gemini-work",
            "remote-model-1",
            local_assignment.provider_id,
            local_assignment.model_id,
        )

        coordinator = client.post(
            "/api/chat/conversations",
            headers=headers,
            json={"agent_id": "local_worker"},
        )
        assert coordinator.status_code == 200
        coordinator_path = (
            f"/api/chat/conversations/{coordinator.json()['conversation']['id']}/messages"
        )
        denied = client.post(
            coordinator_path, headers=headers, json={"text": "private question"}
        )
        assert denied.status_code == 403
        assert provider.calls == []
        accepted = client.post(
            coordinator_path,
            headers=headers,
            json={"text": "private question", "cloud_consent": True},
        )
        assert accepted.status_code == 200
        assert len(provider.calls) == 1

        employee = client.post(
            "/api/employee-chat/conversations",
            headers=headers,
            json={"employee_id": "local_employee"},
        )
        assert employee.status_code == 201
        employee_path = (
            f"/api/employee-chat/conversations/"
            f"{employee.json()['conversation']['id']}/messages"
        )
        denied = client.post(
            employee_path, headers=headers, json={"text": "private question"}
        )
        assert denied.status_code == 403
        assert len(provider.calls) == 1
        accepted = client.post(
            employee_path,
            headers=headers,
            json={"text": "private question", "cloud_consent": True},
        )
        assert accepted.status_code == 200
        assert len(provider.calls) == 2


def test_provider_slot_exhaustion_is_reported_without_fallback():
    runtime = create_corporation_runtime()
    service = make_connections(runtime)
    service.add_gemini("work", "Work account", API_KEY, 1)
    original = runtime.application_service.get_model_assignment("local_worker")
    service.assign(
        "local_worker",
        "gemini-work",
        "remote-model-1",
        original.provider_id,
        original.model_id,
    )
    provider = FakeGeminiManager.instances[0]._provider
    provider.block = True
    app = create_local_app(password=PASSWORD, application_service=runtime.application_service)

    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 50002)) as client:
        headers = sign_in(client)
        first = client.post(
            "/api/chat/conversations",
            headers=headers,
            json={"agent_id": "local_worker"},
        )
        second = client.post(
            "/api/chat/conversations",
            headers=headers,
            json={"agent_id": "local_worker"},
        )
        assert first.status_code == second.status_code == 200
        first_path = (
            f"/api/chat/conversations/{first.json()['conversation']['id']}/messages"
        )
        second_path = (
            f"/api/chat/conversations/{second.json()['conversation']['id']}/messages"
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(
                client.post,
                first_path,
                headers=headers,
                json={"text": "first", "cloud_consent": True},
            )
            assert provider.entered.wait(3)
            rejected = client.post(
                second_path,
                headers=headers,
                json={"text": "second", "cloud_consent": True},
            )
            assert rejected.status_code == 429
            assert "request-slot capacity is exhausted" in rejected.text
            assert len(provider.calls) == 1
            provider.release.set()
            assert pending.result(timeout=5).status_code == 200


def factory_not_called(service):
    return not any(record["provider_type"] == "ollama" for record in service.list())
