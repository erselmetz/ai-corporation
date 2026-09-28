from __future__ import annotations

import hashlib
import httpx
import os
import re
import shutil
import stat
import tarfile
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterator, Protocol
from urllib.parse import quote, unquote, urljoin, urlsplit
from uuid import uuid4

from .discovery import (
    GITHUB_API_BASE_URL,
    GITHUB_REPOSITORY_SOURCE_TYPE,
    InvalidSourceLocationError,
    SourceDiscoveryResult,
    validate_github_repository_url,
)

MAX_SOURCE_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_SOURCE_FILES = 2000
MAX_SOURCE_TOTAL_BYTES = 128 * 1024 * 1024
MAX_SOURCE_FILE_BYTES = 16 * 1024 * 1024
MAX_SOURCE_PATH_DEPTH = 12
MAX_SOURCE_ARCHIVE_MEMBERS = 5000
SOURCE_STAGING_TIMEOUT_SECONDS = 15.0
_BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")


class SourceStagingStatus(str, Enum):
    STAGED = "staged"
    INCOMPLETE = "incomplete"
    BLOCKED = "blocked"


class SourceStagingError(Exception):
    """Base class for source staging failures."""


class InvalidSourceForStagingError(SourceStagingError):
    pass


class UnsafeSourceArchiveError(SourceStagingError):
    pass


class SourceStagingLimitError(SourceStagingError):
    pass


def calculate_staged_source_digest(workspace: str | Path) -> tuple[str, int, int]:
    """Hash a staged tree using the canonical Task 34 path/content framing."""
    supplied_root = Path(workspace)
    try:
        if stat.S_ISLNK(supplied_root.lstat().st_mode):
            raise UnsafeSourceArchiveError(
                "Staged workspace is not a regular directory."
            )
        root = supplied_root.resolve(strict=True)
    except OSError as exc:
        raise UnsafeSourceArchiveError(
            "Staged workspace is not a regular directory."
        ) from exc
    if not root.is_dir():
        raise UnsafeSourceArchiveError("Staged workspace is not a regular directory.")

    digest = hashlib.sha256()
    file_count = 0
    total_bytes = 0
    pending = [root]
    files: list[Path] = []
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as iterator:
            entries = sorted(iterator, key=lambda entry: entry.name)
        for entry in entries:
            path = Path(entry.path)
            try:
                path.resolve(strict=True).relative_to(root)
            except (OSError, ValueError) as exc:
                raise UnsafeSourceArchiveError(
                    "Staged source path escaped its workspace."
                ) from exc
            if entry.is_symlink():
                raise UnsafeSourceArchiveError(
                    "Staged source contains a symbolic link."
                )
            if entry.is_dir(follow_symlinks=False):
                pending.append(path)
                continue
            if not entry.is_file(follow_symlinks=False):
                raise UnsafeSourceArchiveError(
                    "Staged source contains a non-regular file."
                )
            files.append(path)
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative_path = path.relative_to(root).as_posix()
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\x00")
        flags = os.O_RDONLY
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        try:
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink > 1:
                raise UnsafeSourceArchiveError(
                    "Staged source file is not an owned regular file."
                )
            size = 0
            with os.fdopen(descriptor, "rb") as source:
                descriptor = -1
                for chunk in iter(lambda: source.read(64 * 1024), b""):
                    size += len(chunk)
                    digest.update(chunk)
            total_bytes += size
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        digest.update(b"\x00")
        digest.update(str(size).encode("ascii"))
        file_count += 1
    return digest.hexdigest(), file_count, total_bytes


