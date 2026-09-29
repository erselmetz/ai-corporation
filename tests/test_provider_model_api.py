from unittest.mock import MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.agents import Agent, AgentRegistry, EmployeeRegistry
from app.api import AuthenticatedPrincipal, create_app
from app.application import CorporationApplicationService
from app.orchestrator import Orchestrator, ProjectRegistry, TaskRegistry
from app.providers import OllamaProvider, ProviderRegistry


class ProviderModelTestAuthenticationBackend:
    def authenticate(self, request: Request) -> AuthenticatedPrincipal | None:
        permissions = {
            "provider-reader": frozenset({"provider:read"}),
            "provider-manager": frozenset({"provider:manage"}),
            "model-reader": frozenset({"model:read"}),
            "model-manager": frozenset({"model:manage"}),
            "other-reader": frozenset({"agent:read"}),
        }.get(request.headers.get("Authorization", ""))
        if permissions is None:
            return None
        return AuthenticatedPrincipal(identity="test-user", permissions=permissions)


@pytest.fixture
def provider_model_api():
    providers = ProviderRegistry()
    providers.register(
        "local",
        OllamaProvider("http://user:password@localhost:11434?api_key=secret"),
    )
    agents = AgentRegistry()
    agents.register(
        Agent(
            id="agent-1",
            name="Worker",
            role="Researcher",
            provider="local",
            model="local-model",
        )
    )
    orchestrator = Orchestrator(
        agents=agents,
        providers=providers,
        tasks=TaskRegistry(),
        projects=ProjectRegistry(),
        employees=EmployeeRegistry(),
    )
    service = CorporationApplicationService(orchestrator)
    for method in (
        "list_providers",
        "get_provider",
        "create_provider",
        "remove_provider",
        "list_models",
        "get_model_assignment",
        "replace_model",
    ):
        setattr(
            service,
            method,
            MagicMock(wraps=getattr(service, method)),
        )
    application = create_app(
        service,
        ProviderModelTestAuthenticationBackend(),
    )
    return application, service, providers, agents


@pytest.mark.parametrize(
    ("path", "method", "permission"),
    [
        ("/api/providers", "get", "provider:read"),
        ("/api/providers/local", "get", "provider:read"),
        ("/api/models", "get", "model:read"),
        ("/api/models/agent-1", "get", "model:read"),
    ],
)
def test_provider_and_model_reads_enforce_authentication_and_permissions(
    provider_model_api,
    path: str,
    method: str,
    permission: str,
):
    application, _, _, _ = provider_model_api
    wrong_permission = (
        "model-reader" if permission == "provider:read" else "provider-reader"
    )

    with TestClient(application) as client:
        unauthenticated = getattr(client, method)(path)
        forbidden = getattr(client, method)(
            path,
            headers={"Authorization": wrong_permission},
        )

    assert unauthenticated.status_code == 401
    assert forbidden.status_code == 403


def test_provider_reads_use_service_and_expose_only_safe_schema(provider_model_api):
    application, service, _, _ = provider_model_api

    with TestClient(application) as client:
        collection = client.get(
            "/api/providers",
            headers={"Authorization": "provider-reader"},
        )
        detail = client.get(
            "/api/providers/local",
            headers={"Authorization": "provider-reader"},
        )

    assert collection.status_code == 200
    assert collection.json() == {
        "items": [{"id": "local", "type": "OllamaProvider"}],
    }
    assert detail.status_code == 200
    assert detail.json() == {"id": "local", "type": "OllamaProvider"}
    assert service.list_providers.call_count == 1
    service.get_provider.assert_called_once_with("local")
    response_text = collection.text + detail.text
    assert "password" not in response_text
    assert "secret" not in response_text
    assert "localhost" not in response_text
    assert "base_url" not in response_text


def test_unknown_provider_returns_404(provider_model_api):
    application, _, _, _ = provider_model_api

    with TestClient(application) as client:
        response = client.get(
            "/api/providers/unknown",
            headers={"Authorization": "provider-reader"},
        )

    assert response.status_code == 404


