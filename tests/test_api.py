from importlib import import_module
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from fastapi import APIRouter, Depends, Request

from app.api import (
    AuthenticatedPrincipal,
    create_app,
    require_authenticated_principal,
    require_permission,
)
from app.application import CorporationApplicationService
from app.orchestrator import Orchestrator


class DeterministicTestAuthenticationBackend:
    def authenticate(self, request: Request) -> AuthenticatedPrincipal | None:
        authorization = request.headers.get("Authorization")
        if authorization == "Bearer test-only-token":
            return AuthenticatedPrincipal(
                identity="test-user",
                permissions=frozenset({"task:read"}),
            )
        return None


def add_protected_test_route(application):
    router = APIRouter()

    @router.get("/protected")
    def protected(
        principal: AuthenticatedPrincipal = Depends(
            require_permission("task:read")
        ),
    ):
        return {"identity": principal.identity}

    @router.get("/authenticated")
    def authenticated(
        principal: AuthenticatedPrincipal = Depends(
            require_authenticated_principal
        ),
    ):
        return {"identity": principal.identity}

    application.include_router(router)


def test_api_root_and_health_return_json_without_runtime_calls():
    service = CorporationApplicationService(MagicMock(spec=Orchestrator))
    application = create_app(service)

    with TestClient(application) as client:
        root = client.get("/")
        health = client.get("/health")

        assert root.status_code == 200
        assert root.json() == {
            "application": "ERSELMETZ AI CORPORATION API",
        }
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        assert application.state.application_service is service
        service._orchestrator.create_task.assert_not_called()
        service._orchestrator.execute_task.assert_not_called()


def test_protected_route_rejects_requests_without_valid_authentication():
    service = CorporationApplicationService(MagicMock(spec=Orchestrator))
    application = create_app(service, DeterministicTestAuthenticationBackend())
    add_protected_test_route(application)

    with TestClient(application) as client:
        assert client.get("/authenticated").status_code == 401
        assert client.get(
            "/authenticated",
            headers={"Authorization": "Bearer invalid-token"},
        ).status_code == 401
        assert client.get("/protected").status_code == 401


def test_authenticated_principal_and_permission_are_enforced_separately():
    service = CorporationApplicationService(MagicMock(spec=Orchestrator))
    application = create_app(service, DeterministicTestAuthenticationBackend())
    add_protected_test_route(application)

    with TestClient(application) as client:
        headers = {"Authorization": "Bearer test-only-token"}
        authenticated = client.get("/authenticated", headers=headers)
        authorized = client.get("/protected", headers=headers)

        assert authenticated.status_code == 200
        assert authenticated.json() == {"identity": "test-user"}
        assert authorized.status_code == 200
        assert authorized.json() == {"identity": "test-user"}


def test_authenticated_principal_without_permission_is_forbidden():
    class NoPermissionBackend:
        def authenticate(self, _request: Request) -> AuthenticatedPrincipal:
            return AuthenticatedPrincipal(
                identity="reader",
                permissions=frozenset(),
            )

    application = create_app(
        CorporationApplicationService(MagicMock(spec=Orchestrator)),
        NoPermissionBackend(),
    )
    add_protected_test_route(application)

    with TestClient(application) as client:
        response = client.get("/protected")

    assert response.status_code == 403
    assert response.json() == {"detail": "Permission denied"}


def test_api_default_lifespan_uses_shared_runtime_factory(monkeypatch):
    api_module = import_module("app.api.app")
    service = CorporationApplicationService(MagicMock(spec=Orchestrator))
    runtime = MagicMock()
    runtime.application_service = service
    factory = MagicMock(return_value=runtime)
    monkeypatch.setattr(api_module, "create_corporation_runtime", factory)

    with TestClient(create_app()) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.app.state.application_service is service

    factory.assert_called_once_with()


def test_api_default_runtime_starts_without_ollama_network_access():
    with TestClient(create_app()) as client:
        assert client.get("/").json() == {
            "application": "ERSELMETZ AI CORPORATION API",
        }
        service = client.app.state.application_service

        assert isinstance(service, CorporationApplicationService)
        assert service._orchestrator.providers.exists("ollama")
