from __future__ import annotations

import threading
import time

import pytest

from app.application.services.capability_approvals import CapabilityApprovalService
from app.application.services.capability_authorization import CapabilityAuthorizationService
from app.application.services.emergency_stop import EmergencyStopService
from app.integrations.scoped_desktop_automation import (
    DesktopActionRequest,
    DesktopActionUnavailable,
    DesktopAutomationPolicy,
    DesktopPolicyDenied,
    DesktopTargetUnavailable,
    DesktopWindowRequest,
    ScopedDesktopAutomation,
    ScopedDesktopError,
)


OWNER = "local-owner"
SESSION = "desktop-session"
PROCESS = "notepad.exe"
PERMISSIONS = frozenset({"desktop:act", "capability-approval:manage"})


def request():
    return DesktopActionRequest(
        "invoke_button", 4242, 161616, PROCESS, "Document - Notepad",
        "saveButton", "Save",
    )


class FakeBackend:
    def __init__(self):
        self.state = {
            "process_id": 4242,
            "window_handle": 161616,
            "process_name": PROCESS,
            "window_title": "Document - Notepad",
            "automation_id": "saveButton",
            "control_type": "Button",
            "control_name": "Save",
            "enabled": True,
            "visible": True,
            "rectangle": (100, 100, 180, 130),
        }
        self.invocations = 0
        self.block_invoke = False
        self.fail_invoke = False
        self.block_inspect = False
        self.invoke_started = threading.Event()
        self.inspect_started = threading.Event()
        self.release = threading.Event()

    def list_windows(self, process_name, *, limit):
        assert limit <= 50
        return [{"process_id": 4242, "window_handle": 161616,
                 "process_name": process_name, "window_title": "Document - Notepad"}]

    def list_buttons(self, window, *, timeout_milliseconds):
        assert timeout_milliseconds <= 10_000
        if (window.process_id, window.window_handle, window.process_name, window.window_title) != (
                4242, 161616, PROCESS, "Document - Notepad"):
            raise DesktopTargetUnavailable("The selected desktop window identity changed")
        return [{"automation_id": "saveButton", "control_name": "Save"}]

    def inspect(self, _request, *, timeout_milliseconds):
        assert timeout_milliseconds >= 250
        if self.block_inspect:
            self.inspect_started.set()
            self.release.wait(timeout=3)
        return dict(self.state)

    def invoke(self, _request, *, timeout_milliseconds):
        assert timeout_milliseconds >= 250
        self.invocations += 1
        self.invoke_started.set()
        if self.block_invoke:
            self.release.wait(timeout=3)
        if self.fail_invoke:
            raise RuntimeError("secret internal path must not be exposed")


def make_service(*, timeout=1000, max_actions=2, backend=None, stop=None, processes=None,actions=frozenset({'invoke_button'})):
    policy = DesktopAutomationPolicy(
        allowed_process_names=frozenset({PROCESS} if processes is None else processes),
        max_actions_per_session=max_actions,
        timeout_milliseconds=timeout,
        allowed_actions=actions,
    )
    authorization = CapabilityAuthorizationService()
    approvals = CapabilityApprovalService(authorization)
    backend = backend or FakeBackend()
    stop = stop or EmergencyStopService()
    service = ScopedDesktopAutomation(
        policy, approvals, emergency_stop=stop, backend=backend,
        authorization=authorization,
    )
    return service, approvals, backend, stop


def preview(service, action=None):
    return service.preview(
        action or request(), actor_id=OWNER, permissions=PERMISSIONS,
        session_grants=frozenset(), session_id=SESSION,
    )


def approved_action(service, approvals, action=None):
    action = action or request()
    record = service.request_approval(
        action, actor_id=OWNER, permissions=PERMISSIONS,
        session_grants=frozenset(), session_id=SESSION,
    )
    approvals.approve(
        record["approval_id"], approver_id=OWNER, permissions=PERMISSIONS,
        confirmed_digest=record["approval_digest"],
    )
    return action, record


def execute(service, action, approval_id):
    return service.execute(
        action, approval_id, actor_id=OWNER, permissions=PERMISSIONS,
        session_grants=frozenset(), session_id=SESSION,
    )


