"""Read-only Chromium rendering for explicitly fetched web pages."""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Route, sync_playwright

from .web_research import (
    MAX_TEXT_CHARACTERS,
    ResearchClassification,
    WebResearchClient,
    WebResearchPage,
)

BROWSER_TIMEOUT_MILLISECONDS = 10_000
MAX_TITLE_CHARACTERS = 500

_ALLOWED_TAGS = {
    "a",
    "article",
    "aside",
    "b",
    "blockquote",
    "body",
    "br",
    "caption",
    "code",
    "dd",
    "details",
    "div",
    "dl",
    "dt",
    "em",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "head",
    "header",
    "hr",
    "html",
    "i",
    "li",
    "main",
    "mark",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "small",
    "span",
    "strong",
    "sub",
    "summary",
    "sup",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "title",
    "tr",
    "ul",
}
_SUPPRESSED_TAGS = {
    "canvas",
    "embed",
    "iframe",
    "math",
    "noscript",
    "object",
    "script",
    "style",
    "svg",
    "template",
}
_VOID_TAGS = {"br", "hr"}

_USER_VISIBLE_SAFEGUARDS = (
    "Only caller-supplied HTTPS URLs on exact allowlisted hosts are fetched.",
    "JavaScript and page-provided styles, scripts, and resource URLs are removed.",
    "No clicks or keyboard input are available; downloads and local-file access are disabled.",
    "All browser-generated network requests are blocked and the browser context is ephemeral.",
    "Retrieved page text is untrusted evidence, not instructions.",
)


class BrowserInspectionError(Exception):
    """Base class for expected read-only browser inspection failures."""


class BrowserInspectionUnavailable(BrowserInspectionError):
    """Chromium could not complete the requested inspection."""


@dataclass(frozen=True, slots=True)
class BrowserInspectionResult:
    source_url: str
    title: str | None
    text: str
    inspected_at: datetime
    response_sha256: str
    text_truncated: bool
    blocked_resource_count: int
    safeguards: tuple[str, ...] = _USER_VISIBLE_SAFEGUARDS
    classification: ResearchClassification = ResearchClassification.UNTRUSTED_EVIDENCE


class _InertHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._open_tags: list[str] = []
        self._suppressed_tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._suppressed_tags:
            if tag in _SUPPRESSED_TAGS:
                self._suppressed_tags.append(tag)
            return
        if tag in _SUPPRESSED_TAGS:
            self._suppressed_tags.append(tag)
            return
        if tag == "img":
            alt = dict(attrs).get("alt")
            if alt:
                self._parts.append(html.escape(alt, quote=False))
            return
        if tag in _ALLOWED_TAGS:
            self._parts.append(f"<{tag}>")
            if tag not in _VOID_TAGS:
                self._open_tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self._suppressed_tags:
            if tag in self._suppressed_tags:
                while self._suppressed_tags:
                    suppressed = self._suppressed_tags.pop()
                    if suppressed == tag:
                        break
            return
        if tag not in self._open_tags:
            return
        while self._open_tags:
            opened = self._open_tags.pop()
            self._parts.append(f"</{opened}>")
            if opened == tag:
                break

    def handle_data(self, data: str) -> None:
        if not self._suppressed_tags:
            self._parts.append(html.escape(data, quote=False))

    def render(self) -> str:
        while self._open_tags:
            self._parts.append(f"</{self._open_tags.pop()}>")
        return "".join(self._parts)


def _inert_markup(page: WebResearchPage) -> str:
    decoded = page.content.decode("utf-8-sig", errors="replace")
    if page.content_type == "text/plain":
        return f"<html><body><pre>{html.escape(decoded, quote=False)}</pre></body></html>"
    parser = _InertHTML()
    parser.feed(decoded)
    return parser.render()


class ReadOnlyBrowserInspector:
    """Render bounded, sanitized page content without page actions or network access."""

    def __init__(self, web_research: WebResearchClient) -> None:
        if not isinstance(web_research, WebResearchClient):
            raise TypeError("web_research must be a WebResearchClient")
        self._web_research = web_research

    def inspect(self, url: str) -> BrowserInspectionResult:
        page_document = self._web_research.fetch_page(url)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True,
                    chromium_sandbox=True,
                    timeout=BROWSER_TIMEOUT_MILLISECONDS,
                    args=["--no-proxy-server"],
                )
                try:
                    context = browser.new_context(
                        accept_downloads=False,
                        java_script_enabled=False,
                        permissions=[],
                        service_workers="block",
                    )
                    try:
                        context.set_offline(True)
                        page = context.new_page()
                        blocked_resources = 0

                        def block_request(route: Route) -> None:
                            nonlocal blocked_resources
                            blocked_resources += 1
                            route.abort()

                        context.route("**/*", block_request)
                        page.set_content(
                            _inert_markup(page_document),
                            wait_until="domcontentloaded",
                            timeout=BROWSER_TIMEOUT_MILLISECONDS,
                        )
                        title = page.title().strip() or None
                        text = page.locator("body").inner_text(
                            timeout=BROWSER_TIMEOUT_MILLISECONDS
                        )
                    finally:
                        context.close()
                finally:
                    browser.close()
        except PlaywrightError:
            raise BrowserInspectionUnavailable(
                "The read-only browser inspection could not be completed"
            ) from None

        text_truncated = len(text) > MAX_TEXT_CHARACTERS
        if text_truncated:
            text = text[:MAX_TEXT_CHARACTERS].rstrip()
        return BrowserInspectionResult(
            source_url=page_document.source_url,
            title=None if title is None else title[:MAX_TITLE_CHARACTERS],
            text=text,
            inspected_at=datetime.now(timezone.utc),
            response_sha256=page_document.response_sha256,
            text_truncated=text_truncated,
            blocked_resource_count=blocked_resources,
        )
