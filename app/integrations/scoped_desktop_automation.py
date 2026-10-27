"""Owner-approved, bounded Windows UI Automation actions over semantic controls."""
from __future__ import annotations

from dataclasses import dataclass
from contextvars import copy_context
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import threading
from functools import wraps
from typing import Literal, Protocol

from app.application.services.automation_traces import AutomationTraceService
from app.application.services.capability_approvals import (
    POLICY_VERSION,
    CapabilityApprovalError,
    CapabilityApprovalService,
)
from app.application.services.capability_authorization import (
    CapabilityAuthorizationService,
    DEFAULT_CAPABILITY_AUTHORIZATION,
)
from app.application.services.emergency_stop import EmergencyStopService


CAPABILITY_ID = "desktop:act"
MAX_ALLOWED_PROCESSES = 16
MAX_ACTIONS_PER_SESSION = 10
MAX_ACTION_TIMEOUT_MILLISECONDS = 10_000
_PROCESS_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}\.exe$", re.IGNORECASE)


class ScopedDesktopError(RuntimeError):
    """Base class for bounded desktop action failures."""


class DesktopPolicyDenied(ScopedDesktopError):
    """The process, target, or action is outside explicit policy."""


class DesktopTargetUnavailable(ScopedDesktopError):
    """The exact native target is missing, stale, or ambiguous."""


class DesktopActionUnavailable(ScopedDesktopError):
    """The bounded desktop action could not be verified or dispatched."""


@dataclass(frozen=True, slots=True)
class DesktopAutomationPolicy:
    """Exact process-name/action policy; empty process allowlist denies all."""

    allowed_process_names: frozenset[str] = frozenset()
    allowed_actions: frozenset[str] = frozenset({"invoke_button"})
    max_actions_per_session: int = MAX_ACTIONS_PER_SESSION
    timeout_milliseconds: int = MAX_ACTION_TIMEOUT_MILLISECONDS

    def __post_init__(self) -> None:
        if (not isinstance(self.allowed_process_names, frozenset)
                or len(self.allowed_process_names) > MAX_ALLOWED_PROCESSES
                or any(not isinstance(name, str) or not _PROCESS_NAME.fullmatch(name)
                       or name != name.lower() for name in self.allowed_process_names)):
            raise ValueError("Desktop process policy must be a frozen list of canonical executable names")
        if (not isinstance(self.allowed_actions, frozenset)
                or not self.allowed_actions.issubset({"invoke_button","fill_text"})):
            raise ValueError("Desktop action policy contains an unsupported operation")
        if (type(self.max_actions_per_session) is not int
                or not 1 <= self.max_actions_per_session <= MAX_ACTIONS_PER_SESSION):
            raise ValueError("Desktop actions per session must be between 1 and 10")
        if (type(self.timeout_milliseconds) is not int
                or not 250 <= self.timeout_milliseconds <= MAX_ACTION_TIMEOUT_MILLISECONDS):
            raise ValueError("Desktop timeout must be between 250 and 10000 milliseconds")


@dataclass(frozen=True, slots=True)
class DesktopActionRequest:
    action: Literal["invoke_button","fill_text"]
    process_id: int
    window_handle: int
    process_name: str
    window_title: str
    automation_id: str
    control_name: str
    value: str | None = None


@dataclass(frozen=True, slots=True)
class DesktopWindowRequest:
    process_id: int
    window_handle: int
    process_name: str
    window_title: str


@dataclass(frozen=True, slots=True)
class DesktopActionPreview:
    action: str
    process_name: str
    window_title: str
    target_label: str
    target_digest: str
    payload_digest: str
    confirmation_required: bool = True
    state: str = "preview_only"


class DesktopAutomationBackend(Protocol):
    def inspect(self, request: DesktopActionRequest, *, timeout_milliseconds: int) -> dict: ...
    def invoke(self, request: DesktopActionRequest, *, timeout_milliseconds: int) -> None: ...
    def list_windows(self, process_name: str, *, limit: int) -> list[dict]: ...
    def list_buttons(self, request: DesktopWindowRequest, *, timeout_milliseconds: int) -> list[dict]: ...


