import sys

import anyio
import pytest
from mcp.client.stdio import StdioServerParameters
from mcp.server import MCPServer
from mcp.types import ListToolsResult, Tool as MCPRemoteTool

from app.tools import mcp_adapter
from app.tools import (
    MCPIntegrationError,
    MCPServerConfig,
    MCPToolClient,
    MCPToolInvocationError,
    MCPToolNotFoundError,
    MCPToolPolicy,
    MCPTransportError,
    ToolRegistry,
)


def _client(
    server: MCPServer,
    allowed: frozenset[str] = frozenset({"greet"}),
    **limits: object,
) -> MCPToolClient:
    return MCPToolClient(
        MCPServerConfig("test-server", server),
        MCPToolPolicy(allowed_tools=allowed, **limits),
    )


def test_discovers_only_explicitly_allowed_tools_and_does_not_execute_them() -> None:
    server = MCPServer(name="test-server")
    calls = []

    @server.tool()
    def greet(name: str) -> str:
        calls.append(name)
        return f"hello {name}"

    @server.tool()
    def remove_file(path: str) -> str:
        return path

    registry = ToolRegistry()
    client = _client(server)

    tools = client.register_allowed_tools(registry)

    assert len(tools) == 1
    assert tools[0].id == "mcp.test-server.greet"
    assert tools[0].name == "greet"
    assert registry.get(tools[0].id) is tools[0]
    assert calls == []


def test_invokes_selected_tool_through_existing_tool_contract() -> None:
    server = MCPServer(name="test-server")

    @server.tool()
    def greet(name: str) -> str:
        return f"hello {name}"

    tool = _client(server).discover_tools()[0]

    assert tool.execute(name="Ada") == "hello Ada"


def test_missing_allowed_tool_is_distinct_and_does_not_modify_registry() -> None:
    server = MCPServer(name="test-server")
    registry = ToolRegistry()
    client = _client(server)

    with pytest.raises(MCPToolNotFoundError):
        client.register_allowed_tools(registry)

    assert registry.all() == []


def test_discovers_allowlisted_tools_across_bounded_pages(monkeypatch) -> None:
    cursors = []
    pages = {
        None: ListToolsResult(
            tools=[
                MCPRemoteTool(
                    name="not_allowed",
                    input_schema={"type": "object"},
                )
            ],
            next_cursor="page-2",
        ),
        "page-2": ListToolsResult(
            tools=[
                MCPRemoteTool(
                    name="greet",
                    input_schema={"type": "object"},
                )
            ]
        ),
    }

    class PagedClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            pass

        async def list_tools(self, *, cursor=None):
            cursors.append(cursor)
            return pages[cursor]

    monkeypatch.setattr(mcp_adapter, "Client", PagedClient)
    client = _client(MCPServer(name="test-server"))

    tools = client.discover_tools()

    assert [tool.name for tool in tools] == ["greet"]
    assert cursors == [None, "page-2"]


def test_repeated_mcp_pagination_cursor_fails_without_looping(monkeypatch) -> None:
    class RepeatingClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            pass

        async def list_tools(self, *, cursor=None):
            return ListToolsResult(tools=[], next_cursor="repeat")

    monkeypatch.setattr(mcp_adapter, "Client", RepeatingClient)
    client = _client(MCPServer(name="test-server"))

    with pytest.raises(MCPIntegrationError, match="pagination is invalid"):
        client.discover_tools()


def test_remote_tool_errors_are_sanitized() -> None:
    server = MCPServer(name="test-server")

    @server.tool()
    def fail() -> str:
        raise RuntimeError("credential=secret-token")

    tool = _client(server, frozenset({"fail"})).discover_tools()[0]

    with pytest.raises(MCPToolInvocationError) as error:
        tool.execute()

    assert "secret-token" not in str(error.value)
    assert "credential" not in str(error.value)


