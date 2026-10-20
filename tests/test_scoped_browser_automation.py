from __future__ import annotations

from contextlib import contextmanager

import pytest
from playwright.sync_api import Error as PlaywrightError
from app.application.services.capability_approvals import CapabilityApprovalService
from app.application.services.capability_authorization import (
    CapabilityAuthorizationService,
)
from app.application.services.emergency_stop import EmergencyStopService
from app.integrations.scoped_browser_automation import (
    BrowserActionRequest,
    BrowserPolicyDenied,
    BrowserSitePolicy,
    BrowserTargetUnavailable,
    ScopedBrowserAutomation,
    ScopedBrowserError,
)


ORIGIN = "https://docs.example.com"
SESSION = "session-one"
OWNER = "local-owner"
PERMISSIONS = frozenset({"browser:act", "capability-approval:manage"})


class FakeLocator:
    def __init__(self, page: FakePage, role: str, name: str):
        self.page = page
        self.role = role
        self.name = name

    def count(self):
        return 1 if self.page.target_present else 0

    def is_visible(self, *, timeout):
        assert timeout == 2500
        return self.page.target_visible

    def is_enabled(self, *, timeout):
        assert timeout == 2500
        return self.page.target_enabled

    def evaluate(self, expression, *, timeout):
        assert timeout == 2500
        if self.role == "body":
            return self.page.body_text
        if "element.tagName" in expression:
            return {
                "tag": self.page.tag,
                "type": self.page.input_type,
                "autocomplete": self.page.autocomplete,
                "target": "",
                "href": self.page.href,
                "disabled": not self.page.target_enabled,
                "readonly": self.page.readonly,
            }
        return {
            "tag": self.page.tag,
            "type": self.page.input_type,
            "disabled": not self.page.target_enabled,
            "readonly": self.page.readonly,
            "text": self.page.value or self.page.name,
            "href": self.page.href,
        }

    def get_attribute(self, name, *, timeout):
        assert timeout == 2500
        return self.page.target_attributes.get(name)

    def click(self, *, timeout):
        assert timeout == 2500
        self.page.clicks += 1
        self.page.action_route = FakeRoute(f"{ORIGIN}/save", method="POST")
        self.page.route_handler(self.page.action_route)
        if self.page.click_error:
            raise PlaywrightError("simulated timeout with sensitive internal detail")

    def fill(self, value, *, timeout):
        assert timeout == 2500
        self.page.value = value
        self.page.fills += 1

    def inner_text(self, *, timeout):
        assert timeout == 2500
        return self.page.body_text


class FakePage:
    def __init__(self):
        self.url = f"{ORIGIN}/settings"
        self.name = "Save settings"
        self.title_text = "Settings"
        self.body_text = "Preferences"
        self.target_present = True
        self.target_visible = True
        self.target_enabled = True
        self.tag = "button"
        self.input_type = ""
        self.autocomplete = ""
        self.readonly = False
        self.href = ""
        self.target_attributes = {}
        self.clicks = 0
        self.fills = 0
        self.click_error = False
        self.value = ""
        self.route_handler = None
        self.routes = []
        self.navigation_timeout = None

    def goto(self, url, *, wait_until, timeout):
        assert wait_until == "domcontentloaded"
        assert timeout == 2500
        self.url = url
        if self.route_handler is not None:
            same_origin = FakeRoute(f"{ORIGIN}/app.js", method="GET")
            same_origin_post = FakeRoute(f"{ORIGIN}/preload", method="POST")
            cross_origin = FakeRoute("https://attacker.example/steal")
            self.route_handler(same_origin)
            self.route_handler(same_origin_post)
            self.route_handler(cross_origin)
            self.routes.extend((same_origin, same_origin_post, cross_origin))

    def title(self):
        return self.title_text

    def get_by_role(self, role, *, name, exact):
        assert exact is True
        self.name = name
        return FakeLocator(self, role, name)

    def locator(self, selector):
        assert selector == "body"
        return FakeLocator(self, "body", "")


class FakeRoute:
    def __init__(self, url, method="GET"):
        self.request = type("Request", (), {"url": url, "method": method})()
        self.aborted = False
        self.continued = False

    def abort(self):
        self.aborted = True

    def continue_(self):
        self.continued = True


class FakeContext:
    def __init__(self, page):
        self.page = page
        self.route_handler = None
        self.options = None
        self.closed = False
        self.timeouts = []
        self.websocket_handler = None

    def set_default_timeout(self, timeout):
        self.timeouts.append(timeout)

    def set_default_navigation_timeout(self, timeout):
        self.timeouts.append(timeout)

    def route(self, _pattern, handler):
        self.route_handler = handler
        self.page.route_handler = handler

    def route_web_socket(self, pattern, handler):
        assert pattern == "**/*"
        self.websocket_handler = handler
        websocket = type("WebSocket", (), {"close": lambda self, **_kwargs: None})()
        handler(websocket)

    def new_page(self):
        return self.page

    def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self, context):
        self.context = context
        self.options = None
        self.closed = False

    def new_context(self, **options):
        self.options = options
        return self.context

    def close(self):
        self.closed = True