def test_provider_management_uses_application_service_and_returns_http_statuses(
    provider_model_api,
):
    application, service, providers, _ = provider_model_api

    with TestClient(application) as client:
        denied = client.post(
            "/api/providers",
            headers={"Authorization": "provider-reader"},
            json={"id": "created", "name": "Created Provider"},
        )
        created = client.post(
            "/api/providers",
            headers={"Authorization": "provider-manager"},
            json={"id": "created", "name": "Created Provider"},
        )
        duplicate = client.post(
            "/api/providers",
            headers={"Authorization": "provider-manager"},
            json={"id": "created", "name": "Duplicate"},
        )
        invalid = client.post(
            "/api/providers",
            headers={"Authorization": "provider-manager"},
            json={"id": " ", "name": "Invalid"},
        )
        delete_denied = client.delete(
            "/api/providers/created",
            headers={"Authorization": "provider-reader"},
        )
        deleted = client.delete(
            "/api/providers/created",
            headers={"Authorization": "provider-manager"},
        )
        missing = client.delete(
            "/api/providers/unknown",
            headers={"Authorization": "provider-manager"},
        )

    assert denied.status_code == 403
    assert created.status_code == 201
    assert created.json() == {"id": "created", "type": "OllamaProvider"}
    assert duplicate.status_code == 409
    assert invalid.status_code == 422
    assert delete_denied.status_code == 403
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert missing.status_code == 404
    assert service.create_provider.call_count == 2
    assert service.remove_provider.call_count == 2
    assert not providers.exists("created")


def test_model_reads_return_agent_assignments_without_provider_internals(
    provider_model_api,
):
    application, service, _, _ = provider_model_api

    with TestClient(application) as client:
        collection = client.get(
            "/api/models",
            headers={"Authorization": "model-reader"},
        )
        detail = client.get(
            "/api/models/agent-1",
            headers={"Authorization": "model-reader"},
        )

    expected_assignment = {
        "agent_id": "agent-1",
        "provider_id": "local",
        "model_id": "local-model",
    }
    assert collection.status_code == 200
    assert collection.json() == {"items": [expected_assignment]}
    assert detail.status_code == 200
    assert detail.json() == expected_assignment
    assert service.list_models.call_count == 1
    service.get_model_assignment.assert_called_once_with("agent-1")
    assert "password" not in collection.text + detail.text
    assert "secret" not in collection.text + detail.text
    assert "base_url" not in collection.text + detail.text


def test_unknown_agent_model_assignment_returns_404(provider_model_api):
    application, _, _, _ = provider_model_api

    with TestClient(application) as client:
        response = client.get(
            "/api/models/unknown",
            headers={"Authorization": "model-reader"},
        )

    assert response.status_code == 404


def test_model_replacement_uses_existing_assignment_service(provider_model_api):
    application, service, _, agents = provider_model_api

    with TestClient(application) as client:
        denied = client.put(
            "/api/models/agent-1",
            headers={"Authorization": "model-reader"},
            json={"provider_id": "local", "model_id": "new-model"},
        )
        replaced = client.put(
            "/api/models/agent-1",
            headers={"Authorization": "model-manager"},
            json={"provider_id": "local", "model_id": "new-model"},
        )
        invalid = client.put(
            "/api/models/agent-1",
            headers={"Authorization": "model-manager"},
            json={"provider_id": "local", "model_id": " "},
        )
        missing_agent = client.put(
            "/api/models/unknown",
            headers={"Authorization": "model-manager"},
            json={"provider_id": "local", "model_id": "new-model"},
        )
        missing_provider = client.put(
            "/api/models/agent-1",
            headers={"Authorization": "model-manager"},
            json={"provider_id": "unknown", "model_id": "new-model"},
        )

    assert denied.status_code == 403
    assert replaced.status_code == 200
    assert replaced.json() == {
        "agent_id": "agent-1",
        "provider_id": "local",
        "model_id": "new-model",
    }
    assert invalid.status_code == 422
    assert missing_agent.status_code == 404
    assert missing_provider.status_code == 404
    assert service.replace_model.call_count == 3
    assert agents.get("agent-1").provider == "local"
    assert agents.get("agent-1").model == "new-model"