def test_tool_arguments_are_bounded_before_the_call() -> None:
    server = MCPServer(name="test-server")
    calls = []

    @server.tool()
    def greet(name: str) -> str:
        calls.append(name)
        return "hello"

    tool = _client(server, max_input_bytes=8).discover_tools()[0]

    with pytest.raises(MCPIntegrationError):
        tool.execute(name="a name that is too long")

    assert calls == []


def test_tool_results_are_bounded() -> None:
    server = MCPServer(name="test-server")

    @server.tool()
    def greet() -> str:
        return "response too large"

    tool = _client(server, max_output_bytes=4).discover_tools()[0]

    with pytest.raises(MCPIntegrationError, match="output limit"):
        tool.execute()


def test_timeout_is_enforced_and_sanitized() -> None:
    server = MCPServer(name="test-server")

    @server.tool()
    async def slow() -> str:
        await anyio.sleep(1)
        return "done"

    tool = _client(server, frozenset({"slow"}), timeout_seconds=0.05).discover_tools()[0]

    with pytest.raises(MCPTransportError, match="MCP server request failed"):
        tool.execute()


def test_synchronous_tool_fails_explicitly_inside_async_context() -> None:
    server = MCPServer(name="test-server")

    @server.tool()
    def greet() -> str:
        return "hello"

    tool = _client(server).discover_tools()[0]

    async def invoke() -> None:
        with pytest.raises(MCPIntegrationError, match="active event loop"):
            tool.execute()

    anyio.run(invoke)


def test_stdio_custom_environment_is_rejected() -> None:
    server = StdioServerParameters(command="python", env={"API_TOKEN": "secret"})

    with pytest.raises(ValueError, match="Custom MCP server environments"):
        MCPServerConfig("test-server", server)


def test_unavailable_stdio_server_errors_are_sanitized() -> None:
    server = StdioServerParameters(command="mcp-command-that-does-not-exist")
    client = MCPToolClient(
        MCPServerConfig("test-server", server),
        MCPToolPolicy(frozenset({"greet"})),
    )

    with pytest.raises(MCPTransportError) as error:
        client.discover_tools()

    assert "mcp-command-that-does-not-exist" not in str(error.value)


def test_stdio_server_can_serve_an_explicitly_selected_tool(tmp_path) -> None:
    server_script = tmp_path / "mcp_server.py"
    server_script.write_text(
        "from mcp.server import MCPServer\n"
        "server = MCPServer(name='stdio-test')\n"
        "@server.tool()\n"
        "def greet(name: str) -> str:\n"
        "    return f'hello {name}'\n"
        "server.run()\n",
        encoding="utf-8",
    )
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(server_script)],
    )
    config = MCPServerConfig("stdio-test", server)
    server.args.append("argument-added-after-validation")
    server.env = {"API_TOKEN": "must-not-be-forwarded"}
    client = MCPToolClient(
        config,
        MCPToolPolicy(frozenset({"greet"})),
    )

    tool = client.discover_tools()[0]

    assert tool.execute(name="Ada") == "hello Ada"


def test_invalid_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="frozen tool allowlist"):
        MCPToolPolicy(allowed_tools={"greet"})  # type: ignore[arg-type]


def test_registry_conflict_does_not_partially_register_selected_tools() -> None:
    server = MCPServer(name="test-server")

    @server.tool()
    def greet() -> str:
        return "hello"

    @server.tool()
    def farewell() -> str:
        return "goodbye"

    client = _client(server, frozenset({"greet", "farewell"}))
    registry = ToolRegistry()
    registry.register(client.discover_tools()[0])
    before = registry.all()

    with pytest.raises(ValueError, match="already registered"):
        client.register_allowed_tools(registry)

    assert registry.all() == before


def test_tool_failure_exposes_no_server_exception_details() -> None:
    server = MCPServer(name="test-server")

    @server.tool()
    def broken() -> str:
        raise ValueError("C:\\Users\\someone\\private.txt")

    tool = _client(server, frozenset({"broken"})).discover_tools()[0]

    with pytest.raises(MCPToolInvocationError) as error:
        tool.execute()

    assert "private.txt" not in str(error.value)