class FakeChromium:
    def __init__(self, browser):
        self.browser = browser
        self.options = None
        self.launches = 0

    def launch(self, **options):
        self.launches += 1
        self.options = options
        return self.browser


class FakePlaywright:
    def __init__(self):
        self.page = FakePage()
        self.context = FakeContext(self.page)
        self.browser = FakeBrowser(self.context)
        self.chromium = FakeChromium(self.browser)


class FakePlaywrightManager:
    def __init__(self, playwright):
        self.playwright = playwright

    def __enter__(self):
        return self.playwright

    def __exit__(self, *_args):
        return False


def make_service(*, origins=frozenset({ORIGIN}), actions=frozenset({"click", "fill_text"}),
                 max_actions=2, emergency=None):
    policy = BrowserSitePolicy(
        allowed_origins=origins, allowed_actions=actions,
        max_actions_per_session=max_actions, timeout_milliseconds=2500,
    )
    playwright = FakePlaywright()
    authorization = CapabilityAuthorizationService()
    approvals = CapabilityApprovalService(authorization)
    emergency = emergency or EmergencyStopService()
    service = ScopedBrowserAutomation(
        policy, approvals, authorization=authorization,
        emergency_stop=emergency, browser_launcher=lambda: FakePlaywrightManager(playwright),
    )
    return service, approvals, playwright, emergency


def request(action="click", *, name="Save settings", role="button", value=None, url=None):
    return BrowserActionRequest(action, url or f"{ORIGIN}/settings", role, name, value)


def preview(service, action_request):
    return service.preview(
        action_request, actor_id=OWNER, permissions=PERMISSIONS,
        session_grants=frozenset(), session_id=SESSION,
    )


def execute(service, action_request, approval_id):
    return service.execute(
        action_request, approval_id, actor_id=OWNER, permissions=PERMISSIONS,
        session_grants=frozenset(), session_id=SESSION,
    )


def test_deny_by_default_exact_origin_and_operation_policy():
    service, _approvals, _playwright, _stop = make_service(origins=frozenset())
    with pytest.raises(BrowserPolicyDenied):
        preview(service, request())

    service, _approvals, _playwright, _stop = make_service(actions=frozenset({"fill_text"}))
    with pytest.raises(BrowserPolicyDenied):
        preview(service, request())

    service, _approvals, _playwright, _stop = make_service()
    with pytest.raises(BrowserPolicyDenied):
        preview(service, request(url="https://sub.docs.example.com/settings"))
    with pytest.raises(ValueError):
        preview(service, request(url="https://docs.example.com/settings?token=secret"))


def test_preview_is_read_only_ephemeral_and_blocks_other_origins():
    service, _approvals, playwright, _stop = make_service()
    result = preview(service, request())

    assert result.state == "preview_only"
    assert result.confirmation_required is True
    assert len(result.target_digest) == len(result.payload_digest) == 64
    assert playwright.page.clicks == playwright.page.fills == 0
    assert playwright.browser.closed is True
    assert playwright.context.closed is True
    assert playwright.browser.options == {
        "accept_downloads": False, "java_script_enabled": True,
        "permissions": [], "service_workers": "block",
    }
    assert playwright.chromium.options["headless"] is False
    assert playwright.chromium.options["chromium_sandbox"] is True
    assert all(route.continued for route in playwright.page.routes[:1])
    assert all(route.aborted for route in playwright.page.routes[1:])


def test_browser_action_requires_exact_owner_approval_then_reports_unknown_remote_result():
    service, approvals, playwright, _stop = make_service()
    action = request()
    before = preview(service, action)
    record = service.request_approval(
        action, actor_id=OWNER, permissions=PERMISSIONS,
        session_grants=frozenset(), session_id=SESSION,
    )
    assert record["status"] == "pending"
    assert record["payload_digest"] == before.payload_digest
    assert playwright.page.clicks == 0

    approvals.approve(
        record["approval_id"], approver_id=OWNER, permissions=PERMISSIONS,
        confirmed_digest=record["approval_digest"],
    )
    result = execute(service, action, record["approval_id"])

    assert result["status"] == "action_dispatched"
    assert result["remote_outcome"] == "unknown"
    trace = service.trace_service.get(result["trace_id"], actor_id=OWNER)
    assert trace.grant_id == record["approval_id"]
    assert trace.action_id == "browser.click"
    assert trace.before_digest == record["target_digest"]
    assert trace.after_state == "unknown"
    assert trace.screenshot_references == ()
    assert playwright.page.clicks == 1
    assert playwright.page.action_route.continued is True
    assert approvals.get(record["approval_id"]).status == "consumed"
    assert playwright.browser.closed is True


def test_unapproved_action_is_rejected_before_opening_a_browser():
    service, _approvals, playwright, _stop = make_service()
    action = request()
    record = service.request_approval(
        action, actor_id=OWNER, permissions=PERMISSIONS,
        session_grants=frozenset(), session_id=SESSION,
    )
    launches = playwright.chromium.launches
    with pytest.raises(ScopedBrowserError, match="not currently owner-approved"):
        execute(service, action, record["approval_id"])
    assert playwright.chromium.launches == launches
    assert playwright.page.clicks == 0