def _com_call(method):
    @wraps(method)
    def invoke(*args,**kwargs):
        if os.name!='nt':return method(*args,**kwargs)
        import ctypes
        ole=ctypes.WinDLL('ole32');initialize=ole.CoInitializeEx
        initialize.argtypes=[ctypes.c_void_p,ctypes.c_ulong];initialize.restype=ctypes.c_long
        result=initialize(None,0)
        if result not in (0,1,-2147417850):raise DesktopActionUnavailable('Windows control inspection could not initialize')
        try:return method(*args,**kwargs)
        finally:
            if result in (0,1):ole.CoUninitialize()
    return invoke


class WindowsUIAutomationBackend:
    """Resolve one direct child Button using UI Automation; never sends coordinates/keys."""

    @_com_call
    def inspect(self, request: DesktopActionRequest, *, timeout_milliseconds: int) -> dict:
        _app, window, button = self._resolve(request, timeout_milliseconds)
        info = button.element_info
        rectangle=button.rectangle()
        state = {
            "process_id": window.element_info.process_id,
            "window_handle": window.element_info.handle,
            "process_name": _process_basename(request.process_id),
            "window_title": window.window_text(),
            "automation_id": info.automation_id or "",
            "control_type": info.control_type,
            "control_name": info.name or "",
            "enabled": bool(button.is_enabled()),
            "visible": bool(button.is_visible()),
            "rectangle": (rectangle.left,rectangle.top,rectangle.right,rectangle.bottom),
        }
        if request.action=='fill_text':
            state.update(password=bool(info.element.CurrentIsPassword),
                         read_only=bool(button.iface_value.CurrentIsReadOnly),
                         value_digest=sha256(str(button.iface_value.CurrentValue).encode('utf-8')).hexdigest())
        return state

    @_com_call
    def invoke(self, request: DesktopActionRequest, *, timeout_milliseconds: int) -> None:
        _app, _window, button = self._resolve(request, timeout_milliseconds)
        if not button.is_enabled() or not button.is_visible():
            raise DesktopTargetUnavailable("The approved desktop button is no longer available")
        if request.action=='fill_text':
            if button.element_info.element.CurrentIsPassword or button.iface_value.CurrentIsReadOnly:
                raise DesktopTargetUnavailable('The approved text field is no longer editable')
            button.iface_value.SetValue(request.value)
        else:button.invoke()

    def list_windows(self, process_name: str, *, limit: int = 50) -> list[dict]:
        """Read-only list of visible top-level windows for one allowlisted process."""
        if os.name != "nt":
            raise DesktopActionUnavailable("Windows UI Automation is available only on Windows")
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        enum_windows = user32.EnumWindows
        enum_windows.argtypes = (wintypes.WNDENUMPROC, wintypes.LPARAM)
        enum_windows.restype = wintypes.BOOL
        is_visible = user32.IsWindowVisible
        is_visible.argtypes = (wintypes.HWND,)
        is_visible.restype = wintypes.BOOL
        get_title = user32.GetWindowTextW
        get_title.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        get_title.restype = ctypes.c_int
        get_process = user32.GetWindowThreadProcessId
        get_process.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        get_process.restype = wintypes.DWORD
        found: list[dict] = []

        def visit(handle, _parameter):
            if len(found) >= limit or not is_visible(handle):
                return True
            process_id = wintypes.DWORD()
            get_process(handle, ctypes.byref(process_id))
            try:
                if _process_basename(process_id.value) != process_name:
                    return True
                buffer = ctypes.create_unicode_buffer(512)
                length = get_title(handle, buffer, len(buffer))
                title = buffer.value[:min(length, 256)].strip()
                if title:
                    found.append({"process_id": process_id.value, "window_handle": int(handle),
                                  "process_name": process_name, "window_title": title})
            except DesktopActionUnavailable:
                return True
            return True

        callback = wintypes.WNDENUMPROC(visit)
        enum_windows(callback, 0)
        return found

    def list_buttons(self, request: DesktopWindowRequest, *, timeout_milliseconds: int) -> list[dict]:
        return self.list_controls(request,timeout_milliseconds=timeout_milliseconds,buttons_only=True)

    @_com_call
    def list_controls(self, request: DesktopWindowRequest, *, timeout_milliseconds: int,buttons_only=False) -> list[dict]:
        if os.name != "nt":
            raise DesktopActionUnavailable("Windows UI Automation is available only on Windows")
        try:
            from pywinauto import Application
            app = Application(backend="uia", allow_magic_lookup=False).connect(
                process=request.process_id, timeout=timeout_milliseconds / 1000,
            )
            window = app.window(handle=request.window_handle)
            window.wait("exists visible enabled", timeout=timeout_milliseconds / 1000)
            if (window.element_info.process_id != request.process_id
                    or window.element_info.handle != request.window_handle
                    or window.window_text() != request.window_title
                    or _process_basename(request.process_id) != request.process_name):
                raise DesktopTargetUnavailable("The selected desktop window identity changed")
            buttons = []
            for child in window.children():
                info = child.element_info
                if (info.control_type in ({'Button'} if buttons_only else {'Button','Edit'}) and child.is_visible() and child.is_enabled()
                        and info.automation_id and info.name and len(buttons) < 100):
                    if info.control_type=='Edit':
                        try:
                            if info.element.CurrentIsPassword or child.iface_value.CurrentIsReadOnly:continue
                        except Exception:continue
                    record={"automation_id":str(info.automation_id)[:256],"control_name":str(info.name)[:160]}
                    if not buttons_only:record['action']='invoke_button' if info.control_type=='Button' else 'fill_text'
                    buttons.append(record)
            return buttons
        except (DesktopTargetUnavailable, DesktopActionUnavailable):
            raise
        except ImportError:
            raise DesktopActionUnavailable("Optional Windows UI Automation support is not installed") from None
        except Exception:
            raise DesktopActionUnavailable("Windows UI Automation could not inspect the selected window") from None

    @staticmethod
    def _resolve(request: DesktopActionRequest, timeout_milliseconds: int):
        if os.name != "nt":
            raise DesktopActionUnavailable("Windows UI Automation is available only on Windows")
        try:
            from pywinauto import Application
        except ImportError:
            raise DesktopActionUnavailable(
                "Optional Windows UI Automation support is not installed"
            ) from None
        timeout_seconds = timeout_milliseconds / 1000
        try:
            app = Application(backend="uia", allow_magic_lookup=False).connect(
                process=request.process_id, timeout=timeout_seconds,
            )
            window = app.window(handle=request.window_handle)
            window.wait("exists visible enabled", timeout=timeout_seconds)
            info = window.element_info
            if (info.process_id != request.process_id
                    or info.handle != request.window_handle
                    or window.window_text() != request.window_title
                    or _process_basename(request.process_id) != request.process_name):
                raise DesktopTargetUnavailable("The approved desktop window identity changed")
            matches = []
            for child in window.children():
                child_info = child.element_info
                if (child_info.control_type == ('Edit' if request.action=='fill_text' else 'Button')
                        and child_info.automation_id == request.automation_id
                        and child_info.name == request.control_name):
                    matches.append(child)
            if len(matches) != 1:
                raise DesktopTargetUnavailable(
                    "The exact direct-child UI Automation button is missing or ambiguous"
                )
            return app, window, matches[0]
        except (DesktopTargetUnavailable, DesktopActionUnavailable):
            raise
        except Exception:
            raise DesktopActionUnavailable(
                "Windows UI Automation could not inspect the approved target"
            ) from None


