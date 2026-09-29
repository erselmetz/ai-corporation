from unittest.mock import MagicMock

from fastapi import Request
from fastapi.testclient import TestClient

from app.api import AuthenticatedPrincipal, create_app
from app.application import CorporationApplicationService
from app.corporation import Corporation
from app.node import Node
from app.orchestrator import Orchestrator
from app.providers import OllamaProvider


class StatusTestAuthenticationBackend:
    def authenticate(self, request: Request) -> AuthenticatedPrincipal | None:
        token = request.headers.get("Authorization")
        if token == "Bearer status-reader":
            return AuthenticatedPrincipal(
                identity="status-reader",
                permissions=frozenset({"corporation:read"}),
            )
        if token == "Bearer other-reader":
            return AuthenticatedPrincipal(
                identity="other-reader",
                permissions=frozenset({"task:read"}),
            )
        return None


def make_application_service() -> tuple[
    CorporationApplicationService,
    MagicMock,
    Corporation,
    Node,
]:
    orchestrator = MagicMock(spec=Orchestrator)
    corporation = Corporation(id="corp_local", name="ERSELMETZ Local Corp")
    node = Node(
        id="node_local",
        corporation_id=corporation.id,
        name="Local Node 1",
    )
    return (
        CorporationApplicationService(orchestrator, corporation, node),
        orchestrator,
        corporation,
        node,
    )


def test_status_requires_authentication_and_corporation_read_permission():
    service, _, _, _ = make_application_service()
    application = create_app(service, StatusTestAuthenticationBackend())

    with TestClient(application) as client:
        unauthenticated = client.get("/api/status")
        forbidden = client.get(
            "/api/status",
            headers={"Authorization": "Bearer other-reader"},
        )

    assert unauthenticated.status_code == 401
    assert unauthenticated.json() == {"detail": "Authentication required"}
    assert forbidden.status_code == 403
    assert forbidden.json() == {"detail": "Permission denied"}


def test_authorized_status_returns_stable_json_through_application_service():
    service, orchestrator, corporation, node = make_application_service()
    status_operation = MagicMock(wraps=service.get_corporation_status)
    service.get_corporation_status = status_operation
    application = create_app(service, StatusTestAuthenticationBackend())

    with TestClient(application) as client:
        response = client.get(
            "/api/status",
            headers={"Authorization": "Bearer status-reader"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "corporation": {
            "id": "corp_local",
            "name": "ERSELMETZ Local Corp",
        },
        "node": {
            "id": "node_local",
            "name": "Local Node 1",
        },
    }
    assert status_operation.call_count == 1
    assert orchestrator.method_calls == []
    assert (corporation.id, corporation.name) == (
        "corp_local",
        "ERSELMETZ Local Corp",
    )
    assert (node.id, node.name, node.corporation_id) == (
        "node_local",
        "Local Node 1",
        "corp_local",
    )


def test_default_runtime_status_uses_configured_identity_without_ollama(
    monkeypatch,
):
    generate = MagicMock(side_effect=AssertionError("Status must not call Ollama"))
    monkeypatch.setattr(OllamaProvider, "generate", generate)
    application = create_app(
        authentication_backend=StatusTestAuthenticationBackend(),
    )

    with TestClient(application) as client:
        response = client.get(
            "/api/status",
            headers={"Authorization": "Bearer status-reader"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "corporation": {
            "id": "corp_local",
            "name": "ERSELMETZ Local Corp",
        },
        "node": {
            "id": "node_local",
            "name": "Local Node 1",
        },
    }
    generate.assert_not_called()


def test_health_remains_public_and_separate_from_corporation_status():
    service, _, _, _ = make_application_service()
    application = create_app(service, StatusTestAuthenticationBackend())

    with TestClient(application) as client:
        health = client.get("/health")
        root = client.get("/")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert root.status_code == 200
    assert root.json() == {
        "application": "ERSELMETZ AI CORPORATION API",
    }
