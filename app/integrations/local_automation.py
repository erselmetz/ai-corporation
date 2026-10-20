"""Process-local owner policies for the already-reviewed automation services."""
from __future__ import annotations

import threading
from contextlib import contextmanager

from app.application.services.automation_traces import AutomationTraceService
from app.application.services.capability_approvals import CapabilityApprovalService
from app.application.services.capability_authorization import CapabilityAuthorizationService
from app.application.services.emergency_stop import EmergencyStopService
from app.integrations.scoped_browser_automation import (
    BrowserSitePolicy,
    ScopedBrowserAutomation,
)
from app.integrations.scoped_desktop_automation import (
    DesktopAutomationPolicy,
    ScopedDesktopAutomation,
)


class LocalAutomationRegistry:
    """Keep user-configured allowlists empty by default and only for this process."""

    MAX_ORIGINS = 16
    MAX_PROCESSES = 16

    def __init__(self, approvals: CapabilityApprovalService,
                 authorization: CapabilityAuthorizationService,
                 emergency_stop: EmergencyStopService,
                 traces: AutomationTraceService):
        self._approvals = approvals
        self._authorization = authorization
        self._stop = emergency_stop
        self._traces = traces
        self._origins: set[str] = set()
        self._processes: set[str] = set()
        self._browser: ScopedBrowserAutomation | None = None
        self._desktop: ScopedDesktopAutomation | None = None
        self._browser_policy: frozenset[str] | None = None
        self._desktop_policy: frozenset[str] | None = None
        self._browser_leases = 0
        self._desktop_leases = 0
        self._lock = threading.RLock()

    def snapshot(self) -> dict:
        with self._lock:
            browser = self._browser.activity_snapshot() if self._browser is not None else {"active": False}
            desktop = self._desktop.activity_snapshot() if self._desktop is not None else {"active": False}
            return {
                "browser": {"allowed_origins": sorted(self._origins), **browser},
                "desktop": {"allowed_process_names": sorted(self._processes), **desktop},
                "persistence": "process_only",
                "default_policy": "empty_allowlists",
                "browser_visible": True,
                "pyautogui": "not-used",
            }

    def set_origin(self, origin: str, *, allowed: bool) -> dict:
        # Reuse the automation policy's canonical public-HTTPS validator.
        BrowserSitePolicy(frozenset({origin}))
        with self._lock:
            self._ensure_idle()
            if allowed and origin not in self._origins and len(self._origins) >= self.MAX_ORIGINS:
                raise ValueError("The browser origin allowlist is full")
            if allowed:
                self._origins.add(origin)
            else:
                self._origins.discard(origin)
            self._browser = None
            self._browser_policy = None
            return self.snapshot()["browser"]

    def set_process(self, process_name: str, *, allowed: bool) -> dict:
        # Reuse the exact canonical Windows executable-name policy validator.
        DesktopAutomationPolicy(frozenset({process_name}))
        with self._lock:
            self._ensure_idle()
            if allowed and process_name not in self._processes and len(self._processes) >= self.MAX_PROCESSES:
                raise ValueError("The desktop process allowlist is full")
            if allowed:
                self._processes.add(process_name)
            else:
                self._processes.discard(process_name)
            self._desktop = None
            self._desktop_policy = None
            return self.snapshot()["desktop"]

    def browser(self) -> ScopedBrowserAutomation:
        with self._lock:
            policy = frozenset(self._origins)
            if self._browser is None or self._browser_policy != policy:
                self._browser = ScopedBrowserAutomation(
                    BrowserSitePolicy(policy), self._approvals,
                    authorization=self._authorization, emergency_stop=self._stop,
                    trace_service=self._traces,
                )
                self._browser_policy = policy
            return self._browser

    def desktop(self) -> ScopedDesktopAutomation:
        with self._lock:
            policy = frozenset(self._processes)
            if self._desktop is None or self._desktop_policy != policy:
                self._desktop = ScopedDesktopAutomation(
                    DesktopAutomationPolicy(policy), self._approvals,
                    authorization=self._authorization, emergency_stop=self._stop,
                    trace_service=self._traces,
                )
                self._desktop_policy = policy
            return self._desktop

    def traces(self) -> AutomationTraceService:
        return self._traces

    @contextmanager
    def browser_operation(self):
        with self._lock:
            service = self.browser()
            self._browser_leases += 1
        try:
            yield service
        finally:
            with self._lock:
                self._browser_leases -= 1

    @contextmanager
    def desktop_operation(self):
        with self._lock:
            service = self.desktop()
            self._desktop_leases += 1
        try:
            yield service
        finally:
            with self._lock:
                self._desktop_leases -= 1

    def _ensure_idle(self) -> None:
        if (self._browser_leases or self._desktop_leases
                or self._browser is not None and self._browser.activity_snapshot().get("active")
                or self._desktop is not None and self._desktop.activity_snapshot().get("active")):
            raise RuntimeError("Automation policy cannot change while an action is active")
