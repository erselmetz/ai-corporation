"""Owner-only, exact-action access to the existing scoped automation services."""
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

from app.application.services.automation_traces import AutomationTraceService
from app.application.services.capability_approvals import CapabilityApprovalService
from app.application.services.capability_authorization import CapabilityAuthorizationService
from app.application.services.emergency_stop import EmergencyStopService
from app.integrations.local_automation import LocalAutomationRegistry
from app.integrations.scoped_browser_automation import (
    BrowserActionRequest,
    ScopedBrowserError,
)
from app.integrations.scoped_desktop_automation import (
    DesktopActionRequest,
    DesktopWindowRequest,
    ScopedDesktopError,
)
from .security import AuthenticatedPrincipal, require_permission


router = APIRouter(prefix="/api/local/automation", tags=["local-automation"])


class OriginPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: StrictStr = Field(min_length=9, max_length=512)
    allowed: StrictBool


class ProcessPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    process_name: StrictStr = Field(min_length=5, max_length=132)
    allowed: StrictBool


class BrowserActionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["click", "fill_text"]
    url: StrictStr = Field(min_length=9, max_length=2048)
    role: Literal["button", "link", "textbox"]
    name: StrictStr = Field(min_length=1, max_length=512)
    value: StrictStr | None = Field(default=None, max_length=2048, repr=False)

    def domain(self) -> BrowserActionRequest:
        return BrowserActionRequest(self.action, self.url, self.role, self.name, self.value)


class BrowserExecuteBody(BrowserActionBody):
    approval_id: StrictStr = Field(min_length=32, max_length=32, pattern="^[0-9a-f]{32}$")


class DesktopWindowBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    process_name: StrictStr = Field(min_length=5, max_length=132)


class DesktopButtonsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    process_id: StrictInt = Field(gt=0, le=2**31 - 1)
    window_handle: StrictInt = Field(gt=0, le=2**63 - 1)
    process_name: StrictStr = Field(min_length=5, max_length=132)
    window_title: StrictStr = Field(min_length=1, max_length=256)

    def domain(self) -> DesktopWindowRequest:
        return DesktopWindowRequest(self.process_id, self.window_handle,
                                    self.process_name, self.window_title)


class DesktopActionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal['invoke_button','fill_text']='invoke_button'
    value: StrictStr | None=Field(default=None,min_length=1,max_length=2048,repr=False)
    process_id: StrictInt = Field(gt=0, le=2**31 - 1)
    window_handle: StrictInt = Field(gt=0, le=2**63 - 1)
    process_name: StrictStr = Field(min_length=5, max_length=132)
    window_title: StrictStr = Field(min_length=1, max_length=256)
    automation_id: StrictStr = Field(min_length=1, max_length=256)
    control_name: StrictStr = Field(min_length=1, max_length=160)

    def domain(self) -> DesktopActionRequest:
        return DesktopActionRequest(self.action, self.process_id, self.window_handle,
                                    self.process_name, self.window_title,
                                    self.automation_id, self.control_name,self.value)


class DesktopExecuteBody(DesktopActionBody):
    approval_id: StrictStr = Field(min_length=32, max_length=32, pattern="^[0-9a-f]{32}$")


def _registry(request: Request) -> LocalAutomationRegistry:
    with request.app.state.local_automation_registry_lock:
        existing = getattr(request.app.state, "local_automation_registry", None)
        if isinstance(existing, LocalAutomationRegistry):
            return existing
        approvals = getattr(request.app.state, "capability_approval_service", None)
        authorization = getattr(request.app.state, "capability_authorization_service", None)
        stop = getattr(request.app.state, "emergency_stop_service", None)
        if not (isinstance(approvals, CapabilityApprovalService)
                and isinstance(authorization, CapabilityAuthorizationService)
                and isinstance(stop, EmergencyStopService)):
            raise HTTPException(503, "Local automation services are not configured")
        traces = getattr(request.app.state, "automation_trace_service", None)
        if not isinstance(traces, AutomationTraceService):
            traces = AutomationTraceService()
            request.app.state.automation_trace_service = traces
        existing = LocalAutomationRegistry(approvals, authorization, stop, traces)
        request.app.state.local_automation_registry = existing
        return existing


def _require_session(principal: AuthenticatedPrincipal) -> None:
    if principal.session_id is None:
        raise HTTPException(403, "An authenticated owner session is required for computer automation")


