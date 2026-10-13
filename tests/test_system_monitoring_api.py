from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi import Request
from fastapi.testclient import TestClient

from app.api import AuthenticatedPrincipal, create_app
from app.application import CorporationApplicationService
from app.application.services.system_monitoring import (
    CapacityObservation,
    CapacityScope,
    SystemMonitoringReport,
)
from app.orchestrator import Orchestrator
from app.orchestrator.task import TaskStatus
from app.providers.availability import AvailabilityState


class SystemAuthentication:
    def authenticate(self, request: Request):
        permission = request.headers.get("Authorization")
        if permission == "system-reader":
            return AuthenticatedPrincipal("owner", frozenset({"system:read"}))
        if permission == "task-reader":
            return AuthenticatedPrincipal("reader", frozenset({"task:read"}))
        return None


def test_system_snapshot_is_protected_and_reports_software_capacity_truthfully():
    service = CorporationApplicationService(MagicMock(spec=Orchestrator))
    service.monitor_system = MagicMock(return_value=SystemMonitoringReport(
        datetime(2026, 10, 14, tzinfo=timezone.utc),
        ((TaskStatus.PENDING, 2),), ("local-provider",), 0, AvailabilityState.UNKNOWN,
        (CapacityObservation(CapacityScope.GLOBAL, 4, 1, 3),), (),
    ))
    app = create_app(service, SystemAuthentication())

    with TestClient(app) as client:
        unauthenticated = client.get("/api/system/monitor")
        denied = client.get("/api/system/monitor", headers={"Authorization": "task-reader"})
        allowed = client.get("/api/system/monitor", headers={"Authorization": "system-reader"})

    assert unauthenticated.status_code == 401
    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["provider_availability"] == "unknown"
    assert allowed.json()["observed_at"] == "2026-10-14T00:00:00+00:00"
    assert allowed.json()["resource_capacities"] == [{
        "scope": "global", "limit": 4, "allocated": 1, "remaining": 3,
        "provider_id": None, "model_id": None,
    }]
    service.monitor_system.assert_called_once_with()
