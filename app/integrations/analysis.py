from __future__ import annotations

import base64
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import httpx

from .discovery import (
    GITHUB_API_BASE_URL,
    GITHUB_API_TIMEOUT_SECONDS,
    GITHUB_REPOSITORY_SOURCE_TYPE,
    GitHubRateLimitError,
    PrivateRepositoryError,
    RepositoryNotFoundError,
    SourceDiscoveryResult,
    validate_github_repository_url,
)

MAX_FILES_INSPECTED = 50
MAX_FILE_BYTES = 48 * 1024
MAX_TOTAL_SOURCE_BYTES = 256 * 1024
MAX_TREE_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TREE_DEPTH = 8
MAX_DOCUMENTATION_FILES = 4
MAX_PATH_CHARACTERS = 1024

_TEXT_EXTENSIONS = {
    ".cs": "C#",
    ".go": "Go",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".php": "PHP",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
}
_MANIFEST_NAMES = {
    "cargo.toml",
    "composer.json",
    "go.mod",
    "package.json",
    "poetry.lock",
    "pyproject.toml",
    "requirements.txt",
    "setup.cfg",
    "setup.py",
}
_CONFIG_NAMES = {
    "dockerfile",
    ".gitignore",
    "makefile",
    "tsconfig.json",
}
_DOC_EXTENSIONS = {".md", ".markdown", ".rst", ".txt"}
_LANGUAGE_BY_EXTENSION = {
    **_TEXT_EXTENSIONS,
    ".json": "JSON",
    ".toml": "TOML",
    ".yaml": "YAML",
    ".yml": "YAML",
}
_PURPOSE_LINE = re.compile(r"^\s*(?:#\s*)?(.{8,180})\s*$")


class SourceAnalysisError(Exception):
    """Base class for expected external source analysis failures."""


class UnsupportedAnalysisSourceError(SourceAnalysisError):
    pass


class SourceAnalysisAPIError(SourceAnalysisError):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"GitHub API error ({status_code}): {message}")


class SourceAnalysisNetworkError(SourceAnalysisError):
    pass


class MalformedSourceAnalysisResponseError(SourceAnalysisError):
    pass


@dataclass(frozen=True)
class ProjectFile:
    path: str
    category: str
    size_bytes: int | None


@dataclass(frozen=True)
class AnalysisObservation:
    statement: str
    evidence_paths: tuple[str, ...]


@dataclass(frozen=True)
class SourceAnalysisResult:
    id: str
    source_discovery_id: str
    repository_url: str
    repository_name: str
    analyzed_at: datetime
    detected_languages: tuple[str, ...]
    top_level_directories: tuple[str, ...]
    important_files: tuple[ProjectFile, ...]
    dependency_manifests: tuple[str, ...]
    documentation_files: tuple[str, ...]
    test_paths: tuple[str, ...]
    detected_frameworks: tuple[AnalysisObservation, ...]
    project_purpose: AnalysisObservation | None
    potential_capabilities: tuple[AnalysisObservation, ...]
    analysis_notes: tuple[str, ...]
    is_complete: bool
    source_bytes_inspected: int
    revision_sha: str | None = None


class SourceAnalyzer(ABC):
    """Adapter boundary for bounded analysis of a discovered external source."""

    @abstractmethod
    def analyze(self, discovery: SourceDiscoveryResult) -> SourceAnalysisResult:
        raise NotImplementedError


@dataclass(frozen=True)
class _TreeFile:
    path: str
    size_bytes: int | None
    sha: str
    category: str


class _ResponseLimitExceeded(Exception):
    pass


