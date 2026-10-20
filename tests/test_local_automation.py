import pytest

from app.application.services.automation_traces import AutomationTraceService
from app.application.services.capability_approvals import CapabilityApprovalService
from app.application.services.capability_authorization import CapabilityAuthorizationService
from app.application.services.emergency_stop import EmergencyStopService
from app.integrations.local_automation import LocalAutomationRegistry


def registry():
    authorization = CapabilityAuthorizationService()
    return LocalAutomationRegistry(CapabilityApprovalService(authorization), authorization,
                                   EmergencyStopService(), AutomationTraceService())


def test_policy_cannot_change_during_an_in_flight_preview_or_discovery_lease():
    manager = registry()
    with manager.browser_operation():
        with pytest.raises(RuntimeError, match="while an action is active"):
            manager.set_origin("https://example.org", allowed=True)
    assert manager.set_origin("https://example.org", allowed=True)["allowed_origins"] == ["https://example.org"]

    with manager.desktop_operation():
        with pytest.raises(RuntimeError, match="while an action is active"):
            manager.set_process("notepad.exe", allowed=True)
    assert manager.set_process("notepad.exe", allowed=True)["allowed_process_names"] == ["notepad.exe"]
