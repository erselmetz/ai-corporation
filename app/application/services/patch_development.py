"""Apply bounded caller-supplied diffs to explicitly selected disposable copies."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import os
import re
import stat
import tempfile
from pathlib import Path, PurePosixPath
from threading import RLock
from uuid import uuid4

from .maintenance_proposals import MaintenanceProposal, _validate_text


_HUNK_HEADER = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: .*)?$"
)
_PATCH_PATH = re.compile(r"^(---|\+\+\+) ([ab])/([^\t]+)(?:\t.*)?$")
_WINDOWS_RESERVED_NAMES = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)


@dataclass(frozen=True, slots=True)
class PatchWorkspace:
    workspace_id: str
    proposal_id: str
    files: tuple[str, ...]
    changed_files: tuple[str, ...]
    patch_sha256: str
    source_sha256: str
    created_at: datetime
    path: Path
    unified_diff: str = field(default="", repr=False)
    source_root: Path | None = field(default=None, repr=False)


class PatchDevelopmentService:
    MAX_FILES = 20
    MAX_PATCH_BYTES = 65536
    MAX_FILE_BYTES = 1024 * 1024
    MAX_TOTAL_SOURCE_BYTES = 16 * 1024 * 1024
    MAX_LINES = 10000
    MAX_WORKSPACES = 20

    def __init__(self):
        self._workspaces: dict[str, tuple[PatchWorkspace, tempfile.TemporaryDirectory]] = {}
        self._lock = RLock()

    def develop(
        self,
        proposal: MaintenanceProposal,
        source_root: str | Path,
        selected_files: tuple[str, ...],
        unified_diff: str,
    ) -> PatchWorkspace:
        if not isinstance(proposal, MaintenanceProposal):
            raise TypeError("Expected MaintenanceProposal")
        if not isinstance(selected_files, tuple) or not 1 <= len(selected_files) <= self.MAX_FILES:
            raise ValueError("Select an immutable tuple of 1 to 20 source files")
        paths = tuple(_validate_relative_path(item) for item in selected_files)
        if len(set(paths)) != len(paths):
            raise ValueError("Selected source paths must be unique")
        _validate_text(unified_diff, "unified_diff", self.MAX_PATCH_BYTES, allow_empty=False)
        parsed = _parse_unified_diff(unified_diff, frozenset(paths), self.MAX_LINES)

        try:
            root = Path(source_root).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError("Source root is unavailable") from exc
        if not root.is_dir():
            raise ValueError("Source root must be a directory")
        source_contents: dict[str, bytes] = {}
        total_bytes = 0
        for relative_path in paths:
            source_file = _source_file(root, relative_path)
            try:
                with source_file.open("rb") as stream:
                    content = stream.read(self.MAX_FILE_BYTES + 1)
            except OSError as exc:
                raise ValueError("Selected source file is unavailable") from exc
            if len(content) > self.MAX_FILE_BYTES:
                raise ValueError("Selected source file exceeds the byte limit")
            total_bytes += len(content)
            if total_bytes > self.MAX_TOTAL_SOURCE_BYTES:
                raise ValueError("Selected source files exceed the total byte limit")
            source_contents[relative_path] = content
        if any(path not in source_contents for path in parsed):
            raise ValueError("Patch references a file outside the selected source files")

        patched = {
            path: _apply_file_patch(source_contents[path], hunks, self.MAX_FILE_BYTES)
            for path, hunks in parsed.items()
        }
        workspace_source_digest = _source_digest(source_contents)
        patch_digest = hashlib.sha256(unified_diff.encode("utf-8")).hexdigest()
        with self._lock:
            if len(self._workspaces) >= self.MAX_WORKSPACES:
                raise ValueError("Patch workspace limit reached")
            temporary_directory = tempfile.TemporaryDirectory(prefix="ai-corp-patch-")
            workspace_path = Path(temporary_directory.name)
            try:
                for relative_path, original in source_contents.items():
                    destination = workspace_path.joinpath(*PurePosixPath(relative_path).parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(patched.get(relative_path, original))
                workspace = PatchWorkspace(
                    workspace_id=uuid4().hex,
                    proposal_id=proposal.proposal_id,
                    files=paths,
                    changed_files=tuple(sorted(patched)),
                    patch_sha256=patch_digest,
                    source_sha256=workspace_source_digest,
                    created_at=datetime.now(timezone.utc),
                    path=workspace_path,
                    unified_diff=unified_diff,
                    source_root=root,
                )
                self._workspaces[workspace.workspace_id] = (
                    workspace,
                    temporary_directory,
                )
                return workspace
            except BaseException:
                temporary_directory.cleanup()
                raise

    def get(self, workspace_id: str) -> PatchWorkspace:
        with self._lock:
            try:
                workspace, _ = self._workspaces[workspace_id]
            except KeyError:
                raise ValueError("Patch workspace not found") from None
            return workspace

    def dispose(self, workspace_id: str) -> None:
        with self._lock:
            try:
                _, temporary_directory = self._workspaces.pop(workspace_id)
            except KeyError:
                raise ValueError("Patch workspace not found") from None
        temporary_directory.cleanup()


def _validate_relative_path(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or any(ord(character) < 32 for character in value)
        or any(character in value for character in ':<>"|?*')
    ):
        raise ValueError("Source paths must be nonempty relative POSIX paths")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or not path.parts
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(part.endswith((" ", ".")) for part in path.parts)
        or any(part.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES for part in path.parts)
    ):
        raise ValueError("Source paths must be canonical and safe relative paths")
    try:
        path_size = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError("Source paths must contain valid Unicode text") from exc
    if path_size > 512:
        raise ValueError("Source path exceeds the byte limit")
    return path.as_posix()


def _source_file(root: Path, relative_path: str) -> Path:
    current = root
    for part in PurePosixPath(relative_path).parts:
        current = current / part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ValueError("Selected source file is unavailable") from exc
        if _is_symlink_or_reparse_point(metadata):
            raise ValueError("Selected source paths must not include symlinks")
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("Selected source path must be a regular file")
    return current


def _is_symlink_or_reparse_point(metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    return bool(reparse_point and file_attributes & reparse_point)


def _parse_unified_diff(
    patch: str,
    selected_paths: frozenset[str],
    max_lines: int,
) -> dict[
    str, tuple[tuple[int, int, int, int, tuple[tuple[str, str], ...]], ...]
]:
    lines = patch.splitlines(keepends=True)
    if len(lines) > max_lines:
        raise ValueError("Unified diff exceeds the line limit")
    index = 0
    patches: dict[
        str, tuple[tuple[int, int, int, int, tuple[tuple[str, str], ...]], ...]
    ] = {}
    while index < len(lines):
        if not lines[index].startswith("--- "):
            raise ValueError("Unified diff must contain standard file headers")
        old_match = _PATCH_PATH.fullmatch(lines[index].rstrip("\r\n"))
        if old_match is None or old_match.group(1) != "---" or old_match.group(2) != "a":
            raise ValueError("Unified diff file headers are invalid")
        old_path = _validate_relative_path(old_match.group(3))
        index += 1
        if index >= len(lines):
            raise ValueError("Unified diff is missing a new-file header")
        new_match = _PATCH_PATH.fullmatch(lines[index].rstrip("\r\n"))
        if new_match is None or new_match.group(1) != "+++" or new_match.group(2) != "b":
            raise ValueError("Unified diff file headers are invalid")
        new_path = _validate_relative_path(new_match.group(3))
        index += 1
        if old_path != new_path or old_path not in selected_paths:
            raise ValueError("Unified diff may only modify explicitly selected files")
        if old_path in patches:
            raise ValueError("Unified diff may contain only one file section per path")

        hunks: list[
            tuple[int, int, int, int, tuple[tuple[str, str], ...]]
        ] = []
        while index < len(lines) and lines[index].startswith("@@ "):
            header = _HUNK_HEADER.fullmatch(lines[index].rstrip("\r\n"))
            if header is None:
                raise ValueError("Unified diff hunk header is invalid")
            old_start = int(header.group(1))
            old_count = int(header.group(2) or "1")
            new_start = int(header.group(3))
            new_count = int(header.group(4) or "1")
            index += 1
            hunk_lines: list[tuple[str, str]] = []
            actual_old = 0
            actual_new = 0
            while index < len(lines) and lines[index][:1] in {" ", "+", "-", "\\"}:
                line = lines[index]
                prefix = line[:1]
                if prefix == "\\":
                    if line.rstrip("\r\n") != "\\ No newline at end of file":
                        raise ValueError("Unified diff contains an invalid marker")
                    if not hunk_lines:
                        raise ValueError("Unified diff newline marker has no preceding line")
                    previous_prefix, previous_text = hunk_lines[-1]
                    hunk_lines[-1] = (previous_prefix, previous_text.rstrip("\r\n"))
                    index += 1
                    continue
                if not line.endswith(("\n", "\r")):
                    raise ValueError("Unified diff line endings are invalid")
                text = line[1:]
                hunk_lines.append((prefix, text))
                actual_old += prefix in {" ", "-"}
                actual_new += prefix in {" ", "+"}
                index += 1
            if actual_old != old_count or actual_new != new_count:
                raise ValueError("Unified diff hunk counts do not match its header")
            hunk_lines_tuple = tuple(
                (prefix, text) for prefix, text in hunk_lines
            )
            hunks.append((old_start, old_count, new_start, new_count, hunk_lines_tuple))
        if not hunks:
            raise ValueError("Unified diff must contain at least one hunk")
        patches[old_path] = tuple(hunks)
    if not patches:
        raise ValueError("Unified diff is empty")
    return patches


def _apply_file_patch(
    original: bytes,
    hunks: tuple[
        tuple[int, int, int, int, tuple[tuple[str, str], ...]], ...
    ],
    max_bytes: int,
) -> bytes:
    try:
        source_text = original.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Selected source files must be UTF-8 text") from exc
    source_lines = source_text.splitlines(keepends=True)
    output: list[str] = []
    cursor = 0
    for old_start, old_count, new_start, new_count, hunk_lines in hunks:
        target = old_start if old_count == 0 else old_start - 1
        if target < cursor or target > len(source_lines):
            raise ValueError("Unified diff hunks overlap or exceed the source file")
        new_target = len(output) + target - cursor
        expected_new_start = new_target if new_count == 0 else new_target + 1
        if new_start != expected_new_start:
            raise ValueError("Unified diff hunk positions do not match")
        output.extend(source_lines[cursor:target])
        cursor = target
        for prefix, text in hunk_lines:
            if prefix in {" ", "-"}:
                if cursor >= len(source_lines) or source_lines[cursor] != text:
                    raise ValueError("Unified diff context does not match the source file")
                cursor += 1
            if prefix in {" ", "+"}:
                output.append(text)
    output.extend(source_lines[cursor:])
    result = "".join(output).encode("utf-8")
    if len(result) > max_bytes:
        raise ValueError("Patched file exceeds the byte limit")
    if result == original:
        raise ValueError("Unified diff does not change the selected files")
    return result


def _source_digest(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for path, content in sorted(files.items()):
        encoded_path = path.encode("utf-8")
        digest.update(len(encoded_path).to_bytes(4, "big"))
        digest.update(encoded_path)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()