def test_desktop_policy_is_deny_by_default_and_process_names_are_exact():
    with pytest.raises(ValueError):
        DesktopAutomationPolicy(allowed_process_names=frozenset({"*"}))
    service, _approvals, _backend, _stop = make_service(processes=set())
    with pytest.raises(DesktopPolicyDenied):
        preview(service)

    service, _approvals, _backend, _stop = make_service(processes={"notepad.exe"})
    altered = DesktopActionRequest(
        "invoke_button", 4242, 161616, "calc.exe", "Document - Notepad",
        "saveButton", "Save",
    )
    with pytest.raises(DesktopPolicyDenied):
        preview(service, altered)


def test_preview_is_read_only_and_binds_the_exact_visible_control():
    service, _approvals, backend, _stop = make_service()
    result = preview(service)
    assert result.state == "preview_only"
    assert result.confirmation_required is True
    assert len(result.target_digest) == len(result.payload_digest) == 64
    assert backend.invocations == 0
    assert service.activity_snapshot()["state"] == "idle"

    backend.state["visible"] = False
    with pytest.raises(DesktopTargetUnavailable):
        preview(service)


def test_read_only_discovery_is_allowlisted_authorized_and_exact_window_scoped():
    service, _approvals, backend, _stop = make_service()
    windows = service.list_windows(PROCESS, actor_id=OWNER, permissions=PERMISSIONS,
                                   session_grants=frozenset(), session_id=SESSION)
    assert windows[0]["window_title"] == "Document - Notepad"
    selected = DesktopWindowRequest(**windows[0])
    buttons = service.list_buttons(selected, actor_id=OWNER, permissions=PERMISSIONS,
                                   session_grants=frozenset(), session_id=SESSION)
    assert buttons == [{"automation_id": "saveButton", "control_name": "Save"}]
    assert backend.invocations == 0

    with pytest.raises(DesktopPolicyDenied):
        service.list_windows("calc.exe", actor_id=OWNER, permissions=PERMISSIONS,
                             session_grants=frozenset(), session_id=SESSION)
    with pytest.raises(DesktopTargetUnavailable, match="identity"):
        service.list_buttons(DesktopWindowRequest(4242, 999, PROCESS, "Other"), actor_id=OWNER,
                             permissions=PERMISSIONS, session_grants=frozenset(), session_id=SESSION)
    assert backend.invocations == 0


def test_invoke_requires_exact_owner_approval_and_reports_unknown_outcome():
    service, approvals, backend, _stop = make_service()
    action, record = approved_action(service, approvals)
    assert backend.invocations == 0
    result = execute(service, action, record["approval_id"])
    assert result["status"] == "action_dispatched"
    assert result["remote_outcome"] == "unknown"
    trace = service.trace_service.get(result["trace_id"], actor_id=OWNER)
    assert trace.grant_id == record["approval_id"]
    assert trace.action_id == "desktop.invoke_button"
    assert trace.before_digest == record["target_digest"]
    assert trace.after_state == "unknown"
    assert backend.invocations == 1
    assert approvals.get(record["approval_id"]).status == "consumed"
    assert service.activity_snapshot()["state"] == "outcome_unknown"


def test_changed_window_or_control_state_blocks_dispatch():
    service, approvals, backend, _stop = make_service()
    action, record = approved_action(service, approvals)
    backend.state["control_name"] = "Delete"
    with pytest.raises(DesktopActionUnavailable):
        execute(service, action, record["approval_id"])
    assert backend.invocations == 0


def test_unapproved_and_stopped_actions_never_reach_backend():
    service, _approvals, backend, stop = make_service()
    action = request()
    record = service.request_approval(
        action, actor_id=OWNER, permissions=PERMISSIONS,
        session_grants=frozenset(), session_id=SESSION,
    )
    with pytest.raises(ScopedDesktopError, match="not currently owner-approved"):
        execute(service, action, record["approval_id"])
    stop.stop()
    with pytest.raises(ScopedDesktopError, match="emergency stop"):
        execute(service, action, record["approval_id"])
    assert backend.invocations == 0


