from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import Request
from fastapi.testclient import TestClient

from app.api import AuthenticatedPrincipal, create_app
from app.application.services.hardware_profile import (
    HardwareProfile,
    Observation,
)
from app.application.services.corporation import CorporationApplicationService
from app.orchestrator import Orchestrator


class SystemAuthentication:
    def authenticate(self, request: Request):
        permission = request.headers.get("Authorization")
        if permission == "system-reader":
            return AuthenticatedPrincipal("owner", frozenset({"system:read"}))
        if permission == "task-reader":
            return AuthenticatedPrincipal("reader", frozenset({"task:read"}))
        return None


def test_hardware_profile_route_requires_existing_system_read_permission_and_redacts_paths():
    timestamp = datetime(2026, 10, 18, tzinfo=timezone.utc).isoformat()
    observation = Observation("observed", {"name": "Example CPU"}, None, "fake WMI source", timestamp)
    profile = HardwareProfile(timestamp, observation, observation, observation, observation, {
        "ollama_model_class": "small (up to about 3B parameters, Q4)",
        "cpu_warning": "GPU use is unknown.", "basis": "Fake evidence.",
        "fit_claim": "No fit guarantee.",
    })
    app = create_app(CorporationApplicationService(MagicMock(spec=Orchestrator)), SystemAuthentication())

    with patch("app.api.system_monitoring.collect_hardware_profile", return_value=profile):
        with TestClient(app) as client:
            unauthenticated = client.get("/api/system/hardware-profile")
            denied = client.get("/api/system/hardware-profile", headers={"Authorization": "task-reader"})
            allowed = client.get("/api/system/hardware-profile", headers={"Authorization": "system-reader"})

    assert unauthenticated.status_code == 401
    assert denied.status_code == 403
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["cpu"]["source"] == "fake WMI source"
    assert body["gpu"]["observed_at"] == timestamp
    assert body["privacy"] == "Read-only local observation; not stored or uploaded."
    assert "ollama_model_class" in body["recommendation"]
    assert "absolute_path" not in body
