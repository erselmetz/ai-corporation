from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from app.integrations import (
    BrowserInspectionUnavailable,
    ReadOnlyBrowserInspector,
    ResearchDomainNotAllowed,
    WebResearchClient,
)
from app.integrations.web_research import WebResearchPage


class FakeRoute:
    def __init__(self) -> None:
        self.aborted = False

    def abort(self) -> None:
        self.aborted = True


class FakeLocator:
    def inner_text(self, *, timeout: int) -> str:
        assert timeout == 10_000
        return "Safe evidence"


class FakePage:
    def __init__(self, context: FakeContext) -> None:
        self.context = context
        self.markup = ""

    def set_content(self, markup: str, **options: object) -> None:
        assert options == {"wait_until": "domcontentloaded", "timeout": 10_000}
        self.markup = markup
        route = FakeRoute()
        assert self.context.route_handler is not None
        self.context.route_handler(route)
        self.context.routes_aborted.append(route.aborted)

    def title(self) -> str:
        return "Safe title"

    def locator(self, selector: str) -> FakeLocator:
        assert selector == "body"
        return FakeLocator()


class FakeContext:
    def __init__(self) -> None:
        self.route_handler = None
        self.routes_aborted: list[bool] = []
        self.page = FakePage(self)
        self.closed = False
        self.offline = False

    def new_page(self) -> FakePage:
        return self.page

    def set_offline(self, offline: bool) -> None:
        self.offline = offline

    def route(self, pattern: str, handler: object) -> None:
        assert pattern == "**/*"
        self.route_handler = handler

    def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self, context: FakeContext) -> None:
        self.context = context
        self.context_options: dict[str, object] | None = None
        self.closed = False

    def new_context(self, **options: object) -> FakeContext:
        self.context_options = options
        return self.context

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser
        self.launch_options: dict[str, object] | None = None

    def launch(self, **options: object) -> FakeBrowser:
        self.launch_options = options
        return self.browser


class FakePlaywright:
    def __init__(self, chromium: FakeChromium) -> None:
        self.chromium = chromium


class FakePlaywrightManager:
    def __init__(self, playwright: FakePlaywright) -> None:
        self.playwright = playwright

    def __enter__(self) -> FakePlaywright:
        return self.playwright

    def __exit__(self, *_args: object) -> bool:
        return False


def install_fake_browser(monkeypatch: pytest.MonkeyPatch) -> tuple[
    FakePage,
    FakeContext,
    FakeBrowser,
    FakeChromium,
]:
    context = FakeContext()
    browser = FakeBrowser(context)
    chromium = FakeChromium(browser)
    playwright = FakePlaywright(chromium)
    monkeypatch.setattr(
        "app.integrations.browser_inspection.sync_playwright",
        lambda: FakePlaywrightManager(playwright),
    )
    return context.page, context, browser, chromium


def fake_page(content: bytes, content_type: str = "text/html") -> WebResearchPage:
    return WebResearchPage(
        source_url="https://docs.example.com/page",
        content_type=content_type,
        content=content,
        retrieved_at=datetime.now(timezone.utc),
        response_sha256="a" * 64,
    )