def test_approval_is_bound_to_payload_target_and_fresh_page_state():
    service, approvals, playwright, _stop = make_service()
    playwright.page.tag = "input"
    playwright.page.input_type = "text"
    action = request(action="fill_text", name="Display name", role="textbox", value="New label")
    record = service.request_approval(
        action, actor_id=OWNER, permissions=PERMISSIONS,
        session_grants=frozenset(), session_id=SESSION,
    )
    approvals.approve(record["approval_id"], approver_id=OWNER, permissions=PERMISSIONS,
                     confirmed_digest=record["approval_digest"])
    altered = request(action="fill_text", name="Display name", role="textbox", value="Other label")
    with pytest.raises(ScopedBrowserError, match="not currently owner-approved"):
        execute(service, altered, record["approval_id"])
    assert playwright.page.fills == 0

    changed_record = service.request_approval(
        action, actor_id=OWNER, permissions=PERMISSIONS,
        session_grants=frozenset(), session_id=SESSION,
    )
    approvals.approve(changed_record["approval_id"], approver_id=OWNER,
                       permissions=PERMISSIONS, confirmed_digest=changed_record["approval_digest"])
    playwright.page.body_text = "Preferences changed"
    with pytest.raises(ScopedBrowserError, match="page changed after approval"):
        execute(service, action, changed_record["approval_id"])
    assert playwright.page.fills == 0


def test_sensitive_fields_and_non_native_click_targets_are_denied():
    service, _approvals, playwright, _stop = make_service()
    with pytest.raises(BrowserPolicyDenied):
        preview(service, request(action="fill_text", name="Account email", role="textbox", value="x@example.com"))
    playwright.page.tag = "input"
    playwright.page.input_type = "password"
    with pytest.raises(BrowserPolicyDenied):
        preview(service, request(action="fill_text", name="Password", role="textbox", value="secret"))
    playwright.page.tag = "div"
    with pytest.raises(BrowserPolicyDenied):
        preview(service, request(action="click", name="Save settings", role="button"))


def test_emergency_stop_and_per_session_action_limit_block_dispatch():
    stop = EmergencyStopService()
    service, approvals, playwright, _stop = make_service(max_actions=1, emergency=stop)
    action = request()
    first = service.request_approval(action, actor_id=OWNER, permissions=PERMISSIONS,
                                    session_grants=frozenset(), session_id=SESSION)
    approvals.approve(first["approval_id"], approver_id=OWNER, permissions=PERMISSIONS,
                      confirmed_digest=first["approval_digest"])
    stop.stop()
    with pytest.raises(ScopedBrowserError, match="emergency stop"):
        execute(service, action, first["approval_id"])
    assert playwright.page.clicks == 0
    stop.resume()
    assert execute(service, action, first["approval_id"])["status"] == "action_dispatched"

    second = service.request_approval(action, actor_id=OWNER, permissions=PERMISSIONS,
                                      session_grants=frozenset(), session_id=SESSION)
    approvals.approve(second["approval_id"], approver_id=OWNER, permissions=PERMISSIONS,
                      confirmed_digest=second["approval_digest"])
    with pytest.raises(ScopedBrowserError, match="action limit"):
        execute(service, action, second["approval_id"])
    assert playwright.page.clicks == 1


def test_policy_rejects_non_public_or_noncanonical_origins_and_unsafe_links():
    for origin in ("http://docs.example.com", "https://127.0.0.1", "https://localhost",
                   "https://*.example.com", "https://docs.example.com/path"):
        with pytest.raises(ValueError):
            BrowserSitePolicy(allowed_origins=frozenset({origin}))

    service, _approvals, playwright, _stop = make_service()
    playwright.page.tag = "a"
    playwright.page.href = "https://attacker.example/"
    with pytest.raises(BrowserPolicyDenied):
        preview(service, request(role="link", name="Open report"))


def test_authorization_failure_and_ambiguous_target_fail_closed():
    service, _approvals, playwright, _stop = make_service()
    with pytest.raises(PermissionError):
        service.preview(request(), actor_id=OWNER, permissions=frozenset(),
                        session_grants=frozenset(), session_id=SESSION)
    playwright.page.target_present = False
    with pytest.raises(BrowserTargetUnavailable):
        preview(service, request())


def test_playwright_failure_after_click_is_unknown_and_never_retried():
    service, approvals, playwright, _stop = make_service()
    playwright.page.click_error = True
    action = request()
    record = service.request_approval(
        action, actor_id=OWNER, permissions=PERMISSIONS,
        session_grants=frozenset(), session_id=SESSION,
    )
    approvals.approve(
        record["approval_id"], approver_id=OWNER, permissions=PERMISSIONS,
        confirmed_digest=record["approval_digest"],
    )

    with pytest.raises(ScopedBrowserError, match="may have been dispatched; its remote outcome is unknown") as error:
        execute(service, action, record["approval_id"])

    assert "sensitive internal detail" not in str(error.value)
    assert playwright.page.clicks == 1
    assert approvals.get(record["approval_id"]).status == "consumed"
