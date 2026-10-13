"""Owner-approved, exact-origin browser actions with ephemeral Playwright contexts."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import ipaddress
import json
import re
import threading
from typing import Literal
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import Error as PlaywrightError, Route, sync_playwright

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


CAPABILITY_ID = "browser:act"
MAX_POLICY_ORIGINS = 16
MAX_ACTIONS_PER_SESSION = 10
MAX_TIMEOUT_MILLISECONDS = 10_000
MAX_TARGET_TEXT_CHARACTERS = 12_000
_SENSITIVE_LABEL = re.compile(
    r"password|credential|secret|token|api[ _-]?key|e-?mail|credit[ _-]?card|"
    r"security[ _-]?code|one[ _-]?time|\botp\b|\b2fa\b|\busername\b|"
    r"cc[-_ ]?(number|exp|csc)|account[ _-]?number|routing[ _-]?number",
    re.IGNORECASE,
)
_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class ScopedBrowserError(RuntimeError):
    """Base class for bounded browser automation failures."""


class BrowserPolicyDenied(ScopedBrowserError):
    """The requested origin or action is outside explicit policy."""


class BrowserTargetUnavailable(ScopedBrowserError):
    """The reviewed accessible target is missing or ambiguous."""


class BrowserActionStale(ScopedBrowserError):
    """The page or target changed after the owner reviewed it."""


class BrowserActionUnavailable(ScopedBrowserError):
    """The isolated browser could not complete its bounded action."""


@dataclass(frozen=True, slots=True)
class BrowserSitePolicy:
    """Exact, constructor-supplied HTTPS origins and role-based actions."""

    allowed_origins: frozenset[str] = frozenset()
    allowed_actions: frozenset[str] = frozenset({"click", "fill_text"})
    max_actions_per_session: int = MAX_ACTIONS_PER_SESSION
    timeout_milliseconds: int = MAX_TIMEOUT_MILLISECONDS

    def __post_init__(self) -> None:
        if (not isinstance(self.allowed_origins, frozenset)
                or len(self.allowed_origins) > MAX_POLICY_ORIGINS):
            raise ValueError("Browser origins must be a frozen allowlist of at most 16 entries")
        if any(_normalize_origin(origin) != origin for origin in self.allowed_origins):
            raise ValueError("Browser origins must be canonical exact HTTPS origins")
        if (not isinstance(self.allowed_actions, frozenset)
                or not self.allowed_actions.issubset({"click", "fill_text"})):
            raise ValueError("Browser action policy contains an unsupported operation")
        if (type(self.max_actions_per_session) is not int
                or not 1 <= self.max_actions_per_session <= MAX_ACTIONS_PER_SESSION):
            raise ValueError("Browser actions per session must be between 1 and 10")
        if (type(self.timeout_milliseconds) is not int
                or not 250 <= self.timeout_milliseconds <= MAX_TIMEOUT_MILLISECONDS):
            raise ValueError("Browser timeout must be between 250 and 10000 milliseconds")


@dataclass(frozen=True, slots=True)
class BrowserActionRequest:
    action: Literal["click", "fill_text"]
    url: str
    role: Literal["button", "link", "textbox"]
    name: str
    value: str | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class BrowserActionPreview:
    action: str
    url: str
    target_label: str
    target_digest: str
    payload_digest: str
    confirmation_required: bool = True
    state: str = "preview_only"


class ScopedBrowserAutomation:
    """Run one reviewed click or text fill in a throwaway, exact-origin context.

    No origins or actions are available unless the caller supplies an explicit
    BrowserSitePolicy. Every action requires the existing exact-digest owner
    approval service, and the assigned model/tool receives no browser API.
    """

    def __init__(
        self,
        policy: BrowserSitePolicy,
        approvals: CapabilityApprovalService,
        *,
        authorization: CapabilityAuthorizationService = DEFAULT_CAPABILITY_AUTHORIZATION,
        emergency_stop: EmergencyStopService,
        browser_launcher=None,
        trace_service: AutomationTraceService | None = None,
    ) -> None:
        if not isinstance(policy, BrowserSitePolicy):
            raise TypeError("policy must be an explicit BrowserSitePolicy")
        if not isinstance(approvals, CapabilityApprovalService):
            raise TypeError("approvals must use the existing capability approval service")
        if not isinstance(authorization, CapabilityAuthorizationService):
            raise TypeError("authorization must use the configured capability policy")
        if not isinstance(emergency_stop, EmergencyStopService):
            raise TypeError("emergency_stop must use the configured process stop service")
        if trace_service is not None and not isinstance(trace_service, AutomationTraceService):
            raise TypeError("trace_service must use the bounded automation trace service")
        self._policy = policy
        self._approvals = approvals
        self._authorization = authorization
        self._emergency_stop = emergency_stop
        self._browser_launcher = browser_launcher or self._launch_chromium
        self._trace_service = trace_service or AutomationTraceService()
        self._lock = threading.RLock()
        self._actions: dict[str, int] = {}
        self._in_flight: set[str] = set()

    @property
    def trace_service(self) -> AutomationTraceService:
        return self._trace_service

    def preview(
        self,
        request: BrowserActionRequest,
        *,
        actor_id: str,
        permissions: frozenset[str],
        session_grants: frozenset[tuple[str, str, str]],
        session_id: str,
    ) -> BrowserActionPreview:
        _validate_session_id(session_id)
        origin, canonical_url = self._validate(request)
        self._authorize(actor_id, permissions, session_grants, origin)
        self._require_running()
        with self._open_page(origin, canonical_url) as (page, _action_network_enabled):
            target = self._read_target(page, request)
            target_digest = self._target_digest(page, request, target)
        return BrowserActionPreview(
            action=request.action,
            url=canonical_url,
            target_label=f"{request.role}: {request.name}",
            target_digest=target_digest,
            payload_digest=_digest({
                "action": request.action, "url": canonical_url,
                "role": request.role, "name": request.name,
                "value": request.value,
            }),
        )

    def request_approval(
        self,
        request: BrowserActionRequest,
        *,
        actor_id: str,
        permissions: frozenset[str],
        session_grants: frozenset[tuple[str, str, str]],
        session_id: str,
    ) -> dict:
        _validate_session_id(session_id)
        preview = self.preview(
            request, actor_id=actor_id, permissions=permissions,
            session_grants=session_grants, session_id=session_id,
        )
        origin, _ = self._validate(request)
        approval = self._approvals.request(
            actor_id=actor_id,
            permissions=permissions,
            session_grants=session_grants,
            capability_id=CAPABILITY_ID,
            action_id=f"browser.{request.action}",
            action_summary=f"{request.action} {request.role} named {request.name[:120]}",
            target_ref=f"browser:{urlsplit(origin).hostname}",
            scope_type="principal", scope_id=actor_id,
            payload_digest=preview.payload_digest,
            target_digest=preview.target_digest,
            irreversible=True,
        )
        return self._approvals.snapshot(approval)

    def execute(
        self,
        request: BrowserActionRequest,
        approval_id: str,
        *,
        actor_id: str,
        permissions: frozenset[str],
        session_grants: frozenset[tuple[str, str, str]],
        session_id: str,
    ) -> dict:
        _validate_session_id(session_id)
        origin, canonical_url = self._validate(request)
        self._authorize(actor_id, permissions, session_grants, origin)
        self._require_running()
        payload_digest = _digest({
            "action": request.action, "url": canonical_url,
            "role": request.role, "name": request.name,
            "value": request.value,
        })
        action_id = f"browser.{request.action}"
        action_summary = f"{request.action} {request.role} named {request.name[:120]}"
        target_ref = f"browser:{urlsplit(origin).hostname}"
        approval = self._approvals.get(approval_id)
        if (self._approvals.snapshot(approval)["status"] != "approved"
                or approval.actor_id != actor_id
                or approval.capability_id != CAPABILITY_ID
                or approval.action_id != action_id
                or approval.action_summary != action_summary
                or approval.target_ref != target_ref
                or approval.scope_type != "principal"
                or approval.scope_id != actor_id
                or approval.payload_digest != payload_digest
                or approval.policy_version != POLICY_VERSION):
            raise ScopedBrowserError("The exact browser action is not currently owner-approved")

        with self._lock:
            if len(self._actions) >= 64 and session_id not in self._actions:
                raise ScopedBrowserError("Browser session capacity is full; restart the local app")
            if session_id in self._in_flight:
                raise ScopedBrowserError("A browser action is already running for this session")
            if self._actions.get(session_id, 0) >= self._policy.max_actions_per_session:
                raise ScopedBrowserError("Browser action limit reached for this session")
            self._in_flight.add(session_id)
        action_attempted = False
        trace_started_at = datetime.now(timezone.utc)
        trace_eligible = False
        trace_succeeded = False
        result = None
        try:
            with self._open_page(origin, canonical_url) as (page, action_network_enabled):
                def current_target_digest() -> str:
                    self._require_running()
                    target = self._read_target(page, request)
                    return self._target_digest(page, request, target)

                def perform_action() -> dict:
                    nonlocal action_attempted
                    self._require_running()
                    target = self._read_target(page, request)
                    if self._target_digest(page, request, target) != self._approvals.get(approval_id).target_digest:
                        raise BrowserActionStale("The browser target changed before action dispatch")
                    with self._lock:
                        if self._actions.get(session_id, 0) >= self._policy.max_actions_per_session:
                            raise ScopedBrowserError("Browser action limit reached for this session")
                        self._actions[session_id] = self._actions.get(session_id, 0) + 1
                    action_attempted = True
                    action_network_enabled["value"] = True
                    try:
                        if request.action == "click":
                            target.click(timeout=self._policy.timeout_milliseconds)
                        else:
                            target.fill(request.value or "", timeout=self._policy.timeout_milliseconds)
                    finally:
                        action_network_enabled["value"] = False
                    return {
                        "status": "action_dispatched",
                        "remote_outcome": "unknown",
                        "action": request.action,
                        "target_origin": origin,
                        "dispatched_at": datetime.now(timezone.utc).isoformat(),
                    }

                trace_eligible = True
                result = self._approvals.execute(
                    approval_id,
                    actor_id=actor_id,
                    permissions=permissions,
                    session_grants=session_grants,
                    capability_id=CAPABILITY_ID,
                    action_id=action_id,
                    action_summary=action_summary,
                    target_ref=target_ref,
                    scope_type="principal", scope_id=actor_id,
                    payload_digest=payload_digest,
                    current_policy_version=POLICY_VERSION,
                    read_current_target_digest=current_target_digest,
                    operation=perform_action,
                )
                trace_succeeded = True
                return result
        except (ScopedBrowserError, PermissionError):
            raise
        except CapabilityApprovalError as error:
            if "target state has changed" in str(error):
                raise BrowserActionStale("The page changed after approval; preview and approve again") from None
            raise ScopedBrowserError("The owner approval is no longer usable") from None
        except PlaywrightError:
            message = (
                "The approved browser action may have been dispatched; its remote outcome is unknown. Do not retry automatically."
                if action_attempted else
                "The scoped browser could not reach or inspect the approved target. No action was dispatched."
            )
            raise BrowserActionUnavailable(message) from None
        finally:
            if trace_eligible:
                trace = self._trace_service.record_action(
                    actor_id=actor_id, capability_id=CAPABILITY_ID,
                    grant_id=approval_id, policy_version=POLICY_VERSION,
                    target_ref=target_ref, action_id=action_id,
                    before_digest=approval.target_digest,
                    action_result=("failed_before_dispatch" if not action_attempted
                                   else "dispatched" if trace_succeeded
                                   else "failed_unknown"),
                    remote_outcome=("not_dispatched" if not action_attempted else "unknown"),
                    started_at=trace_started_at,
                )
                if isinstance(result, dict):
                    result["trace_id"] = trace.trace_id
            with self._lock:
                self._in_flight.discard(session_id)

    def _validate(self, request: BrowserActionRequest) -> tuple[str, str]:
        if not isinstance(request, BrowserActionRequest):
            raise ValueError("A structured browser action is required")
        if request.action not in self._policy.allowed_actions:
            raise BrowserPolicyDenied("The browser operation is not allowlisted")
        if request.action == "click" and request.role not in {"button", "link"}:
            raise BrowserPolicyDenied("Click targets must be accessible buttons or links")
        if request.action == "fill_text" and request.role != "textbox":
            raise BrowserPolicyDenied("Text entry targets must be accessible textboxes")
        if (not isinstance(request.name, str) or not request.name.strip()
                or len(request.name) > 160 or any(ord(char) < 32 for char in request.name)):
            raise ValueError("Browser target name is invalid")
        if request.action == "fill_text":
            if (not isinstance(request.value, str) or len(request.value.encode("utf-8")) > 4096
                    or any(ord(char) < 32 and char not in "\n\t" for char in request.value)):
                raise ValueError("Browser text value is invalid or exceeds limits")
            if _SENSITIVE_LABEL.search(request.name):
                raise BrowserPolicyDenied("Credential and payment fields are not supported")
        elif request.value is not None:
            raise ValueError("Click actions cannot include text values")
        origin, canonical_url = _normalize_url(request.url)
        if origin not in self._policy.allowed_origins:
            raise BrowserPolicyDenied("The browser origin is not explicitly allowed")
        return origin, canonical_url

    def _authorize(self, actor_id, permissions, session_grants, origin) -> None:
        self._authorization.require(
            identity=actor_id, permissions=permissions,
            session_grants=session_grants, capability_id=CAPABILITY_ID,
            scope_type="principal", scope_id=actor_id,
        )
        if not origin:
            raise BrowserPolicyDenied("The browser origin is invalid")

    def _require_running(self) -> None:
        if self._emergency_stop.stopped:
            raise ScopedBrowserError("Browser actions are blocked while emergency stop is active")

    @contextmanager
    def _open_page(self, origin: str, url: str):
        yielded_page = False
        try:
            with self._browser_launcher() as playwright:
                browser = playwright.chromium.launch(
                    headless=True, chromium_sandbox=True,
                    timeout=self._policy.timeout_milliseconds,
                    args=["--no-proxy-server"],
                )
                try:
                    context = browser.new_context(
                        accept_downloads=False, java_script_enabled=True,
                        permissions=[], service_workers="block",
                    )
                    context.set_default_timeout(self._policy.timeout_milliseconds)
                    context.set_default_navigation_timeout(self._policy.timeout_milliseconds)
                    context.route_web_socket(
                        "**/*", lambda websocket: websocket.close(
                            code=1008, reason="WebSocket access is disabled for this action"
                        ),
                    )
                    try:
                        action_network_enabled = {"value": False}

                        def route_request(route: Route) -> None:
                            requested_origin = _origin_from_url(route.request.url)
                            if requested_origin != origin:
                                route.abort()
                                return
                            if (route.request.method.upper() not in {"GET", "HEAD"}
                                    and not action_network_enabled["value"]):
                                route.abort()
                                return
                            route.continue_()

                        context.route("**/*", route_request)
                        page = context.new_page()
                        page.goto(url, wait_until="domcontentloaded",
                                  timeout=self._policy.timeout_milliseconds)
                        if _origin_from_url(page.url) != origin:
                            raise BrowserPolicyDenied("The browser navigated outside the approved origin")
                        yielded_page = True
                        yield page, action_network_enabled
                    finally:
                        context.close()
                finally:
                    browser.close()
        except (BrowserPolicyDenied, BrowserTargetUnavailable):
            raise
        except PlaywrightError:
            if yielded_page:
                raise
            raise BrowserActionUnavailable("The scoped browser request could not be completed") from None

    def _read_target(self, page, request: BrowserActionRequest):
        target = page.get_by_role(request.role, name=request.name, exact=True)
        if target.count() != 1:
            raise BrowserTargetUnavailable("The named accessible target is missing or ambiguous")
        if not target.is_visible(timeout=self._policy.timeout_milliseconds):
            raise BrowserTargetUnavailable("The named browser target is not visible")
        if not target.is_enabled(timeout=self._policy.timeout_milliseconds):
            raise BrowserTargetUnavailable("The named browser target is disabled")
        details = target.evaluate(
            "element => ({tag: element.tagName.toLowerCase(), type: "
            "(element.getAttribute('type') || '').toLowerCase(), "
            "autocomplete: (element.getAttribute('autocomplete') || '').toLowerCase(), "
            "target: (element.getAttribute('target') || '').toLowerCase(), "
            "href: element.getAttribute('href') || '', "
            "disabled: Boolean(element.disabled), readonly: Boolean(element.readOnly)})",
            timeout=self._policy.timeout_milliseconds,
        )
        if not isinstance(details, dict):
            raise BrowserTargetUnavailable("The named browser target could not be inspected")
        if request.action == "fill_text":
            if (details.get("tag") not in {"input", "textarea"}
                    or details.get("type") not in {"", "text", "search"}
                    or details.get("autocomplete") in {
                        "current-password", "new-password", "username", "email",
                        "cc-number", "cc-exp", "cc-csc", "one-time-code",
                    }
                    or details.get("readonly") is True
                    or target.get_attribute("name", timeout=self._policy.timeout_milliseconds)
                    and _SENSITIVE_LABEL.search(target.get_attribute(
                        "name", timeout=self._policy.timeout_milliseconds) or "")):
                raise BrowserPolicyDenied("Only non-sensitive text and search fields are supported")
        else:
            if details.get("tag") not in {"button", "a"}:
                raise BrowserPolicyDenied("Only native buttons and links can be clicked")
            if details.get("target") == "_blank":
                raise BrowserPolicyDenied("New-window navigation is not supported")
            if details.get("tag") == "a" and details.get("href"):
                target_url = urlsplit(urljoin(page.url, details["href"]))
                if _origin_from_parts(target_url) != _origin_from_url(page.url):
                    raise BrowserPolicyDenied("Links outside the approved origin cannot be clicked")
        return target

    def _target_digest(self, page, request, target) -> str:
        target_state = target.evaluate(
            "element => ({tag: element.tagName.toLowerCase(), "
            "type: (element.getAttribute('type') || '').toLowerCase(), "
            "disabled: Boolean(element.disabled), readonly: Boolean(element.readOnly), "
            "text: (element.innerText || element.value || '').slice(0, 1000), "
            "href: element.getAttribute('href') || ''})",
            timeout=self._policy.timeout_milliseconds,
        )
        body_text = page.locator("body").evaluate(
            "element => (element.innerText || '').slice(0, 12000)",
            timeout=self._policy.timeout_milliseconds,
        )
        return _digest({
            "url": page.url, "title": page.title()[:500],
            "body": body_text if isinstance(body_text, str) else "",
            "action": request.action, "role": request.role, "name": request.name,
            "target": target_state,
        })

    @staticmethod
    def _launch_chromium():
        return sync_playwright()


def _normalize_origin(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError("A canonical exact HTTPS origin is required")
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError("A canonical exact HTTPS origin is required") from None
    if (parsed.scheme != "https" or not host or parsed.username or parsed.password
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
            or port not in {None, 443}):
        raise ValueError("Only exact HTTPS origins without credentials or custom ports are supported")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    try:
        normalized_host = host.encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise ValueError("Browser origins must use exact public DNS host names") from None
    if (address is not None or "." not in normalized_host
            or normalized_host.endswith((".localhost", ".local", ".internal"))
            or any(not _HOST_LABEL.fullmatch(label) for label in normalized_host.split("."))):
        raise ValueError("Browser origins must use exact public DNS host names")
    canonical = f"https://{normalized_host}"
    if value.rstrip("/") != canonical:
        raise ValueError("Browser origins must be canonical exact HTTPS origins")
    return canonical


def _normalize_url(value: str) -> tuple[str, str]:
    if not isinstance(value, str) or len(value) > 2048 or any(ord(char) < 32 for char in value) or "\\" in value:
        raise ValueError("A valid exact-origin HTTPS page URL is required")
    try:
        parsed = urlsplit(value)
        origin = _normalize_origin(f"{parsed.scheme}://{parsed.netloc}")
    except ValueError:
        raise ValueError("A valid exact-origin HTTPS page URL is required") from None
    if parsed.query or parsed.fragment:
        raise ValueError("Browser URLs cannot contain query or fragment data")
    path = parsed.path or "/"
    if any(segment in {".", ".."} for segment in path.split("/")):
        raise ValueError("Browser paths cannot contain relative traversal segments")
    return origin, f"{origin}{path}"


def _origin_from_parts(parsed) -> str:
    host = parsed.hostname
    port = parsed.port
    if (parsed.scheme != "https" or host is None or port not in {None, 443}
            or parsed.username is not None or parsed.password is not None):
        return ""
    return f"https://{host.encode('idna').decode('ascii').lower()}"


def _origin_from_url(value: str) -> str:
    try:
        return _origin_from_parts(urlsplit(value))
    except (ValueError, UnicodeError):
        return ""


def _digest(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def _validate_session_id(session_id: str) -> None:
    if not isinstance(session_id, str) or not session_id.strip() or len(session_id) > 128:
        raise ValueError("An authenticated owner session is required")