class ScopedDesktopAutomation:
    """One-use-approved UIA button invocation with a bounded caller wait and no replay."""

    def __init__(
        self,
        policy: DesktopAutomationPolicy,
        approvals: CapabilityApprovalService,
        *,
        emergency_stop: EmergencyStopService,
        backend: DesktopAutomationBackend | None = None,
        authorization: CapabilityAuthorizationService = DEFAULT_CAPABILITY_AUTHORIZATION,
        trace_service: AutomationTraceService | None = None,
    ):
        if not isinstance(policy, DesktopAutomationPolicy):
            raise TypeError("A DesktopAutomationPolicy is required")
        if not isinstance(approvals, CapabilityApprovalService):
            raise TypeError("A CapabilityApprovalService is required")
        if not isinstance(emergency_stop, EmergencyStopService):
            raise TypeError("An EmergencyStopService is required")
        if not isinstance(authorization, CapabilityAuthorizationService):
            raise TypeError("A CapabilityAuthorizationService is required")
        if trace_service is not None and not isinstance(trace_service, AutomationTraceService):
            raise TypeError("An AutomationTraceService is required")
        self._policy = policy
        self._approvals = approvals
        self._stop = emergency_stop
        self._authorization = authorization
        self._backend = backend or WindowsUIAutomationBackend()
        self._trace_service = trace_service or AutomationTraceService()
        self._lock = threading.RLock()
        self._actions: dict[str, int] = {}
        self._active_sessions: set[str] = set()
        self._activity = {"state": "idle", "started_at": None,
                          "finished_at": None, "result": None}
        self._activity_generation = 0

    @property
    def trace_service(self) -> AutomationTraceService:
        return self._trace_service

    def activity_snapshot(self) -> dict:
        with self._lock:
            return {**self._activity, "active": bool(self._active_sessions),
                    "emergency_stopped": self._stop.stopped,
                    "persistence": "process_only"}

    def preview(
        self, request: DesktopActionRequest, *, actor_id: str,
        permissions: frozenset[str], session_grants: frozenset[tuple[str, str, str]],
        session_id: str,
    ) -> DesktopActionPreview:
        _validate_session_id(session_id)
        self._validate_request(request)
        self._authorize(actor_id, permissions, session_grants)
        self._require_running()
        try:
            state = self._backend.inspect(
                request, timeout_milliseconds=self._policy.timeout_milliseconds,
            )
            self._validate_target_state(request, state)
        except (DesktopTargetUnavailable, DesktopActionUnavailable):
            raise
        except Exception:
            raise DesktopActionUnavailable("Desktop target inspection failed") from None
        target_digest = _digest(state)
        return DesktopActionPreview(
            action=request.action, process_name=request.process_name,
            window_title=request.window_title,
            target_label=f"{request.control_name} ({request.automation_id})",
            target_digest=target_digest,
            payload_digest=_request_digest(request),
        )

    def list_windows(self, process_name: str, *, actor_id: str,
                     permissions: frozenset[str],
                     session_grants: frozenset[tuple[str, str, str]],
                     session_id: str) -> list[dict]:
        _validate_session_id(session_id)
        if (not isinstance(process_name, str) or process_name != process_name.lower()
                or not _PROCESS_NAME.fullmatch(process_name)
                or process_name not in self._policy.allowed_process_names):
            raise DesktopPolicyDenied("The desktop process is not explicitly allowlisted")
        self._authorize(actor_id, permissions, session_grants)
        self._require_running()
        list_windows = getattr(self._backend, "list_windows", None)
        if not callable(list_windows):
            raise DesktopActionUnavailable("Window discovery is unavailable in this UI Automation provider")
        return list_windows(process_name, limit=50)

    def list_buttons(self, request: DesktopWindowRequest, *, actor_id: str,
                     permissions: frozenset[str],
                     session_grants: frozenset[tuple[str, str, str]],
                     session_id: str) -> list[dict]:
        _validate_session_id(session_id)
        self._validate_window_request(request)
        self._authorize(actor_id, permissions, session_grants)
        self._require_running()
        list_buttons = getattr(self._backend, "list_buttons", None)
        if not callable(list_buttons):
            raise DesktopActionUnavailable("Button discovery is unavailable in this UI Automation provider")
        return list_buttons(request, timeout_milliseconds=self._policy.timeout_milliseconds)

    def list_controls(self,request,*,actor_id,permissions,session_grants,session_id):
        _validate_session_id(session_id);self._validate_window_request(request)
        self._authorize(actor_id,permissions,session_grants);self._require_running()
        method=getattr(self._backend,'list_controls',None)
        if not callable(method):raise DesktopActionUnavailable('Control discovery is unavailable')
        return method(request,timeout_milliseconds=self._policy.timeout_milliseconds)

    def _validate_window_request(self, request: DesktopWindowRequest) -> None:
        if not isinstance(request, DesktopWindowRequest):
            raise ValueError("A selected desktop window is required")
        if (type(request.process_id) is not int or request.process_id <= 0
                or type(request.window_handle) is not int or request.window_handle <= 0
                or request.process_name not in self._policy.allowed_process_names
                or not _PROCESS_NAME.fullmatch(request.process_name)
                or not isinstance(request.window_title, str)
                or not request.window_title.strip() or len(request.window_title) > 256):
            raise ValueError("The selected desktop window identity is invalid")

    def request_approval(
        self, request: DesktopActionRequest, *, actor_id: str,
        permissions: frozenset[str], session_grants: frozenset[tuple[str, str, str]],
        session_id: str,
    ) -> dict:
        preview = self.preview(
            request, actor_id=actor_id, permissions=permissions,
            session_grants=session_grants, session_id=session_id,
        )
        approval = self._approvals.request(
            actor_id=actor_id, permissions=permissions, session_grants=session_grants,
            capability_id=CAPABILITY_ID, action_id="desktop."+request.action,
            action_summary=_action_summary(request),
            target_ref=f"desktop:{request.process_name}:{request.process_id}:{request.window_handle}",
            scope_type="principal", scope_id=actor_id,
            payload_digest=preview.payload_digest, target_digest=preview.target_digest,
            irreversible=True,
        )
        return self._approvals.snapshot(approval)

    def execute(
        self, request: DesktopActionRequest, approval_id: str, *, actor_id: str,
        permissions: frozenset[str], session_grants: frozenset[tuple[str, str, str]],
        session_id: str,
    ) -> dict:
        _validate_session_id(session_id)
        self._validate_request(request)
        self._authorize(actor_id, permissions, session_grants)
        self._require_running()
        payload_digest = _request_digest(request)
        target_ref = f"desktop:{request.process_name}:{request.process_id}:{request.window_handle}"
        approval = self._approvals.get(approval_id)
        if (self._approvals.snapshot(approval)["status"] != "approved"
                or approval.actor_id != actor_id or approval.capability_id != CAPABILITY_ID
                or approval.action_id != "desktop."+request.action
                or approval.target_ref != target_ref or approval.scope_type != "principal"
                or approval.scope_id != actor_id or approval.payload_digest != payload_digest
                or approval.policy_version != POLICY_VERSION):
            raise ScopedDesktopError("The exact desktop action is not currently owner-approved")
        trace_started_at = datetime.now(timezone.utc)

        def record_trace(action_result: str, remote_outcome: str):
            return self._trace_service.record_action(
                actor_id=actor_id, capability_id=CAPABILITY_ID,
                grant_id=approval_id, policy_version=POLICY_VERSION,
                target_ref=target_ref, action_id="desktop."+request.action,
                before_digest=approval.target_digest, action_result=action_result,
                remote_outcome=remote_outcome, started_at=trace_started_at,
            )

        with self._lock:
            if len(self._actions) >= 64 and session_id not in self._actions:
                raise ScopedDesktopError("Desktop session capacity is full; restart the local app")
            if session_id in self._active_sessions:
                raise ScopedDesktopError("A desktop action is already running for this session")
            if self._actions.get(session_id, 0) >= self._policy.max_actions_per_session:
                raise ScopedDesktopError("Desktop action limit reached for this session")
            if self._active_sessions:
                raise ScopedDesktopError("Another desktop action is already active in this process")
            self._active_sessions.add(session_id)
            self._activity_generation += 1
            generation = self._activity_generation
            self._activity = {"state": "action_running", "started_at": _now(),
                              "finished_at": None, "result": "pending"}

        outcome: dict = {}
        completed = threading.Event()
        attempted = threading.Event()
        cancel_before_dispatch = threading.Event()
        dispatch_lock = threading.Lock()
        from app.resources.context import application_service,native_scope
        application=application_service.get();scope=native_scope.get()
        runtime=application.native_runtime() if application is not None and scope is not None else None
        operation=None
        if runtime is not None:
            try:operation=runtime.begin(scope,'desktop','Approved desktop '+request.action);runtime.mark(operation,'running')
            except Exception:
                with self._lock:self._active_sessions.discard(session_id)
                raise

        def guarded_action() -> dict:
            def inspect_target() -> str:
                if cancel_before_dispatch.is_set():
                    raise DesktopActionUnavailable("Desktop request expired before action dispatch")
                self._require_running()
                state = self._backend.inspect(
                    request, timeout_milliseconds=self._policy.timeout_milliseconds,
                )
                self._validate_target_state(request, state)
                return _digest(state)

            def invoke() -> dict:
                self._require_running()
                with dispatch_lock:
                    if cancel_before_dispatch.is_set():
                        raise DesktopActionUnavailable("Desktop request expired before action dispatch")
                    with self._lock:
                        self._actions[session_id] = self._actions.get(session_id, 0) + 1
                    attempted.set()
                self._backend.invoke(
                    request, timeout_milliseconds=self._policy.timeout_milliseconds,
                )
                return {"status": "action_dispatched", "remote_outcome": "unknown",
                        "action": request.action, "process_name": request.process_name,
                        "window_title": request.window_title, "dispatched_at": _now()}

            return self._approvals.execute(
                approval_id, actor_id=actor_id, permissions=permissions,
                session_grants=session_grants, capability_id=CAPABILITY_ID,
                action_id="desktop."+request.action,
                action_summary=_action_summary(request),
                target_ref=target_ref, scope_type="principal", scope_id=actor_id,
                payload_digest=payload_digest, current_policy_version=POLICY_VERSION,
                read_current_target_digest=inspect_target, operation=invoke,
            )

        def run_guarded_action() -> None:
            try:
                outcome["result"] = guarded_action()
            except CapabilityApprovalError as error:
                outcome["error"] = (
                    "The desktop target changed after approval; preview and approve again"
                    if "target state has changed" in str(error)
                    else "The owner approval is no longer usable"
                )
                outcome["error_type"] = "approval"
            except (DesktopTargetUnavailable, DesktopActionUnavailable, PermissionError) as error:
                outcome["error"] = (
                    "The desktop action may have been dispatched; its result is unknown"
                    if attempted.is_set() else str(error)
                )
                outcome["error_type"] = "unknown" if attempted.is_set() else "safe"
            except Exception:
                outcome["error"] = "Windows UI Automation failed; the remote outcome is unknown"
                outcome["error_type"] = "unknown" if attempted.is_set() else "safe"
            finally:
                completed.set()
                if runtime is not None:runtime.finish(operation)
                with self._lock:
                    self._active_sessions.discard(session_id)
                    if generation == self._activity_generation:
                        result = outcome.get("result")
                        timed_out_before_dispatch = (
                            cancel_before_dispatch.is_set() and not attempted.is_set()
                        )
                        self._activity = {
                            "state": ("timed_out_before_dispatch" if timed_out_before_dispatch
                                      else "outcome_unknown"
                                      if (outcome.get("error_type") == "unknown"
                                          or isinstance(result, dict)
                                          and result.get("remote_outcome") == "unknown")
                                      else "idle"),
                            "started_at": self._activity.get("started_at"),
                            "finished_at": _now(),
                            "result": ("not_dispatched" if timed_out_before_dispatch
                                       else "unknown" if outcome.get("error_type") == "unknown"
                                       else result.get("status") if isinstance(result, dict)
                                       else outcome.get("error_type", "failure")),
                        }

        context=copy_context()
        worker = threading.Thread(
            target=lambda:context.run(run_guarded_action), name="desktop-ui-automation", daemon=True,
        )
        worker.start()
        worker.join(self._policy.timeout_milliseconds / 1000)
        if not completed.is_set():
            with dispatch_lock:
                if not attempted.is_set():
                    cancel_before_dispatch.set()
            if attempted.is_set():
                self._set_activity_for_generation(generation, "outcome_unknown", "unknown")
                trace = record_trace("timed_out_unknown", "unknown")
                return {"status": "timed_out", "remote_outcome": "unknown",
                        "action": request.action, "retry": "forbidden",
                        "trace_id": trace.trace_id,
                        "message": "The desktop action may have run; do not retry automatically."}
            self._set_activity_for_generation(generation, "timed_out_before_dispatch", "not_dispatched")
            record_trace("failed_before_dispatch", "not_dispatched")
            raise DesktopActionUnavailable("Desktop inspection timed out before action dispatch")
        if "error" in outcome:
            if outcome.get("error_type") == "approval":
                record_trace("failed_before_dispatch", "not_dispatched")
                raise ScopedDesktopError(outcome["error"])
            if outcome.get("error_type") == "unknown":
                self._set_activity_for_generation(generation, "outcome_unknown", "unknown")
                trace = record_trace("failed_unknown", "unknown")
                return {"status": "action_failed", "remote_outcome": "unknown",
                        "action": request.action, "retry": "forbidden",
                        "trace_id": trace.trace_id,
                        "message": outcome["error"]}
            record_trace("failed_before_dispatch", "not_dispatched")
            raise DesktopActionUnavailable(outcome["error"])
        result = outcome["result"]
        trace = record_trace("dispatched", "unknown")
        result["trace_id"] = trace.trace_id
        return result

    def _validate_request(self, request: DesktopActionRequest) -> None:
        if not isinstance(request, DesktopActionRequest):
            raise ValueError("A structured desktop action is required")
        if request.action not in self._policy.allowed_actions:
            raise DesktopPolicyDenied("The desktop action is not allowlisted")
        if request.action=='fill_text':
            if (not isinstance(request.value,str) or not 1<=len(request.value)<=2048
                    or any(ord(char)<32 or ord(char)==127 for char in request.value)):
                raise ValueError('Desktop text must be one nonempty line of at most 2048 characters')
        elif request.value is not None:raise ValueError('A button invocation cannot contain typed text')
        if (type(request.process_id) is not int or request.process_id <= 0
                or type(request.window_handle) is not int or request.window_handle <= 0):
            raise ValueError("A specific process and visible window are required")
        if (not isinstance(request.process_name, str)
                or request.process_name != request.process_name.lower()
                or not _PROCESS_NAME.fullmatch(request.process_name)
                or request.process_name not in self._policy.allowed_process_names):
            raise DesktopPolicyDenied("The desktop process is not explicitly allowlisted")
        for value, max_length in ((request.window_title, 256),
                                  (request.automation_id, 256),
                                  (request.control_name, 160)):
            if (not isinstance(value, str) or not value.strip() or len(value) > max_length
                    or any(ord(char) < 32 for char in value)):
                raise ValueError("The exact desktop target identity is invalid")

    def _validate_target_state(self, request: DesktopActionRequest, state: dict) -> None:
        if not isinstance(state, dict):
            raise DesktopTargetUnavailable("The desktop target could not be inspected")
        expected = {
            "process_id": request.process_id,
            "window_handle": request.window_handle,
            "process_name": request.process_name,
            "window_title": request.window_title,
            "automation_id": request.automation_id,
            "control_type": 'Edit' if request.action=='fill_text' else 'Button',
            "control_name": request.control_name,
            "enabled": True,
            "visible": True,
        }
        if any(state.get(key) != value for key, value in expected.items()):
            raise DesktopTargetUnavailable("The exact visible desktop button is unavailable")
        if request.action=='fill_text' and (state.get('password') is not False or state.get('read_only') is not False
                or not isinstance(state.get('value_digest'),str) or not re.fullmatch('[0-9a-f]{64}',state['value_digest'])):
            raise DesktopTargetUnavailable('Only an inspected non-password, writable text field can be edited')

    def _authorize(self, actor_id, permissions, session_grants) -> None:
        self._authorization.require(
            identity=actor_id, permissions=permissions, session_grants=session_grants,
            capability_id=CAPABILITY_ID, scope_type="principal", scope_id=actor_id,
        )

    def _require_running(self) -> None:
        from app.resources.context import check_native_stop
        from app.application.services.native_runtime import NativeRuntimeStopped
        try:check_native_stop()
        except NativeRuntimeStopped:raise DesktopActionUnavailable('This native window was stopped; the desktop action was not dispatched') from None
        if self._stop.stopped:
            raise ScopedDesktopError("Desktop actions are blocked while emergency stop is active")

    def _set_activity_for_generation(self, generation: int, state: str, result: str) -> None:
        with self._lock:
            if generation == self._activity_generation:
                self._activity = {"state": state,
                                  "started_at": self._activity.get("started_at"),
                                  "finished_at": _now(), "result": result}