@dataclass(frozen=True)
class SourceStagingLimits:
    max_archive_bytes: int = MAX_SOURCE_ARCHIVE_BYTES
    max_files: int = MAX_SOURCE_FILES
    max_total_bytes: int = MAX_SOURCE_TOTAL_BYTES
    max_file_bytes: int = MAX_SOURCE_FILE_BYTES
    max_path_depth: int = MAX_SOURCE_PATH_DEPTH
    max_archive_members: int = MAX_SOURCE_ARCHIVE_MEMBERS

    def __post_init__(self) -> None:
        bounds = (
            ("max_archive_bytes", self.max_archive_bytes, MAX_SOURCE_ARCHIVE_BYTES),
            ("max_files", self.max_files, MAX_SOURCE_FILES),
            ("max_total_bytes", self.max_total_bytes, MAX_SOURCE_TOTAL_BYTES),
            ("max_file_bytes", self.max_file_bytes, MAX_SOURCE_FILE_BYTES),
            ("max_path_depth", self.max_path_depth, MAX_SOURCE_PATH_DEPTH),
            (
                "max_archive_members",
                self.max_archive_members,
                MAX_SOURCE_ARCHIVE_MEMBERS,
            ),
        )
        for name, value, hard_maximum in bounds:
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
            if value > hard_maximum:
                raise ValueError(f"{name} cannot exceed the hard maximum")


@dataclass(frozen=True)
class SourceStagingResult:
    staging_id: str
    source_discovery_id: str
    workspace_reference: str | None
    status: SourceStagingStatus
    sha256: str | None
    archive_sha256: str | None
    file_count: int
    total_bytes: int
    complete: bool
    staged_at: datetime
    sandbox_id: str | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.staging_id, str) or not self.staging_id.strip():
            raise ValueError("staging_id cannot be empty")
        if (
            not isinstance(self.source_discovery_id, str)
            or not self.source_discovery_id.strip()
        ):
            raise ValueError("source_discovery_id cannot be empty")
        if not isinstance(self.status, SourceStagingStatus):
            raise TypeError("status must be a SourceStagingStatus")
        if (
            isinstance(self.file_count, bool)
            or not isinstance(self.file_count, int)
            or self.file_count < 0
        ):
            raise ValueError("file_count must be a non-negative integer")
        if (
            isinstance(self.total_bytes, bool)
            or not isinstance(self.total_bytes, int)
            or self.total_bytes < 0
        ):
            raise ValueError("total_bytes must be a non-negative integer")
        if not isinstance(self.complete, bool):
            raise TypeError("complete must be a bool")
        if self.complete != (self.status == SourceStagingStatus.STAGED):
            raise ValueError("Only STAGED results may be complete")
        if self.complete and (
            self.workspace_reference is None
            or self.sha256 is None
            or self.archive_sha256 is None
        ):
            raise ValueError("A complete result requires workspace and SHA-256 values")
        if not isinstance(self.notes, tuple) or any(
            not isinstance(note, str) or not note.strip() for note in self.notes
        ):
            raise ValueError("notes must be a tuple of non-empty strings")


class _StreamingResponse(Protocol):
    status_code: int
    headers: httpx.Headers

    def raise_for_status(self) -> None: ...

    def iter_bytes(self) -> Iterator[bytes]: ...


class _StreamingClient(Protocol):
    def stream(self, method: str, url: str, **kwargs: object): ...


class SourceStager(ABC):
    """Controlled source-material staging boundary."""

    @abstractmethod
    def stage(
        self,
        discovery: SourceDiscoveryResult,
        *,
        sandbox_id: str | None = None,
    ) -> SourceStagingResult:
        raise NotImplementedError


@dataclass(frozen=True)
class _ValidatedMember:
    member: tarfile.TarInfo
    relative_path: PurePosixPath


