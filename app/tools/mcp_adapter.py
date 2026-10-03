"""Explicit, bounded MCP client integration for the existing Tool contract."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, TypeVar

import anyio
from mcp import Client
from mcp.client import InputRequiredRoundsExceededError
from mcp.client.stdio import StdioServerParameters
from mcp.server import MCPServer
from mcp.shared.exceptions import MCPError
from mcp.types import Tool as MCPRemoteTool
from pydantic import ValidationError

from .base import Tool
from .registry import ToolRegistry

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_MAX_SERVER_TOOLS = 64
_MAX_ALLOWED_TOOLS = 32
_MAX_DESCRIPTION_BYTES = 2_048
_MAX_SCHEMA_BYTES = 16_384
_MAX_COMMAND_BYTES = 256
_MAX_ARGUMENT_BYTES = 4_096
_T = TypeVar("_T")


class MCPIntegrationError(RuntimeError):
    """Base error for the bounded MCP tool integration."""


class MCPTransportError(MCPIntegrationError):
    """An MCP server could not be reached or did not complete a request."""


class MCPToolNotFoundError(MCPIntegrationError):
    """An explicitly allowed tool was not advertised by the MCP server."""


class MCPToolInvocationError(MCPIntegrationError):
    """An MCP tool call failed or returned an unsupported result."""


@dataclass(frozen=True, slots=True)
class _MCPStdioConfig:
    command: str
    args: tuple[str, ...]
    cwd: str | Path | None
    encoding: str
    encoding_error_handler: str

    def to_parameters(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=self.command,
            args=list(self.args),
            cwd=self.cwd,
            encoding=self.encoding,
            encoding_error_handler=self.encoding_error_handler,
        )


@dataclass(frozen=True, slots=True)
class MCPServerConfig:
    """A trusted in-process MCP server or a local stdio server without custom env."""

    server_id: str
    server: MCPServer | StdioServerParameters | _MCPStdioConfig

    def __post_init__(self) -> None:
        if not isinstance(self.server_id, str) or not _IDENTIFIER.fullmatch(self.server_id):
            raise ValueError("MCP server id must be a short identifier")
        if isinstance(self.server, StdioServerParameters):
            if self.server.env is not None:
                raise ValueError("Custom MCP server environments are not supported")
            command = self.server.command
            arguments = self.server.args
            if (
                not isinstance(command, str)
                or not command.strip()
                or "\x00" in command
                or len(command.encode("utf-8")) > _MAX_COMMAND_BYTES
            ):
                raise ValueError("MCP server command is invalid")
            if (
                not isinstance(arguments, list)
                or len(arguments) > 32
                or any(not isinstance(argument, str) or "\x00" in argument for argument in arguments)
                or sum(len(argument.encode("utf-8")) for argument in arguments) > _MAX_ARGUMENT_BYTES
            ):
                raise ValueError("MCP server arguments are invalid")
            object.__setattr__(
                self,
                "server",
                _MCPStdioConfig(
                    command=command,
                    args=tuple(arguments),
                    cwd=self.server.cwd,
                    encoding=self.server.encoding,
                    encoding_error_handler=self.server.encoding_error_handler,
                ),
            )
        elif not isinstance(self.server, (_MCPStdioConfig, MCPServer)):
            raise TypeError("MCP server must use local stdio or an in-process MCP server")

    def _client_server(self) -> MCPServer | StdioServerParameters:
        if isinstance(self.server, _MCPStdioConfig):
            return self.server.to_parameters()
        return self.server


@dataclass(frozen=True, slots=True)
class MCPToolPolicy:
    """Immutable allowlist and resource bounds applied to MCP tool calls."""

    allowed_tools: frozenset[str]
    timeout_seconds: float = 10.0
    max_input_bytes: int = 16_384
    max_output_bytes: int = 65_536

    def __post_init__(self) -> None:
        if not isinstance(self.allowed_tools, frozenset) or not self.allowed_tools:
            raise ValueError("MCP policy requires a non-empty frozen tool allowlist")
        if len(self.allowed_tools) > _MAX_ALLOWED_TOOLS or any(
            not isinstance(name, str) or not _IDENTIFIER.fullmatch(name)
            for name in self.allowed_tools
        ):
            raise ValueError("MCP tool allowlist contains an invalid or excessive name")
        if (
            isinstance(self.timeout_seconds, bool)
            or not isinstance(self.timeout_seconds, (int, float))
            or not 0 < self.timeout_seconds <= 30
        ):
            raise ValueError("MCP timeout must be greater than zero and at most 30 seconds")
        if (
            isinstance(self.max_input_bytes, bool)
            or not isinstance(self.max_input_bytes, int)
            or not 1 <= self.max_input_bytes <= 65_536
            or isinstance(self.max_output_bytes, bool)
            or not isinstance(self.max_output_bytes, int)
            or not 1 <= self.max_output_bytes <= 262_144
        ):
            raise ValueError("MCP input and output limits are invalid")


class MCPToolClient:
    """Discovers, explicitly registers, and invokes allowlisted MCP tools."""

    def __init__(self, server: MCPServerConfig, policy: MCPToolPolicy) -> None:
        if not isinstance(server, MCPServerConfig):
            raise TypeError("server must be an MCPServerConfig")
        if not isinstance(policy, MCPToolPolicy):
            raise TypeError("policy must be an MCPToolPolicy")
        self._server = server
        self._policy = policy

    def discover_tools(self) -> tuple[Tool, ...]:
        """Connect once and return only tools named in the explicit allowlist."""
        remote_tools = self._run_sync(self._discover_remote_tools)
        if len(remote_tools) > _MAX_SERVER_TOOLS:
            raise MCPIntegrationError("MCP server advertised too many tools")

        selected: dict[str, Any] = {}
        for remote_tool in remote_tools:
            name = getattr(remote_tool, "name", None)
            if isinstance(name, str) and name in self._policy.allowed_tools:
                if not _IDENTIFIER.fullmatch(name) or name in selected:
                    raise MCPIntegrationError("MCP server advertised invalid tool metadata")
                selected[name] = remote_tool

        missing = self._policy.allowed_tools.difference(selected)
        if missing:
            raise MCPToolNotFoundError("An allowed MCP tool is not available")

        tools = []
        for name in sorted(self._policy.allowed_tools):
            remote_tool = selected[name]
            input_schema = getattr(remote_tool, "input_schema", None)
            if not isinstance(input_schema, dict):
                raise MCPIntegrationError("MCP server advertised an invalid input schema")
            schema = _bounded_json(
                input_schema,
                _MAX_SCHEMA_BYTES,
                "MCP server advertised an invalid input schema",
            )
            description = getattr(remote_tool, "description", None)
            if not isinstance(description, str) or not description.strip():
                description = f"Tool supplied by MCP server {self._server.server_id}"
            description = _bounded_text(
                description,
                _MAX_DESCRIPTION_BYTES,
                "MCP server advertised an invalid description",
            )
            title = getattr(remote_tool, "title", None)
            if not isinstance(title, str) or not title.strip():
                title = name
            title = _bounded_text(title, _MAX_DESCRIPTION_BYTES, "MCP server advertised invalid metadata")
            tools.append(
                MCPTool(
                    client=self,
                    server_id=self._server.server_id,
                    remote_name=name,
                    title=title,
                    description=description,
                    input_schema=json.loads(schema),
                )
            )
        return tuple(tools)

    def register_allowed_tools(self, registry: ToolRegistry) -> tuple[Tool, ...]:
        """Explicitly register all selected tools, rejecting conflicts before mutation."""
        if not isinstance(registry, ToolRegistry):
            raise TypeError("registry must be a ToolRegistry")
        tools = self.discover_tools()
        if any(registry.exists(tool.id) for tool in tools):
            raise ValueError("An MCP tool id is already registered")
        for tool in tools:
            registry.register(tool)
        return tools

    async def _discover_remote_tools(self) -> list[MCPRemoteTool]:
        try:
            with anyio.fail_after(self._policy.timeout_seconds):
                async with Client(
                    self._server._client_server(),
                    read_timeout_seconds=self._policy.timeout_seconds,
                    input_required_max_rounds=0,
                ) as client:
                    tools: list[MCPRemoteTool] = []
                    cursor: str | None = None
                    seen_cursors: set[str] = set()
                    while True:
                        page = await client.list_tools(cursor=cursor)
                        if len(tools) + len(page.tools) > _MAX_SERVER_TOOLS:
                            raise MCPIntegrationError("MCP server advertised too many tools")
                        tools.extend(page.tools)
                        cursor = page.next_cursor
                        if cursor is None:
                            return tools
                        if (
                            not cursor
                            or len(cursor) > 1_024
                            or cursor in seen_cursors
                            or len(seen_cursors) >= _MAX_SERVER_TOOLS
                        ):
                            raise MCPIntegrationError("MCP server pagination is invalid")
                        seen_cursors.add(cursor)
        except (
            MCPError,
            ValidationError,
            OSError,
            TimeoutError,
            anyio.BrokenResourceError,
            anyio.ClosedResourceError,
            anyio.EndOfStream,
        ):
            raise MCPTransportError("MCP server request failed") from None

    async def _invoke_remote_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if name not in self._policy.allowed_tools:
            raise MCPToolInvocationError("MCP tool is not allowed by policy")
        try:
            with anyio.fail_after(self._policy.timeout_seconds):
                async with Client(
                    self._server._client_server(),
                    read_timeout_seconds=self._policy.timeout_seconds,
                    input_required_max_rounds=0,
                ) as client:
                    result = await client.call_tool(
                        name,
                        arguments,
                        read_timeout_seconds=self._policy.timeout_seconds,
                    )
        except InputRequiredRoundsExceededError:
            raise MCPToolInvocationError("MCP tool requires unsupported interactive input") from None
        except (
            MCPError,
            ValidationError,
            OSError,
            TimeoutError,
            anyio.BrokenResourceError,
            anyio.ClosedResourceError,
            anyio.EndOfStream,
        ):
            raise MCPTransportError("MCP server request failed") from None

        if result.is_error:
            raise MCPToolInvocationError("MCP tool reported an error")
        if result.content and all(getattr(block, "type", None) == "text" for block in result.content):
            parts = []
            output_bytes = 0
            for block in result.content:
                separator_bytes = 1 if parts else 0
                if len(block.text) > self._policy.max_output_bytes - output_bytes - separator_bytes:
                    raise MCPIntegrationError("MCP tool result exceeded the output limit")
                try:
                    part_bytes = len(block.text.encode("utf-8"))
                except UnicodeEncodeError:
                    raise MCPToolInvocationError("MCP tool returned invalid text") from None
                output_bytes += separator_bytes + part_bytes
                if output_bytes > self._policy.max_output_bytes:
                    raise MCPIntegrationError("MCP tool result exceeded the output limit")
                parts.append(block.text)
            return "\n".join(parts)
        if result.structured_content is not None:
            return _bounded_json(
                result.structured_content,
                self._policy.max_output_bytes,
                "MCP tool result exceeded the output limit or was not valid JSON",
            )
        raise MCPToolInvocationError("MCP tool returned an unsupported result format")

    @staticmethod
    def _run_sync(operation: Callable[[], Awaitable[_T]]) -> _T:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return anyio.run(operation)
        raise MCPIntegrationError(
            "The synchronous MCP tool interface cannot run inside an active event loop"
        )


class MCPTool(Tool):
    def __init__(
        self,
        client: MCPToolClient,
        server_id: str,
        remote_name: str,
        title: str,
        description: str,
        input_schema: dict[str, Any],
    ) -> None:
        super().__init__(f"mcp.{server_id}.{remote_name}", title, description)
        self._client = client
        self._remote_name = remote_name
        self.input_schema = input_schema

    def execute(self, **kwargs: Any) -> str:
        _bounded_json(
            kwargs,
            self._client._policy.max_input_bytes,
            "MCP tool arguments exceeded the input limit or were not valid JSON",
        )
        return self._client._run_sync(
            lambda: self._client._invoke_remote_tool(self._remote_name, kwargs)
        )


def _bounded_json(value: Any, limit: int, message: str) -> str:
    try:
        encoder = json.JSONEncoder(
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        chunks = []
        size = 0
        for chunk in encoder.iterencode(value):
            if len(chunk) > limit - size:
                raise MCPIntegrationError(message)
            size += len(chunk.encode("utf-8"))
            if size > limit:
                raise MCPIntegrationError(message)
            chunks.append(chunk)
    except (TypeError, ValueError, UnicodeEncodeError, OverflowError, RecursionError):
        raise MCPIntegrationError(message) from None
    return "".join(chunks)


def _bounded_text(value: str, limit: int, message: str) -> str:
    try:
        size = len(value.encode("utf-8"))
    except UnicodeEncodeError:
        raise MCPIntegrationError(message) from None
    if size > limit:
        raise MCPIntegrationError(message)
    return value
