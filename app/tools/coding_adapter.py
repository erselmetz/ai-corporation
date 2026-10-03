"""Bounded MCP coding-tool invocation that returns patch proposals only."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from .mcp_adapter import MCPTool
from .registry import ToolRegistry

MAX_CODING_FILES = 8
MAX_CODING_FILE_BYTES = 4_096
MAX_CODING_INSTRUCTION_BYTES = 4_096
MAX_CODING_INPUT_BYTES = 16_384
MAX_CODING_PATCH_BYTES = 65_536
MAX_CODING_PATCH_LINES = 10_000

_MCP_TOOL_ID = re.compile(r"^mcp\.[A-Za-z0-9_.-]{1,64}\.[A-Za-z0-9_.-]{1,64}$")
_GIT_FILE_HEADER = re.compile(r"^diff --git a/([^\t\r\n]+) b/([^\t\r\n]+)$")
_OLD_FILE_HEADER = re.compile(r"^--- a/([^\t\r\n]+)(?:\t.*)?$")
_NEW_FILE_HEADER = re.compile(r"^\+\+\+ b/([^\t\r\n]+)(?:\t.*)?$")


class CodingToolError(Exception):
    """Base class for expected coding-tool adapter failures."""


class CodingToolRequestError(CodingToolError):
    """The bounded coding request is invalid."""


class CodingToolNotFoundError(CodingToolError):
    """The selected MCP coding tool is not registered."""


class CodingToolContractError(CodingToolError):
    """The selected MCP tool does not implement the coding proposal contract."""


class CodingToolOutputError(CodingToolError):
    """The coding tool did not return an allowed unified diff."""


@dataclass(frozen=True, slots=True)
class CodingSourceFile:
    path: str
    content: str


@dataclass(frozen=True, slots=True)
class CodingToolProposal:
    tool_id: str
    instruction: str
    file_paths: tuple[str, ...]
    source_sha256: str
    unified_diff: str
    patch_sha256: str
    created_at: datetime


class CodingToolProposalService:
    """Call one selected MCP tool with explicit file contents and retain only a diff."""

    def __init__(self, registry: ToolRegistry) -> None:
        if not isinstance(registry, ToolRegistry):
            raise TypeError("registry must be a ToolRegistry")
        self._registry = registry

    def propose(
        self,
        tool_id: str,
        instruction: str,
        source_files: tuple[CodingSourceFile, ...],
    ) -> CodingToolProposal:
        if not isinstance(tool_id, str) or not _MCP_TOOL_ID.fullmatch(tool_id):
            raise CodingToolRequestError("A registered MCP coding tool id is required")
        try:
            tool = self._registry.get(tool_id)
        except ValueError:
            raise CodingToolNotFoundError("The selected MCP coding tool is not registered") from None
        if not isinstance(tool, MCPTool):
            raise CodingToolNotFoundError("The selected MCP coding tool is not registered")
        _validate_coding_schema(tool)
        validated_files = _validate_source_files(source_files)
        if (
            not isinstance(instruction, str)
            or not instruction.strip()
            or "\x00" in instruction
            or _utf8_size(instruction) > MAX_CODING_INSTRUCTION_BYTES
        ):
            raise CodingToolRequestError("The coding instruction is empty or exceeds its limit")

        files_argument = [
            {"path": source.path, "content": source.content}
            for source in validated_files
        ]
        _encode_json(
            {"instruction": instruction, "files": files_argument},
            MAX_CODING_INPUT_BYTES,
        )
        source_digest = _source_digest(validated_files)

        patch = tool.execute(instruction=instruction, files=files_argument)
        if not isinstance(patch, str):
            raise CodingToolOutputError("The coding tool returned an unsupported result")
        _validate_patch(patch, frozenset(source.path for source in validated_files))
        patch_bytes = patch.encode("utf-8")
        if len(patch_bytes) > MAX_CODING_PATCH_BYTES:
            raise CodingToolOutputError("The coding tool patch exceeded its size limit")
        if len(patch.splitlines()) > MAX_CODING_PATCH_LINES:
            raise CodingToolOutputError("The coding tool patch exceeded its line limit")

        return CodingToolProposal(
            tool_id=tool.id,
            instruction=instruction,
            file_paths=tuple(source.path for source in validated_files),
            source_sha256=source_digest,
            unified_diff=patch,
            patch_sha256=hashlib.sha256(patch_bytes).hexdigest(),
            created_at=datetime.now(timezone.utc),
        )


def _validate_coding_schema(tool: MCPTool) -> None:
    schema = tool.input_schema
    properties = schema.get("properties")
    required = schema.get("required")
    files_schema = properties.get("files") if isinstance(properties, dict) else None
    instruction_schema = (
        properties.get("instruction") if isinstance(properties, dict) else None
    )
    file_items = files_schema.get("items") if isinstance(files_schema, dict) else None
    if (
        schema.get("type") != "object"
        or not isinstance(required, list)
        or any(not isinstance(name, str) for name in required)
        or not {"instruction", "files"}.issubset(required)
        or any(name not in {"instruction", "files"} for name in required)
        or not isinstance(instruction_schema, dict)
        or instruction_schema.get("type") != "string"
        or not isinstance(files_schema, dict)
        or files_schema.get("type") != "array"
        or not isinstance(file_items, dict)
        or file_items.get("type") != "object"
    ):
        raise CodingToolContractError(
            "The selected MCP tool must accept instruction and selected files"
        )


def _validate_source_files(
    source_files: tuple[CodingSourceFile, ...],
) -> tuple[CodingSourceFile, ...]:
    if (
        not isinstance(source_files, tuple)
        or not 1 <= len(source_files) <= MAX_CODING_FILES
        or any(not isinstance(source, CodingSourceFile) for source in source_files)
    ):
        raise CodingToolRequestError("Select an immutable bounded set of source files")
    paths: set[str] = set()
    validated: list[CodingSourceFile] = []
    for source in source_files:
        path = source.path
        content = source.content
        if (
            not isinstance(path, str)
            or not path
            or len(path) > 1_024
            or path.startswith("/")
            or "\\" in path
            or ":" in path
            or any(ord(character) < 32 for character in path)
            or any(part in {"", ".", ".."} for part in path.split("/"))
            or not isinstance(content, str)
            or "\x00" in content
        ):
            raise CodingToolRequestError("A selected source file is invalid")
        if path in paths:
            raise CodingToolRequestError("Selected source file paths must be unique")
        paths.add(path)
        content_bytes = _utf8_size(content)
        if content_bytes > MAX_CODING_FILE_BYTES:
            raise CodingToolRequestError("A selected source file exceeds its byte limit")
        validated.append(source)
    return tuple(sorted(validated, key=lambda source: source.path))


def _validate_patch(patch: str, allowed_paths: frozenset[str]) -> None:
    try:
        patch_bytes = patch.encode("utf-8")
    except UnicodeEncodeError:
        raise CodingToolOutputError("The coding tool returned an invalid patch") from None
    if (
        not patch.strip()
        or len(patch_bytes) > MAX_CODING_PATCH_BYTES
        or "\x00" in patch
    ):
        raise CodingToolOutputError("The coding tool returned an invalid patch")

    lines = patch.splitlines()
    if len(lines) > MAX_CODING_PATCH_LINES:
        raise CodingToolOutputError("The coding tool patch exceeded its line limit")
    if not patch.lstrip().startswith(("--- a/", "diff --git a/")):
        raise CodingToolOutputError("The coding tool did not return a unified diff")
    observed: set[str] = set()
    pending_git_path: str | None = None
    index = 0
    while index < len(lines):
        git_match = _GIT_FILE_HEADER.fullmatch(lines[index])
        if lines[index].startswith("diff --git "):
            if (
                git_match is None
                or pending_git_path is not None
                or git_match.group(1) != git_match.group(2)
                or git_match.group(1) not in allowed_paths
            ):
                raise CodingToolOutputError(
                    "The coding tool patch must modify only selected source files"
                )
            pending_git_path = git_match.group(1)
            index += 1
            continue
        old_match = _OLD_FILE_HEADER.fullmatch(lines[index])
        if old_match is None:
            index += 1
            continue
        if index + 1 >= len(lines):
            raise CodingToolOutputError("The coding tool patch headers are incomplete")
        new_match = _NEW_FILE_HEADER.fullmatch(lines[index + 1])
        if new_match is None:
            raise CodingToolOutputError("The coding tool patch headers are invalid")
        old_path, new_path = old_match.group(1), new_match.group(1)
        if (
            old_path != new_path
            or old_path not in allowed_paths
            or old_path in observed
            or (pending_git_path is not None and old_path != pending_git_path)
        ):
            raise CodingToolOutputError(
                "The coding tool patch must modify only selected source files"
            )
        pending_git_path = None
        observed.add(old_path)
        index += 2
        has_hunk = False
        while (
            index < len(lines)
            and _OLD_FILE_HEADER.fullmatch(lines[index]) is None
            and not lines[index].startswith("diff --git ")
        ):
            has_hunk = has_hunk or lines[index].startswith("@@ ")
            index += 1
        if not has_hunk:
            raise CodingToolOutputError("The coding tool patch contains no valid hunk")
    if not observed:
        raise CodingToolOutputError("The coding tool did not return a unified diff")
    if pending_git_path is not None:
        raise CodingToolOutputError("The coding tool patch headers are incomplete")


def _encode_json(value: object, limit: int) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, OverflowError, RecursionError):
        raise CodingToolRequestError("The coding request is invalid") from None
    if len(encoded) > limit:
        raise CodingToolRequestError("The coding request exceeded its size limit")
    return encoded


def _source_digest(source_files: tuple[CodingSourceFile, ...]) -> str:
    encoded = _encode_json(
        [
            {"path": source.path, "content": source.content}
            for source in source_files
        ],
        MAX_CODING_INPUT_BYTES,
    )
    return hashlib.sha256(encoded).hexdigest()


def _utf8_size(value: str) -> int:
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError:
        raise CodingToolRequestError("Coding request text must be valid UTF-8") from None