def test_inspection_renders_only_inert_content_with_explicit_safeguards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page, context, browser, chromium = install_fake_browser(monkeypatch)
    source = WebResearchClient(frozenset({"docs.example.com"}))
    monkeypatch.setattr(
        source,
        "fetch_page",
        lambda _url: fake_page(
            b"<html><head><title>Untrusted title</title>"
            b"<script>secret()</script><style>body{display:none}</style>"
            b"</head><body><h1 onclick='secret()'>Safe heading</h1>"
            b"<iframe src='file:///C:/secret'>Frame secret</iframe>"
            b"<svg><script>SVG secret</script></svg>"
            b"<meta http-equiv='refresh' content='0;url=file:///C:/secret'>"
            b"<img src='file:///C:/private.txt' onerror='secret()' alt='Image text'>"
            b"<a href='file:///C:/private.txt'>Link text</a></body></html>"
        ),
    )

    result = ReadOnlyBrowserInspector(source).inspect(
        "https://docs.example.com/page"
    )

    assert "Untrusted title" in page.markup
    assert "Safe heading" in page.markup
    assert "Image text" in page.markup
    assert "Link text" in page.markup
    for forbidden in (
        "<script",
        "<style",
        "onclick",
        "onerror",
        "file:",
        "href=",
        "src=",
        "secret()",
        "Frame secret",
        "SVG secret",
        "refresh",
    ):
        assert forbidden not in page.markup
    assert context.routes_aborted == [True]
    assert context.offline is True
    assert context.closed is True
    assert browser.closed is True
    assert chromium.launch_options == {
        "headless": True,
        "chromium_sandbox": True,
        "timeout": 10_000,
        "args": ["--no-proxy-server"],
    }
    assert browser.context_options == {
        "accept_downloads": False,
        "java_script_enabled": False,
        "permissions": [],
        "service_workers": "block",
    }
    assert result.title == "Safe title"
    assert result.text == "Safe evidence"
    assert result.text_truncated is False
    assert result.blocked_resource_count == 1
    assert len(result.safeguards) >= 4
    assert result.classification.value == "untrusted_evidence"


def test_invalid_host_is_rejected_before_browser_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page, _context, _browser, chromium = install_fake_browser(monkeypatch)
    source = WebResearchClient(frozenset({"docs.example.com"}))

    with pytest.raises(ResearchDomainNotAllowed):
        ReadOnlyBrowserInspector(source).inspect("https://other.example.com/page")

    assert page.markup == ""
    assert chromium.launch_options is None


def test_inspection_output_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page, _context, _browser, _chromium = install_fake_browser(monkeypatch)
    source = WebResearchClient(frozenset({"docs.example.com"}))
    monkeypatch.setattr(
        page,
        "locator",
        lambda _selector: type(
            "LongTextLocator",
            (),
            {"inner_text": lambda _self, *, timeout: "x" * 20_001},
        )(),
    )
    monkeypatch.setattr(
        source,
        "fetch_page",
        lambda _url: fake_page(b"<p>safe</p>"),
    )

    result = ReadOnlyBrowserInspector(source).inspect(
        "https://docs.example.com/page"
    )

    assert len(result.text) == 20_000
    assert result.text_truncated is True


def test_browser_failure_does_not_expose_exception_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = WebResearchClient(frozenset({"docs.example.com"}))
    monkeypatch.setattr(
        source,
        "fetch_page",
        lambda _url: fake_page(b"<p>safe</p>"),
    )

    class FailingPlaywrightManager:
        def __enter__(self) -> FakePlaywright:
            raise PlaywrightError("token=secret C:\\private\\profile")

        def __exit__(self, *_args: object) -> bool:
            return False

    monkeypatch.setattr(
        "app.integrations.browser_inspection.sync_playwright",
        FailingPlaywrightManager,
    )

    with pytest.raises(BrowserInspectionUnavailable) as raised:
        ReadOnlyBrowserInspector(source).inspect("https://docs.example.com/page")

    assert "secret" not in str(raised.value)
    assert "private" not in str(raised.value)


def test_inspection_with_installed_chromium(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with sync_playwright() as playwright:
        if not Path(playwright.chromium.executable_path).is_file():
            pytest.skip("Playwright Chromium is not installed")
    source = WebResearchClient(frozenset({"docs.example.com"}))
    monkeypatch.setattr(
        source,
        "fetch_page",
        lambda _url: fake_page(
            b"<html><head><title>Browser title</title></head>"
            b"<body><p>Read-only browser evidence</p></body></html>"
        ),
    )

    result = ReadOnlyBrowserInspector(source).inspect(
        "https://docs.example.com/page"
    )

    assert result.title == "Browser title"
    assert result.text == "Read-only browser evidence"