class GitHubSourceStager(SourceStager):
    """Fetch and safely stage a bounded public GitHub source archive."""

    def __init__(
        self,
        *,
        limits: SourceStagingLimits | None = None,
        client: _StreamingClient | None = None,
        workspace_parent: str | Path | None = None,
        project_root: str | Path | None = None,
    ) -> None:
        self.limits = limits or SourceStagingLimits()
        if not isinstance(self.limits, SourceStagingLimits):
            raise TypeError("limits must be a SourceStagingLimits")
        self._client = client
        self._workspace_parent = (
            Path(workspace_parent) if workspace_parent is not None else None
        )
        self._default_workspace_parent = (
            Path(tempfile.gettempdir()) / "erselmetz-source-staging"
        )
        self._project_root = (
            Path(project_root).resolve()
            if project_root is not None
            else Path(__file__).resolve().parents[2]
        )

    @property
    def workspace_root(self) -> Path:
        """Configured parent directory under which this stager creates workspaces."""
        parent = self._workspace_parent or self._default_workspace_parent
        return parent.resolve()

    @property
    def project_root(self) -> Path:
        """Project root excluded from all staging workspaces."""
        return self._project_root

    def stage(
        self,
        discovery: SourceDiscoveryResult,
        *,
        sandbox_id: str | None = None,
    ) -> SourceStagingResult:
        staged_at = datetime.now(timezone.utc)
        staging_id = f"staging-{uuid4().hex}"
        discovery_id = (
            discovery.id if isinstance(discovery, SourceDiscoveryResult) else "unknown"
        )
        try:
            owner, repository, canonical_url = self._validate_discovery(discovery)
            if sandbox_id is not None and (
                not isinstance(sandbox_id, str) or not sandbox_id.strip()
            ):
                raise InvalidSourceForStagingError("sandbox_id cannot be empty")
            archive = self._download_archive(discovery, owner, repository)
            archive_hash = hashlib.sha256(archive).hexdigest()
            members = self._validate_archive(archive)
            workspace = self._create_workspace(staging_id)
            try:
                source_hash, file_count, total_bytes = self._stage_members(
                    archive, members, workspace
                )
            except Exception:
                shutil.rmtree(workspace, ignore_errors=True)
                raise
            return SourceStagingResult(
                staging_id=staging_id,
                source_discovery_id=discovery.id,
                workspace_reference=str(workspace),
                status=SourceStagingStatus.STAGED,
                sha256=source_hash,
                archive_sha256=archive_hash,
                file_count=file_count,
                total_bytes=total_bytes,
                complete=True,
                staged_at=staged_at,
                sandbox_id=sandbox_id,
                notes=(
                    "SHA-256 identifies staged bytes; it does not establish source trust.",
                    "Source files were staged as data only and were not executed or installed.",
                ),
            )
        except SourceStagingError as exc:
            return self._blocked_result(
                staging_id, discovery_id, staged_at, sandbox_id, str(exc)
            )
        except (
            httpx.HTTPError,
            InvalidSourceLocationError,
            OSError,
            tarfile.TarError,
            EOFError,
            ValueError,
        ) as exc:
            return self._blocked_result(
                staging_id,
                discovery_id,
                staged_at,
                sandbox_id,
                f"Source staging failed: {type(exc).__name__}: {exc}",
            )

    def _validate_discovery(
        self, discovery: SourceDiscoveryResult
    ) -> tuple[str, str, str]:
        if not isinstance(discovery, SourceDiscoveryResult):
            raise InvalidSourceForStagingError(
                "A validated SourceDiscoveryResult is required."
            )
        if discovery.source.source_type != GITHUB_REPOSITORY_SOURCE_TYPE:
            raise InvalidSourceForStagingError(
                "Only public GitHub repository discoveries are supported."
            )
        if not discovery.is_public:
            raise InvalidSourceForStagingError(
                "Private repositories cannot be staged."
            )
        if (
            not isinstance(discovery.id, str)
            or not discovery.id.strip()
            or not isinstance(discovery.owner, str)
            or not isinstance(discovery.repository_name, str)
            or not isinstance(discovery.repository_url, str)
            or not isinstance(discovery.source.location, str)
        ):
            raise InvalidSourceForStagingError(
                "Discovery result is missing valid repository identity fields."
            )
        owner, repository, canonical_url = validate_github_repository_url(
            discovery.repository_url
        )
        source_owner, source_repository, source_url = validate_github_repository_url(
            discovery.source.location
        )
        if (
            owner.casefold() != source_owner.casefold()
            or repository.casefold() != source_repository.casefold()
            or canonical_url.casefold() != source_url.casefold()
            or discovery.repository_name.casefold() != repository.casefold()
            or discovery.owner.casefold() != owner.casefold()
        ):
            raise InvalidSourceForStagingError(
                "Discovery metadata does not match its validated GitHub source."
            )
        branch = discovery.default_branch
        if (
            not isinstance(branch, str)
            or not _BRANCH_PATTERN.fullmatch(branch)
            or any(part in {"", ".", ".."} for part in branch.split("/"))
        ):
            raise InvalidSourceForStagingError(
                "Discovery result does not contain a safe default branch."
            )
        return owner, repository, canonical_url

    def _download_archive(
        self,
        discovery: SourceDiscoveryResult,
        owner: str,
        repository: str,
    ) -> bytes:
        branch = quote(discovery.default_branch or "", safe="")
        url = (
            f"{GITHUB_API_BASE_URL}/repos/{quote(owner, safe='')}/"
            f"{quote(repository, safe='')}/tarball/{branch}"
        )
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ERSELMETZ-source-stager",
        }
        own_client = self._client is None
        client = (
            httpx.Client(
                timeout=SOURCE_STAGING_TIMEOUT_SECONDS,
                follow_redirects=False,
                trust_env=False,
            )
            if own_client
            else self._client
        )
        assert client is not None
        try:
            for redirect_count in range(4):
                with client.stream(
                    "GET",
                    url,
                    headers=headers,
                    follow_redirects=False,
                ) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        if redirect_count == 3:
                            raise InvalidSourceForStagingError(
                                "GitHub archive redirected too many times."
                            )
                        location = response.headers.get("location")
                        url = self._validate_archive_redirect(
                            url, location, owner, repository
                        )
                        continue
                    response.raise_for_status()
                    content_length = response.headers.get("content-length")
                    if content_length is not None:
                        try:
                            declared_size = int(content_length)
                        except ValueError as exc:
                            raise UnsafeSourceArchiveError(
                                "Archive response has an invalid content length."
                            ) from exc
                        if declared_size < 0 or declared_size > self.limits.max_archive_bytes:
                            raise SourceStagingLimitError(
                                "Compressed source archive exceeds the byte limit."
                            )
                    payload = bytearray()
                    for chunk in response.iter_bytes():
                        if len(payload) + len(chunk) > self.limits.max_archive_bytes:
                            raise SourceStagingLimitError(
                                "Compressed source archive exceeds the byte limit."
                            )
                        payload.extend(chunk)
                    if not payload:
                        raise UnsafeSourceArchiveError("Source archive is empty.")
                    return bytes(payload)
            raise InvalidSourceForStagingError("GitHub archive redirect failed.")
        finally:
            if own_client:
                client.close()

    @staticmethod
    def _validate_archive_redirect(
        current_url: str,
        location: str | None,
        owner: str,
        repository: str,
    ) -> str:
        if not isinstance(location, str) or not location.strip():
            raise InvalidSourceForStagingError(
                "GitHub archive redirect has no Location header."
            )
        redirected = urljoin(current_url, location)
        parsed = urlsplit(redirected)
        expected_prefix = f"/{owner}/{repository}/"
        decoded_path = unquote(parsed.path)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "codeload.github.com"
            or parsed.port is not None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or not decoded_path.startswith(expected_prefix)
            or not any(
                decoded_path.startswith(expected_prefix + archive_kind + "/")
                for archive_kind in ("legacy.tar.gz", "tar.gz")
            )
            or "\\" in decoded_path
            or any(part in {".", ".."} for part in decoded_path.split("/"))
        ):
            raise InvalidSourceForStagingError(
                "GitHub archive redirect target is not an allowlisted codeload URL."
            )
        return redirected

    def _validate_archive(self, archive_bytes: bytes) -> tuple[_ValidatedMember, ...]:
        archive_stream = BytesIO(archive_bytes)
        try:
            archive = tarfile.open(fileobj=archive_stream, mode="r:gz")
        except (tarfile.TarError, OSError) as exc:
            raise UnsafeSourceArchiveError("Source is not a valid gzip tar archive.") from exc

        raw_members: list[tuple[tarfile.TarInfo, PurePosixPath, bool]] = []
        total_size = 0
        file_count = 0
        with archive:
            for member in archive:
                if len(raw_members) >= self.limits.max_archive_members:
                    raise SourceStagingLimitError(
                        "Source archive contains too many members."
                    )
                path = self._safe_archive_path(member.name)
                if member.isdir():
                    is_file = False
                elif member.isfile():
                    is_file = True
                    file_count += 1
                    if file_count > self.limits.max_files:
                        raise SourceStagingLimitError(
                            "Source archive contains too many files."
                        )
                    if member.size < 0 or member.size > self.limits.max_file_bytes:
                        raise SourceStagingLimitError(
                            f"Source file exceeds the individual file limit: {member.name}"
                        )
                    total_size += member.size
                    if total_size > self.limits.max_total_bytes:
                        raise SourceStagingLimitError(
                            "Expanded source exceeds the total byte limit."
                        )
                else:
                    raise UnsafeSourceArchiveError(
                        f"Unsupported archive member type: {member.name}"
                    )
                raw_members.append((member, path, is_file))

        root_prefix = self._common_archive_root(raw_members)
        validated: list[_ValidatedMember] = []
        seen_paths: set[str] = set()
        file_paths: set[str] = set()
        directories: set[str] = set()
        for member, path, is_file in raw_members:
            parts = path.parts[1:] if root_prefix is not None else path.parts
            if not parts:
                continue
            if len(parts) > self.limits.max_path_depth:
                raise SourceStagingLimitError(
                    f"Archive path is deeper than the configured limit: {member.name}"
                )
            normalized = PurePosixPath(*parts)
            relative = normalized.as_posix()
            if relative in seen_paths:
                raise UnsafeSourceArchiveError(
                    f"Duplicate archive path: {member.name}"
                )
            seen_paths.add(relative)
            (file_paths if is_file else directories).add(relative)
            validated.append(_ValidatedMember(member, normalized))

        for file_path in file_paths:
            parts = PurePosixPath(file_path).parts
            for index in range(1, len(parts)):
                if PurePosixPath(*parts[:index]).as_posix() in file_paths:
                    raise UnsafeSourceArchiveError(
                        f"Archive path conflicts with a file: {file_path}"
                    )
        if any(directory in file_paths for directory in directories):
            raise UnsafeSourceArchiveError(
                "Archive uses the same path as both a file and directory."
            )
        return tuple(
            sorted(validated, key=lambda item: item.relative_path.as_posix())
        )

    @staticmethod
    def _common_archive_root(
        members: list[tuple[tarfile.TarInfo, PurePosixPath, bool]],
    ) -> str | None:
        top_levels = {path.parts[0] for _, path, _ in members if path.parts}
        if len(top_levels) != 1:
            return None
        root = next(iter(top_levels))
        root_entry_exists = any(
            path.as_posix() == root and not is_file
            for _, path, is_file in members
        )
        return root if root_entry_exists else None

    @staticmethod
    def _safe_archive_path(name: str) -> PurePosixPath:
        if (
            not isinstance(name, str)
            or not name
            or "\x00" in name
            or "\\" in name
        ):
            raise UnsafeSourceArchiveError("Archive contains an invalid path.")
        windows_path = PureWindowsPath(name)
        if name.startswith("/") or windows_path.is_absolute() or windows_path.drive:
            raise UnsafeSourceArchiveError(
                f"Archive contains an absolute path: {name}"
            )
        path_text = name[:-1] if name.endswith("/") else name
        parts = path_text.split("/")
        if not path_text or any(
            part in {"", ".", ".."} or re.match(r"^[A-Za-z]:", part)
            for part in parts
        ):
            raise UnsafeSourceArchiveError(
                f"Archive contains an unsafe path: {name}"
            )
        return PurePosixPath(*parts)

    def _create_workspace(self, staging_id: str) -> Path:
        parent = self._workspace_parent or self._default_workspace_parent
        resolved_parent = parent.resolve()
        if self._is_inside(resolved_parent, self._project_root):
            raise InvalidSourceForStagingError(
                "Staging workspace must be outside the project repository."
            )
        parent.mkdir(parents=True, exist_ok=True)
        resolved_parent = parent.resolve()
        if self._is_inside(resolved_parent, self._project_root):
            raise InvalidSourceForStagingError(
                "Staging workspace must be outside the project repository."
            )
        workspace = Path(
            tempfile.mkdtemp(
                prefix=f"erselmetz-source-{staging_id}-",
                dir=resolved_parent,
            )
        ).resolve()
        if self._is_inside(workspace, self._project_root):
            shutil.rmtree(workspace, ignore_errors=True)
            raise InvalidSourceForStagingError(
                "Staging workspace resolved inside the project repository."
            )
        return workspace

    @staticmethod
    def _is_inside(path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False

    def _stage_members(
        self,
        archive_bytes: bytes,
        members: tuple[_ValidatedMember, ...],
        workspace: Path,
    ) -> tuple[str, int, int]:
        file_count = 0
        total_bytes = 0
        with tarfile.open(fileobj=BytesIO(archive_bytes), mode="r:gz") as archive:
            for validated in members:
                target = workspace.joinpath(*validated.relative_path.parts)
                resolved_target = target.resolve()
                if not self._is_inside(resolved_target, workspace):
                    raise UnsafeSourceArchiveError(
                        f"Staged path escaped workspace: {validated.relative_path}"
                    )
                if validated.member.isdir():
                    target.mkdir(parents=True, exist_ok=True, mode=0o700)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                source = archive.extractfile(validated.member)
                if source is None:
                    raise UnsafeSourceArchiveError(
                        f"Could not read archive file: {validated.member.name}"
                    )
                actual_size = 0
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                if hasattr(os, "O_BINARY"):
                    flags |= os.O_BINARY
                if hasattr(os, "O_NOFOLLOW"):
                    flags |= os.O_NOFOLLOW
                descriptor = os.open(target, flags, 0o600)
                try:
                    with os.fdopen(descriptor, "wb") as destination:
                        for chunk in iter(lambda: source.read(64 * 1024), b""):
                            actual_size += len(chunk)
                            total_bytes += len(chunk)
                            if (
                                actual_size > self.limits.max_file_bytes
                                or total_bytes > self.limits.max_total_bytes
                            ):
                                raise SourceStagingLimitError(
                                    "Expanded source exceeded a staging byte limit."
                                )
                            destination.write(chunk)
                finally:
                    source.close()
                if actual_size != validated.member.size:
                    raise UnsafeSourceArchiveError(
                        f"Archive file size did not match metadata: {validated.member.name}"
                    )
                file_count += 1
        digest, verified_file_count, verified_total_bytes = (
            calculate_staged_source_digest(workspace)
        )
        if (verified_file_count, verified_total_bytes) != (file_count, total_bytes):
            raise UnsafeSourceArchiveError(
                "Staged source metadata changed during workspace creation."
            )
        return digest, file_count, total_bytes

    @staticmethod
    def _blocked_result(
        staging_id: str,
        discovery_id: str,
        staged_at: datetime,
        sandbox_id: str | None,
        reason: str,
    ) -> SourceStagingResult:
        return SourceStagingResult(
            staging_id=staging_id,
            source_discovery_id=discovery_id,
            workspace_reference=None,
            status=SourceStagingStatus.BLOCKED,
            sha256=None,
            archive_sha256=None,
            file_count=0,
            total_bytes=0,
            complete=False,
            staged_at=staged_at,
            sandbox_id=sandbox_id,
            notes=(reason,),
        )
