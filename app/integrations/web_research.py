"""Caller-driven, allowlisted retrieval of untrusted web evidence."""

from __future__ import annotations

import hashlib
import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from html.parser import HTMLParser
from urllib.parse import urlsplit

import httpx

MAX_ALLOWED_DOMAINS = 64
MAX_URL_CHARACTERS = 2_048
MAX_RESPONSE_BYTES = 512 * 1024
MAX_TEXT_CHARACTERS = 20_000
REQUEST_TIMEOUT_SECONDS = 10.0

_DOMAIN_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_IGNORED_TAGS = {"script", "style", "noscript", "iframe", "object", "svg", "template"}


class WebResearchError(Exception):
    """Base class for expected web research failures."""


class InvalidResearchURL(WebResearchError):
    """The supplied URL is not a supported HTTPS page URL."""


class ResearchDomainNotAllowed(WebResearchError):
    """The URL host is not in the configured exact-host allowlist."""


class WebResearchFetchError(WebResearchError):
    """The page could not be retrieved."""


class WebResearchResponseTooLarge(WebResearchError):
    """The page response exceeded the configured size bound."""


class UnsupportedResearchContentType(WebResearchError):
    """The page did not return supported text content."""


class ResearchClassification(str, Enum):
    UNTRUSTED_EVIDENCE = "untrusted_evidence"


@dataclass(frozen=True, slots=True)
class WebResearchDocument:
    source_url: str
    title: str | None
    text: str
    retrieved_at: datetime
    response_sha256: str
    text_truncated: bool
    classification: ResearchClassification = ResearchClassification.UNTRUSTED_EVIDENCE


class _PageTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.title_parts: list[str] = []
        self._ignored_tag: str | None = None
        self._ignored_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if self._ignored_tag is not None:
            if tag == self._ignored_tag:
                self._ignored_depth += 1
            return
        if tag in _IGNORED_TAGS:
            self._ignored_tag = tag
            self._ignored_depth = 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if self._ignored_tag is not None:
            if tag == self._ignored_tag:
                self._ignored_depth -= 1
                if self._ignored_depth == 0:
                    self._ignored_tag = None
            return
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._ignored_tag is not None:
            return
        if self._in_title:
            self.title_parts.append(data)
        else:
            self.text_parts.append(data)


def _normalize_domain(domain: str) -> str:
    if not isinstance(domain, str) or not domain or len(domain) > 253:
        raise ValueError("Allowed research domains must be valid host names")
    try:
        normalized = domain.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise ValueError("Allowed research domains must be valid host names") from None
    if (
        "." not in normalized
        or normalized.startswith("*.")
        or normalized.endswith((".localhost", ".local", ".internal"))
        or any(not _DOMAIN_LABEL.fullmatch(label) for label in normalized.split("."))
    ):
        raise ValueError("Allowed research domains must be exact public host names")
    try:
        ipaddress.ip_address(normalized)
    except ValueError:
        return normalized
    raise ValueError("IP address allowlist entries are not supported")


def _normalize_page_url(url: str, allowed_domains: frozenset[str]) -> str:
    if (
        not isinstance(url, str)
        or not url
        or len(url) > MAX_URL_CHARACTERS
        or any(ord(character) < 32 for character in url)
        or "\\" in url
    ):
        raise InvalidResearchURL("A valid allowlisted HTTPS page URL is required")
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        raise InvalidResearchURL("A valid allowlisted HTTPS page URL is required") from None
    if (
        parsed.scheme.lower() != "https"
        or host is None
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.query
        or parsed.fragment
    ):
        raise InvalidResearchURL("Only HTTPS page URLs without credentials or query data are supported")
    try:
        normalized_host = _normalize_domain(host)
    except ValueError:
        raise InvalidResearchURL("A valid allowlisted HTTPS page URL is required") from None
    if normalized_host not in allowed_domains:
        raise ResearchDomainNotAllowed("The research page host is not allowed")
    path = parsed.path or "/"
    return f"https://{normalized_host}{path}"


def _extract_page_text(body: bytes, content_type: str) -> tuple[str | None, str]:
    decoded = body.decode("utf-8-sig", errors="replace")
    if content_type == "text/plain":
        return None, " ".join(decoded.split())
    parser = _PageTextParser()
    parser.feed(decoded)
    title = " ".join(" ".join(parser.title_parts).split()) or None
    return title, " ".join(" ".join(parser.text_parts).split())


class WebResearchClient:
    """Fetch explicit URLs from an exact-host allowlist without following links."""

    def __init__(self, allowed_domains: frozenset[str] = frozenset()) -> None:
        if (
            not isinstance(allowed_domains, frozenset)
            or len(allowed_domains) > MAX_ALLOWED_DOMAINS
            or any(not isinstance(domain, str) for domain in allowed_domains)
        ):
            raise ValueError("Research domains must be a bounded frozen allowlist")
        self._allowed_domains = frozenset(
            _normalize_domain(domain) for domain in allowed_domains
        )

    def retrieve(self, url: str) -> WebResearchDocument:
        source_url = _normalize_page_url(url, self._allowed_domains)
        try:
            with httpx.Client(
                timeout=REQUEST_TIMEOUT_SECONDS,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                with client.stream(
                    "GET",
                    source_url,
                    headers={"Accept": "text/html, text/plain;q=0.9"},
                ) as response:
                    if response.status_code != 200:
                        raise WebResearchFetchError("The research page request failed")
                    content_type = response.headers.get("content-type", "").split(
                        ";", maxsplit=1
                    )[0].strip().lower()
                    if content_type not in {"text/html", "text/plain"}:
                        raise UnsupportedResearchContentType(
                            "The research page did not return supported text content"
                        )
                    content_length = response.headers.get("content-length")
                    if content_length is not None:
                        try:
                            if int(content_length) > MAX_RESPONSE_BYTES:
                                raise WebResearchResponseTooLarge(
                                    "The research page response exceeded its size limit"
                                )
                        except ValueError:
                            raise WebResearchFetchError(
                                "The research page response was malformed"
                            ) from None
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                            raise WebResearchResponseTooLarge(
                                "The research page response exceeded its size limit"
                            )
                        body.extend(chunk)
        except httpx.RequestError:
            raise WebResearchFetchError("The research page request failed") from None

        title, text = _extract_page_text(bytes(body), content_type)
        text_truncated = len(text) > MAX_TEXT_CHARACTERS
        if text_truncated:
            text = text[:MAX_TEXT_CHARACTERS].rstrip()
        return WebResearchDocument(
            source_url=source_url,
            title=None if title is None else title[:500],
            text=text,
            retrieved_at=datetime.now(timezone.utc),
            response_sha256=hashlib.sha256(body).hexdigest(),
            text_truncated=text_truncated,
        )