def _csrf(request: Request) -> None:
    backend = getattr(request.app.state, "authentication_backend", None)
    require_csrf = getattr(backend, "require_csrf", None)
    if not callable(require_csrf):
        raise HTTPException(403, "Owner request verification is unavailable")
    require_csrf(request)


def _owner_context(principal: AuthenticatedPrincipal):
    _require_session(principal)
    return principal.identity, principal.permissions, principal.session_grants, principal.session_id


@router.get("")
def automation_status(principal: AuthenticatedPrincipal = Depends(require_permission("browser:act")),
                      registry: LocalAutomationRegistry = Depends(_registry)):
    _require_session(principal)
    snapshot = registry.snapshot()
    try:
        import importlib.util
        snapshot["desktop"]["backend_available"] = (
            importlib.util.find_spec("pywinauto") is not None if __import__("os").name == "nt" else False
        )
    except (ImportError, ValueError):
        snapshot["desktop"]["backend_available"] = False
    return snapshot


@router.put("/browser/origin")
def set_browser_origin(body: OriginPolicyUpdate, request: Request,
                       principal: AuthenticatedPrincipal = Depends(require_permission("browser:act")),
                       registry: LocalAutomationRegistry = Depends(_registry)):
    _owner_context(principal)
    _csrf(request)
    try:
        return registry.set_origin(body.origin, allowed=body.allowed)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except RuntimeError as error:
        raise HTTPException(409, str(error)) from None


@router.put("/desktop/process")
def set_desktop_process(body: ProcessPolicyUpdate, request: Request,
                        principal: AuthenticatedPrincipal = Depends(require_permission("desktop:act")),
                        registry: LocalAutomationRegistry = Depends(_registry)):
    _owner_context(principal)
    _csrf(request)
    try:
        return registry.set_process(body.process_name, allowed=body.allowed)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except RuntimeError as error:
        raise HTTPException(409, str(error)) from None


@router.post("/browser/preview")
def preview_browser_action(body: BrowserActionBody, principal: AuthenticatedPrincipal = Depends(
        require_permission("browser:act")), registry: LocalAutomationRegistry = Depends(_registry)):
    actor, permissions, grants, session = _owner_context(principal)
    try:
        with registry.browser_operation() as browser:
            result = browser.preview(body.domain(), actor_id=actor, permissions=permissions,
                                     session_grants=grants, session_id=session)
        return asdict(result)
    except (ValueError, ScopedBrowserError, PermissionError) as error:
        raise HTTPException(409, str(error)) from None


@router.post("/browser/request-approval")
def request_browser_approval(body: BrowserActionBody, request: Request,
                             principal: AuthenticatedPrincipal = Depends(require_permission("browser:act")),
                             registry: LocalAutomationRegistry = Depends(_registry)):
    _owner_context(principal)
    _csrf(request)
    actor, permissions, grants, session = _owner_context(principal)
    try:
        with registry.browser_operation() as browser:
            approval = browser.request_approval(body.domain(), actor_id=actor, permissions=permissions,
                                                session_grants=grants, session_id=session)
        return {"approval": approval}
    except (ValueError, ScopedBrowserError, PermissionError) as error:
        raise HTTPException(409, str(error)) from None


@router.post("/browser/execute")
def execute_browser_action(body: BrowserExecuteBody, request: Request,
                           principal: AuthenticatedPrincipal = Depends(require_permission("browser:act")),
                           registry: LocalAutomationRegistry = Depends(_registry)):
    _owner_context(principal)
    _csrf(request)
    actor, permissions, grants, session = _owner_context(principal)
    try:
        with registry.browser_operation() as browser:
            result = browser.execute(body.domain(), body.approval_id, actor_id=actor,
                                     permissions=permissions, session_grants=grants, session_id=session)
        return result
    except (ValueError, ScopedBrowserError, PermissionError) as error:
        raise HTTPException(409, str(error)) from None


@router.get("/traces")
def list_automation_traces(principal: AuthenticatedPrincipal = Depends(require_permission("activity:read")),
                           registry: LocalAutomationRegistry = Depends(_registry)):
    _require_session(principal)
    return {"items": [asdict(trace) for trace in registry.traces().list_for_actor(
        actor_id=principal.identity, limit=50)]}