class GitHubRepositoryAnalyzer(SourceAnalyzer):
    """Inspect bounded GitHub tree, documentation, and dependency metadata."""

    def analyze(self, discovery: SourceDiscoveryResult) -> SourceAnalysisResult:
        return self._analyze(discovery, pin_revision=False)

    def analyze_pinned(self, discovery: SourceDiscoveryResult) -> SourceAnalysisResult:
        """Analyze a commit resolved once from the discovered default branch."""
        return self._analyze(discovery, pin_revision=True)

    def _analyze(
        self, discovery: SourceDiscoveryResult, *, pin_revision: bool
    ) -> SourceAnalysisResult:
        if not isinstance(discovery, SourceDiscoveryResult):
            raise TypeError("discovery must be a SourceDiscoveryResult")
        if discovery.source.source_type != GITHUB_REPOSITORY_SOURCE_TYPE:
            raise UnsupportedAnalysisSourceError(
                f"Unsupported source type: {discovery.source.source_type}"
            )
        if not discovery.is_public:
            raise PrivateRepositoryError(
                "Only public GitHub repositories can be analyzed"
            )

        owner, repository, canonical_url = validate_github_repository_url(
            discovery.repository_url
        )
        if (
            len(owner) > 100
            or len(repository) > 100
            or (
                discovery.default_branch is not None
                and len(discovery.default_branch) > 255
            )
        ):
            raise MalformedSourceAnalysisResponseError(
                "Discovery result contains an overlong repository identifier"
            )
        if (
            owner.casefold() != discovery.owner.casefold()
            or repository.casefold() != discovery.repository_name.casefold()
        ):
            raise MalformedSourceAnalysisResponseError(
                "Discovery result repository identity does not match its URL"
            )

        notes: list[str] = []
        total_bytes = [0]
        revision_sha = None
        tree_reference = discovery.default_branch
        if discovery.default_branch is None:
            notes.append("Analysis is incomplete because no default branch was discovered.")
            return self._result(
                discovery,
                canonical_url,
                (),
                (),
                (),
                (),
                (),
                (),
                (),
                None,
                (),
                notes,
                False,
            )
        if pin_revision:
            commit_payload, revision_limited, _ = self._request_json(
                f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}"
                f"/commits/{quote(discovery.default_branch, safe='')}",
                max_bytes=64 * 1024,
                total_bytes=total_bytes,
            )
            commit_details = (
                commit_payload.get("commit") if commit_payload is not None else None
            )
            tree_details = (
                commit_details.get("tree")
                if isinstance(commit_details, dict)
                else None
            )
            candidate_revision = (
                commit_payload.get("sha") if commit_payload is not None else None
            )
            candidate_tree = (
                tree_details.get("sha") if isinstance(tree_details, dict) else None
            )
            if (
                revision_limited
                or not isinstance(candidate_revision, str)
                or re.fullmatch(r"[0-9a-fA-F]{40}", candidate_revision) is None
                or not isinstance(candidate_tree, str)
                or re.fullmatch(r"[0-9a-fA-F]{40}", candidate_tree) is None
            ):
                raise MalformedSourceAnalysisResponseError(
                    "GitHub did not return a valid pinned commit and tree"
                )
            revision_sha = candidate_revision.lower()
            tree_reference = candidate_tree.lower()
        tree_payload, tree_limited, _ = self._request_json(
            f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}"
            f"/git/trees/{quote(tree_reference, safe='')}?recursive=1",
            max_bytes=MAX_TREE_RESPONSE_BYTES,
            total_bytes=total_bytes,
            allow_limit=True,
        )
        if tree_limited or tree_payload is None:
            notes.append("The repository tree exceeded the response limit; analysis is partial.")
            return self._result(
                discovery,
                canonical_url,
                (),
                (),
                (),
                (),
                (),
                (),
                (),
                None,
                (),
                notes,
                False,
                revision_sha=revision_sha,
            )

        tree_entries = tree_payload.get("tree")
        if not isinstance(tree_entries, list):
            raise MalformedSourceAnalysisResponseError(
                "GitHub tree response is missing a valid tree"
            )
        if tree_payload.get("truncated") is True:
            notes.append("GitHub truncated the repository tree response.")

        directories: set[str] = set()
        files: list[_TreeFile] = []
        for entry in tree_entries:
            if not isinstance(entry, dict):
                raise MalformedSourceAnalysisResponseError(
                    "GitHub tree contains a malformed entry"
                )
            path = entry.get("path")
            entry_type = entry.get("type")
            if (
                not isinstance(path, str)
                or not path
                or len(path) > MAX_PATH_CHARACTERS
                or path.startswith("/")
            ):
                raise MalformedSourceAnalysisResponseError(
                    "GitHub tree contains an invalid path"
                )
            parts = path.split("/")
            if any(part in {"", ".", ".."} for part in parts):
                raise MalformedSourceAnalysisResponseError(
                    "GitHub tree contains an unsafe path"
                )
            directories.update("/".join(parts[:index]) for index in range(1, len(parts)))
            if entry_type != "blob":
                continue
            size = entry.get("size")
            if size is not None and (
                isinstance(size, bool) or not isinstance(size, int) or size < 0
            ):
                raise MalformedSourceAnalysisResponseError(
                    f"GitHub tree has an invalid size for {path}"
                )
            sha = entry.get("sha")
            if not isinstance(sha, str) or not sha:
                raise MalformedSourceAnalysisResponseError(
                    f"GitHub tree has no blob identifier for {path}"
                )
            category = self._categorize(path)
            if category is not None and len(parts) <= MAX_TREE_DEPTH:
                files.append(_TreeFile(path, size, sha, category))

        files.sort(key=self._file_priority)
        selected = files[:MAX_FILES_INSPECTED]
        if len(files) > MAX_FILES_INSPECTED:
            notes.append(
                f"Only the first {MAX_FILES_INSPECTED} relevant files were inspected."
            )
        if sum(file.category == "documentation" for file in selected) > MAX_DOCUMENTATION_FILES:
            notes.append(
                f"Only {MAX_DOCUMENTATION_FILES} documentation files were read."
            )

        if tree_payload.get("truncated") is True:
            notes.append("File and directory inventories may be incomplete.")

        languages = {
            file_language
            for file in selected
            if (file_language := self._language_for_path(file.path)) is not None
        }
        if discovery.language:
            languages.add(discovery.language)
        if not languages:
            notes.append("No project language could be identified from repository metadata or file extensions.")

        content_by_path: dict[str, str] = {}
        if discovery.readme_excerpt and not pin_revision:
            content_by_path["README (discovery excerpt)"] = discovery.readme_excerpt
        downloaded_source_bytes = (
            len(discovery.readme_excerpt.encode("utf-8"))
            if discovery.readme_excerpt is not None and not pin_revision
            else 0
        )
        documentation_count = 0
        complete = (
            tree_payload.get("truncated") is not True
            and len(files) <= MAX_FILES_INSPECTED
            and sum(file.category == "documentation" for file in selected)
            <= MAX_DOCUMENTATION_FILES
        )
        manifest_files = tuple(
            file.path for file in selected if file.category == "dependency_manifest"
        )
        documentation_files = tuple(
            file.path for file in selected if file.category == "documentation"
        )
        important = tuple(
            ProjectFile(file.path, file.category, file.size_bytes)
            for file in selected
        )

        for file in selected:
            is_readme = file.path.casefold().split("/")[-1].startswith("readme")
            should_read = file.category == "dependency_manifest"
            if file.category == "documentation" and documentation_count < MAX_DOCUMENTATION_FILES:
                should_read = not (
                    is_readme
                    and discovery.readme_excerpt is not None
                    and not pin_revision
                )
                documentation_count += 1
            if not should_read:
                continue
            if file.size_bytes is not None and file.size_bytes > MAX_FILE_BYTES:
                notes.append(f"Skipped oversized file: {file.path}.")
                complete = False
                continue
            remaining_budget = MAX_TOTAL_SOURCE_BYTES - downloaded_source_bytes
            if remaining_budget <= 0:
                notes.append("The total source-content byte limit was reached.")
                complete = False
                break
            byte_limit = min(MAX_FILE_BYTES, remaining_budget)
            path = quote(file.path, safe="/")
            content_ref = revision_sha if pin_revision else discovery.default_branch
            file_payload, limited, _ = self._request_json(
                f"/repos/{quote(owner, safe='')}/{quote(repository, safe='')}"
                f"/contents/{path}?ref={quote(content_ref or '', safe='')}",
                max_bytes=(byte_limit * 4 // 3) + 4096,
                total_bytes=total_bytes,
                allow_limit=True,
                allow_not_found=True,
            )
            if limited:
                notes.append(f"Skipped content exceeding the retrieval limit: {file.path}.")
                complete = False
                continue
            if file_payload is None:
                notes.append(f"Source file was unavailable during retrieval: {file.path}.")
                complete = False
                continue
            text, actual_size = self._decode_file(file_payload, file.path)
            if actual_size > byte_limit:
                notes.append(f"Skipped content exceeding the retrieval limit: {file.path}.")
                complete = False
                continue
            downloaded_source_bytes += actual_size
            if text is not None:
                content_by_path[file.path] = text
            else:
                notes.append(f"Skipped non-UTF-8 content: {file.path}.")
                complete = False

        frameworks = self._detect_frameworks(content_by_path)
        purpose = self._infer_purpose(
            discovery, content_by_path, include_metadata=not pin_revision
        )
        documentation_content = {
            path: content
            for path, content in content_by_path.items()
            if path == "README (discovery excerpt)"
            or self._categorize(path) == "documentation"
        }
        capabilities = self._infer_capabilities(documentation_content)
        if purpose is None:
            notes.append(
                "No documentation evidence was available for purpose analysis."
            )

        return self._result(
            discovery,
            canonical_url,
            tuple(sorted(languages)),
            tuple(sorted(directory for directory in directories if "/" not in directory)),
            important,
            manifest_files,
            documentation_files,
            tuple(
                directory
                for directory in sorted(directories)
                if directory.casefold() in {"test", "tests", "__tests__", "spec", "specs"}
                or directory.casefold().startswith(("test/", "tests/", "spec/"))
            ),
            tuple(frameworks),
            purpose,
            tuple(capabilities),
            tuple(dict.fromkeys(notes)),
            complete,
            source_bytes_inspected=downloaded_source_bytes,
            revision_sha=revision_sha,
        )

    @staticmethod
    def _request_json(
        path: str,
        *,
        max_bytes: int,
        total_bytes: list[int],
        allow_limit: bool = False,
        allow_not_found: bool = False,
    ) -> tuple[dict[str, Any] | None, bool, int]:
        url = f"{GITHUB_API_BASE_URL}{path}"
        received = 0
        try:
            with httpx.stream(
                "GET",
                url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "ERSELMETZ-AI-CORPORATION",
                },
                timeout=GITHUB_API_TIMEOUT_SECONDS,
                follow_redirects=False,
            ) as response:
                if response.status_code == 404:
                    if allow_not_found:
                        return None, False, 0
                    raise RepositoryNotFoundError(
                        "GitHub repository content was not found"
                    )
                if response.status_code == 429 or (
                    response.status_code == 403
                    and response.headers.get("x-ratelimit-remaining") == "0"
                ):
                    raise GitHubRateLimitError("GitHub API rate limit exceeded")
                if not 200 <= response.status_code < 300:
                    body = bytearray()
                    for chunk in response.iter_bytes(chunk_size=4096):
                        body.extend(chunk[: max(0, 4096 - len(body))])
                        if len(body) >= 4096:
                            break
                    message = "Request failed"
                    try:
                        error_payload = json.loads(body)
                    except (ValueError, TypeError):
                        error_payload = None
                    if isinstance(error_payload, dict) and isinstance(
                        error_payload.get("message"), str
                    ):
                        message = error_payload["message"][:300]
                    if response.status_code == 403 and "rate limit" in message.lower():
                        raise GitHubRateLimitError("GitHub API rate limit exceeded")
                    raise SourceAnalysisAPIError(response.status_code, message)

                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=4096):
                    available = max_bytes + 1 - len(body)
                    body.extend(chunk[:available])
                    if len(body) > max_bytes:
                        if allow_limit:
                            received = len(body)
                            break
                        raise _ResponseLimitExceeded
                else:
                    received = len(body)
        except httpx.RequestError as exc:
            raise SourceAnalysisNetworkError(
                "Could not connect to the GitHub API"
            ) from exc
        except _ResponseLimitExceeded:
            return None, True, max_bytes + 1

        total_bytes[0] += received
        if total_bytes[0] > MAX_TREE_RESPONSE_BYTES + MAX_TOTAL_SOURCE_BYTES + (
            MAX_FILES_INSPECTED * 4096
        ):
            return None, True, received
        if len(body) > max_bytes:
            return None, True, received
        try:
            payload = json.loads(body)
        except (ValueError, TypeError) as exc:
            raise MalformedSourceAnalysisResponseError(
                "GitHub API returned invalid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise MalformedSourceAnalysisResponseError(
                "GitHub API response must be a JSON object"
            )
        return payload, False, received

    @staticmethod
    def _decode_file(
        payload: dict[str, Any], path: str
    ) -> tuple[str | None, int]:
        if payload.get("type") != "file":
            raise MalformedSourceAnalysisResponseError(
                f"GitHub content response is not a file: {path}"
            )
        size = payload.get("size")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise MalformedSourceAnalysisResponseError(
                f"GitHub content response has an invalid size: {path}"
            )
        content = payload.get("content")
        encoding = payload.get("encoding")
        if not isinstance(content, str) or encoding != "base64":
            raise MalformedSourceAnalysisResponseError(
                f"GitHub content response is malformed: {path}"
            )
        try:
            decoded = base64.b64decode("".join(content.split()), validate=True)
        except ValueError as exc:
            raise MalformedSourceAnalysisResponseError(
                f"GitHub content response has invalid base64: {path}"
            ) from exc
        try:
            text = decoded.decode("utf-8")
        except UnicodeDecodeError:
            return None, size
        if len(decoded) != size:
            raise MalformedSourceAnalysisResponseError(
                f"GitHub content size does not match its metadata: {path}"
            )
        return text, size

    @staticmethod
    def _categorize(path: str) -> str | None:
        parts = path.split("/")
        name = parts[-1].casefold()
        extension = "." + name.rsplit(".", 1)[-1] if "." in name else ""
        if name.startswith("readme") or name == "license" or name.startswith("license."):
            return "documentation" if name.startswith("readme") else "license"
        if name in _MANIFEST_NAMES:
            return "dependency_manifest"
        if name in _CONFIG_NAMES or extension in {".json", ".yaml", ".yml", ".toml"}:
            return "configuration"
        if extension in _DOC_EXTENSIONS or any(
            part.casefold() in {"docs", "doc", "documentation"} for part in parts[:-1]
        ):
            return "documentation"
        if any(part.casefold() in {"test", "tests", "__tests__", "spec", "specs"} for part in parts[:-1]):
            return "test"
        if extension in _TEXT_EXTENSIONS:
            return "source"
        return None

    @staticmethod
    def _file_priority(file: _TreeFile) -> tuple[int, int, str]:
        priorities = {
            "documentation": 0,
            "dependency_manifest": 1,
            "configuration": 2,
            "test": 3,
            "source": 4,
            "license": 5,
        }
        return priorities[file.category], len(file.path), file.path.casefold()

    @staticmethod
    def _language_for_path(path: str) -> str | None:
        filename = path.rsplit("/", 1)[-1].casefold()
        if filename in {"requirements.txt", "setup.py", "pyproject.toml"}:
            return "Python"
        extension = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
        return _LANGUAGE_BY_EXTENSION.get(extension)

    @staticmethod
    def _detect_frameworks(
        content_by_path: dict[str, str]
    ) -> list[AnalysisObservation]:
        checks = {
            "Django": ("django",),
            "FastAPI": ("fastapi",),
            "Flask": ("flask",),
            "Next.js": ('"next"',),
            "React": ('"react"',),
            "Express": ('"express"',),
        }
        found: list[AnalysisObservation] = []
        for framework, needles in checks.items():
            evidence = tuple(
                path
                for path, content in content_by_path.items()
                if any(needle in content.casefold() for needle in needles)
            )
            if evidence:
                found.append(
                    AnalysisObservation(
                        f"Inspected repository text mentions {framework}.",
                        evidence,
                    )
                )
        return found

    @staticmethod
    def _infer_purpose(
        discovery: SourceDiscoveryResult,
        content_by_path: dict[str, str],
        *,
        include_metadata: bool = True,
    ) -> AnalysisObservation | None:
        sources: list[tuple[str, str]] = []
        if include_metadata and discovery.readme_excerpt:
            sources.append(("README (discovery excerpt)", discovery.readme_excerpt))
        sources.extend(
            (path, content)
            for path, content in content_by_path.items()
            if path.casefold().split("/")[-1].startswith("readme")
        )
        if include_metadata and discovery.description:
            sources.append(("repository description", discovery.description))
        for path, content in sources:
            for line in content.splitlines():
                is_heading = line.lstrip().startswith("#")
                cleaned = line.strip().lstrip("#").strip()
                if not cleaned or cleaned.startswith(("http://", "https://")):
                    continue
                if is_heading and cleaned.casefold() in {
                    "overview",
                    "project purpose",
                    "purpose",
                    "readme",
                    "table of contents",
                }:
                    continue
                match = _PURPOSE_LINE.match(cleaned)
                if match:
                    statement = match.group(1).strip()
                    return AnalysisObservation(
                        f"Available source information describes the project as: {statement}",
                        (path,),
                    )
        return None

    @staticmethod
    def _infer_capabilities(
        content_by_path: dict[str, str],
    ) -> list[AnalysisObservation]:
        patterns = {
            "code generation": re.compile(r"\b(?:generate|generates|generating)\s+code\b", re.I),
            "text summarization": re.compile(r"\b(?:summarize|summarizes|summarization)\b", re.I),
            "repository search": re.compile(r"\b(?:search|index|indexes|indexing)\s+(?:a\s+)?repositories\b", re.I),
            "image generation": re.compile(r"\b(?:generate|generates|generating)\s+images\b", re.I),
        }
        observations: list[AnalysisObservation] = []
        for capability, pattern in patterns.items():
            evidence = tuple(
                path
                for path, content in content_by_path.items()
                if pattern.search(content)
            )
            if evidence:
                observations.append(
                    AnalysisObservation(
                        f"Documentation mentions potential {capability} capability.",
                        evidence,
                    )
                )
        return observations

    @staticmethod
    def _result(
        discovery: SourceDiscoveryResult,
        canonical_url: str,
        languages: tuple[str, ...],
        top_level_directories: tuple[str, ...],
        important_files: tuple[ProjectFile, ...],
        dependency_manifests: tuple[str, ...],
        documentation_files: tuple[str, ...],
        test_paths: tuple[str, ...],
        frameworks: tuple[AnalysisObservation, ...],
        purpose: AnalysisObservation | None,
        capabilities: tuple[AnalysisObservation, ...],
        notes: tuple[str, ...] | list[str],
        is_complete: bool,
        *,
        source_bytes_inspected: int = 0,
        revision_sha: str | None = None,
    ) -> SourceAnalysisResult:
        return SourceAnalysisResult(
            id=str(uuid4()),
            source_discovery_id=discovery.id,
            repository_url=canonical_url,
            repository_name=discovery.repository_name,
            analyzed_at=datetime.now(timezone.utc),
            detected_languages=languages,
            top_level_directories=top_level_directories,
            important_files=important_files,
            dependency_manifests=dependency_manifests,
            documentation_files=documentation_files,
            test_paths=test_paths,
            detected_frameworks=frameworks,
            project_purpose=purpose,
            potential_capabilities=capabilities,
            analysis_notes=tuple(notes),
            is_complete=is_complete,
            source_bytes_inspected=source_bytes_inspected,
            revision_sha=revision_sha,
        )