def _process_basename(process_id: int) -> str:
    if os.name != "nt":
        raise DesktopActionUnavailable("Windows process inspection is available only on Windows")
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_process.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    query_image = kernel32.QueryFullProcessImageNameW
    query_image.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                            ctypes.POINTER(wintypes.DWORD))
    query_image.restype = wintypes.BOOL
    handle = open_process(0x1000, False, process_id)
    if not handle:
        raise DesktopActionUnavailable("The selected desktop process is unavailable")
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buffer))
        if not query_image(handle, 0, buffer, ctypes.byref(length)):
            raise DesktopActionUnavailable("The selected desktop process identity is unavailable")
        return Path(buffer.value).name.lower()
    finally:
        close_handle(handle)


def _request_digest(request: DesktopActionRequest) -> str:
    from app.resources.context import native_scope
    window=native_scope.get()
    payload={
        "action": request.action, "process_id": request.process_id,
        "window_handle": request.window_handle, "process_name": request.process_name,
        "window_title": request.window_title, "automation_id": request.automation_id,
        "control_name": request.control_name,
    }
    if request.value is not None:payload['value']=request.value
    if window is not None:payload['native_window']={'owner':window.owner,'id':window.window_id,'generation':window.generation}
    return _digest(payload)


def _action_summary(request):
    return (f'Replace text in {request.control_name[:100]}' if request.action=='fill_text'
            else f'Invoke desktop button {request.control_name[:100]}')


def _digest(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                   default=list).encode("utf-8")
    return sha256(encoded).hexdigest()


def _validate_session_id(session_id: str) -> None:
    if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 128:
        raise ValueError("An authenticated owner session is required")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