def _desktop_list_ready(registry: LocalAutomationRegistry):
    service = registry.desktop()
    try:
        import importlib.util
        available = __import__("os").name == "nt" and importlib.util.find_spec("pywinauto") is not None
    except (ImportError, ValueError):
        available = False
    if not available:
        raise HTTPException(503, "Windows UI Automation is unavailable on this device")
    return service


@router.post("/desktop/windows")
def list_desktop_windows(body: DesktopWindowBody,
                         principal: AuthenticatedPrincipal = Depends(require_permission("desktop:act")),
                         registry: LocalAutomationRegistry = Depends(_registry)):
    actor, permissions, grants, session = _owner_context(principal)
    try:
        _desktop_list_ready(registry)
        with registry.desktop_operation() as desktop:
            return {"items": desktop.list_windows(body.process_name, actor_id=actor, permissions=permissions,
                                                   session_grants=grants, session_id=session)}
    except (ValueError, ScopedDesktopError, PermissionError) as error:
        raise HTTPException(409, str(error)) from None


@router.post("/desktop/buttons")
def list_desktop_buttons(body: DesktopButtonsBody,
                         principal: AuthenticatedPrincipal = Depends(require_permission("desktop:act")),
                         registry: LocalAutomationRegistry = Depends(_registry)):
    actor, permissions, grants, session = _owner_context(principal)
    try:
        _desktop_list_ready(registry)
        with registry.desktop_operation() as desktop:
            return {"items": desktop.list_buttons(body.domain(), actor_id=actor, permissions=permissions,
                                                   session_grants=grants, session_id=session)}
    except (ValueError, ScopedDesktopError, PermissionError) as error:
        raise HTTPException(409, str(error)) from None


@router.post("/desktop/preview")
def preview_desktop_action(body: DesktopActionBody,
                           principal: AuthenticatedPrincipal = Depends(require_permission("desktop:act")),
                           registry: LocalAutomationRegistry = Depends(_registry)):
    actor, permissions, grants, session = _owner_context(principal)
    try:
        with registry.desktop_operation() as desktop:
            return asdict(desktop.preview(body.domain(), actor_id=actor, permissions=permissions,
                                          session_grants=grants, session_id=session))
    except (ValueError, ScopedDesktopError, PermissionError) as error:
        raise HTTPException(409, str(error)) from None


@router.post('/desktop/controls')
def list_desktop_controls(body:DesktopButtonsBody,
                          principal:AuthenticatedPrincipal=Depends(require_permission('desktop:act')),
                          registry:LocalAutomationRegistry=Depends(_registry)):
    actor,permissions,grants,session=_owner_context(principal)
    try:
        _desktop_list_ready(registry)
        with registry.desktop_operation() as desktop:
            return {'items':desktop.list_controls(body.domain(),actor_id=actor,permissions=permissions,
                                                  session_grants=grants,session_id=session)}
    except (ValueError,ScopedDesktopError,PermissionError) as error:
        raise HTTPException(409,str(error)) from None


@router.post("/desktop/request-approval")
def request_desktop_approval(body: DesktopActionBody, request: Request,
                             principal: AuthenticatedPrincipal = Depends(require_permission("desktop:act")),
                             registry: LocalAutomationRegistry = Depends(_registry)):
    _owner_context(principal)
    _csrf(request)
    actor, permissions, grants, session = _owner_context(principal)
    try:
        with registry.desktop_operation() as desktop:
            approval = desktop.request_approval(body.domain(), actor_id=actor, permissions=permissions,
                                                session_grants=grants, session_id=session)
            return {"approval": approval}
    except (ValueError, ScopedDesktopError, PermissionError) as error:
        raise HTTPException(409, str(error)) from None


@router.post("/desktop/execute")
def execute_desktop_action(body: DesktopExecuteBody, request: Request,
                           principal: AuthenticatedPrincipal = Depends(require_permission("desktop:act")),
                           registry: LocalAutomationRegistry = Depends(_registry)):
    _owner_context(principal)
    _csrf(request)
    actor, permissions, grants, session = _owner_context(principal)
    try:
        with registry.desktop_operation() as desktop:
            return desktop.execute(body.domain(), body.approval_id, actor_id=actor,
                                   permissions=permissions, session_grants=grants, session_id=session)
    except (ValueError, ScopedDesktopError, PermissionError) as error:
        raise HTTPException(409, str(error)) from None