def test_action_timeout_is_unknown_no_retry_and_blocks_overlapping_actions():
    backend = FakeBackend()
    backend.block_invoke = True
    service, approvals, _backend, _stop = make_service(
        timeout=250, backend=backend,
    )
    action, record = approved_action(service, approvals)
    result = execute(service, action, record["approval_id"])
    assert backend.invoke_started.is_set()
    assert result["status"] == "timed_out"
    assert result["remote_outcome"] == "unknown"
    assert result["retry"] == "forbidden"
    trace = service.trace_service.get(result["trace_id"], actor_id=OWNER)
    assert trace.action_result == "timed_out_unknown"
    assert trace.remote_outcome == "unknown"
    assert service.activity_snapshot()["active"] is True

    second_action, second_record = approved_action(service, approvals)
    with pytest.raises(ScopedDesktopError, match="already running"):
        execute(service, second_action, second_record["approval_id"])
    assert backend.invocations == 1
    backend.release.set()
    deadline = time.monotonic() + 2
    while service.activity_snapshot()["active"] and time.monotonic() < deadline:
        time.sleep(0.01)
    assert service.activity_snapshot()["active"] is False


def test_timeout_during_target_check_cancels_late_dispatch():
    backend = FakeBackend()
    service, approvals, _backend, _stop = make_service(
        timeout=250, backend=backend,
    )
    action, record = approved_action(service, approvals)
    backend.block_inspect = True
    with pytest.raises(DesktopActionUnavailable, match="timed out before action dispatch"):
        execute(service, action, record["approval_id"])
    assert backend.inspect_started.is_set()

    backend.release.set()
    deadline = time.monotonic() + 2
    while service.activity_snapshot()["active"] and time.monotonic() < deadline:
        time.sleep(0.01)
    assert backend.invocations == 0
    assert service.activity_snapshot()["state"] == "timed_out_before_dispatch"


def test_single_process_action_and_session_limits_are_enforced():
    service, approvals, backend, _stop = make_service(max_actions=1)
    action, record = approved_action(service, approvals)
    execute(service, action, record["approval_id"])

    second_action, second_record = approved_action(service, approvals)
    with pytest.raises(ScopedDesktopError, match="action limit"):
        execute(service, second_action, second_record["approval_id"])
    assert backend.invocations == 1


def test_backend_error_after_action_dispatch_is_unknown_and_redacted():
    backend = FakeBackend()
    backend.fail_invoke = True
    service, approvals, _backend, _stop = make_service(backend=backend)
    action, record = approved_action(service, approvals)

    result = execute(service, action, record["approval_id"])

    assert result["status"] == "action_failed"
    assert result["remote_outcome"] == "unknown"
    assert result["retry"] == "forbidden"
    assert "secret internal path" not in result["message"]
    assert backend.invocations == 1


def test_text_replacement_requires_exact_value_and_nonpassword_writable_target():
    from dataclasses import replace
    from hashlib import sha256
    backend=FakeBackend();backend.state.update(control_type='Edit',password=False,read_only=False,
        value_digest=sha256(b'original').hexdigest())
    service,approvals,_,_=make_service(backend=backend,actions=frozenset({'fill_text'}))
    action=replace(request(),action='fill_text',value='Reviewed Taglish text — kumusta')
    action,record=approved_action(service,approvals,action)
    with pytest.raises(ScopedDesktopError):execute(service,replace(action,value='Different text'),record['approval_id'])
    result=execute(service,action,record['approval_id'])
    assert result['status']=='action_dispatched' and backend.invocations==1
    backend.state['password']=True
    with pytest.raises(DesktopTargetUnavailable):preview(service,action)
    backend.state['password']=False;backend.state['read_only']=True
    with pytest.raises(DesktopTargetUnavailable):preview(service,action)
    with pytest.raises(ValueError):preview(service,replace(action,value='first\nsecond'))


def test_native_stop_reaches_desktop_worker_before_dispatch_and_other_window_cannot_use_approval():
    from threading import Event
    from app.resources.context import native_scope
    from app.application.services.native_runtime import NativeScope
    from dataclasses import replace
    scope=NativeScope(OWNER,'window-a',0,Event(),Event());token=native_scope.set(scope)
    service,approvals,backend,_=make_service()
    try:
        action,record=approved_action(service,approvals)
        other=native_scope.set(replace(scope,window_id='window-b'))
        try:
            with pytest.raises(ScopedDesktopError):execute(service,action,record['approval_id'])
        finally:native_scope.reset(other)
        original=backend.inspect
        def stop_during_inspection(*args,**kwargs):
            state=original(*args,**kwargs);scope.stop.set();return state
        backend.inspect=stop_during_inspection
        with pytest.raises(DesktopActionUnavailable):execute(service,action,record['approval_id'])
        assert backend.invocations==0
    finally:native_scope.reset(token)
