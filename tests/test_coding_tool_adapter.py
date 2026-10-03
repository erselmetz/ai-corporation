from __future__ import annotations

from collections.abc import Callable

import pytest
from mcp.server import MCPServer

from app.tools import (
    CodingSourceFile,
    CodingToolContractError,
    CodingToolNotFoundError,
    CodingToolOutputError,
    CodingToolProposalService,
    CodingToolRequestError,
    MCPServerConfig,
    MCPTool,
    MCPToolClient,
    MCPToolPolicy,
    Tool,
    ToolRegistry,
)

_PATCH = (
    "--- a/src/main.py\n"
    "+++ b/src/main.py\n"
    "@@ -1 +1 @@\n"
    "-print('old')\n"
    "+print('new')\n"
)


def _coding_registry(
    result_factory: Callable[[str, list[dict[str, str]]], str],
    *,
    max_output_bytes: int = 65_536,
) -> tuple[ToolRegistry, list[tuple[str, list[dict[str, str]]]]]:
    server = MCPServer(name="coding")
    calls: list[tuple[str, list[dict[str, str]]]] = []

    @server.tool()
    def propose(instruction: str, files: list[dict[str, str]]) -> str:
        calls.append((instruction, files))
        return result_factory(instruction, files)

    registry = ToolRegistry()
    client = MCPToolClient(
        MCPServerConfig("coding", server),
        MCPToolPolicy(
            allowed_tools=frozenset({"propose"}),
            max_output_bytes=max_output_bytes,
        ),
    )
    client.register_allowed_tools(registry)
    return registry, calls


def test_selected_mcp_coding_tool_returns_bounded_reviewable_diff_only() -> None:
    registry, calls = _coding_registry(lambda _instruction, _files: _PATCH)
    source_files = (
        CodingSourceFile("src/z.py", "print('z')\n"),
        CodingSourceFile("src/main.py", "print('old')\n"),
    )

    proposal = CodingToolProposalService(registry).propose(
        "mcp.coding.propose",
        "Change the output",
        source_files,
    )

    assert proposal.tool_id == "mcp.coding.propose"
    assert proposal.instruction == "Change the output"
    assert proposal.file_paths == ("src/main.py", "src/z.py")
    assert proposal.unified_diff == _PATCH
    assert len(proposal.patch_sha256) == 64
    assert len(proposal.source_sha256) == 64
    assert proposal.created_at.tzinfo is not None
    assert calls == [
        (
            "Change the output",
            [
                {"path": "src/main.py", "content": "print('old')\n"},
                {"path": "src/z.py", "content": "print('z')\n"},
            ],
        )
    ]
    assert not hasattr(proposal, "source_contents")


def test_unregistered_or_non_mcp_tools_are_rejected() -> None:
    registry = ToolRegistry()
    service = CodingToolProposalService(registry)
    files = (CodingSourceFile("main.py", "value = 1\n"),)

    with pytest.raises(CodingToolNotFoundError):
        service.propose("mcp.missing.propose", "Update value", files)

    class LocalTool(Tool):
        def __init__(self) -> None:
            super().__init__("mcp.fake.propose", "fake", "not an MCP tool")

        def execute(self, **kwargs: object) -> str:
            del kwargs
            return _PATCH

    registry.register(LocalTool())
    with pytest.raises(CodingToolNotFoundError):
        service.propose("mcp.fake.propose", "Update value", files)


def test_tool_must_declare_the_instruction_and_file_input_contract() -> None:
    server = MCPServer(name="coding")

    @server.tool()
    def unrelated(command: str) -> str:
        return command

    registry = ToolRegistry()
    MCPToolClient(
        MCPServerConfig("coding", server),
        MCPToolPolicy(allowed_tools=frozenset({"unrelated"})),
    ).register_allowed_tools(registry)

    with pytest.raises(CodingToolContractError):
        CodingToolProposalService(registry).propose(
            "mcp.coding.unrelated",
            "Update value",
            (CodingSourceFile("main.py", "value = 1\n"),),
        )


@pytest.mark.parametrize(
    ("source_files", "instruction"),
    [
        ((CodingSourceFile("../outside.py", "value = 1\n"),), "Update value"),
        ((CodingSourceFile("main.py", "value = 1\n"),) * 2, "Update value"),
        ((CodingSourceFile("main.py", "x" * 4_097),), "Update value"),
        ((CodingSourceFile("main.py", "value = 1\n"),), "x" * 4_097),
        (
            tuple(CodingSourceFile(f"f{number}.py", "x" * 4_000) for number in range(5)),
            "Update value",
        ),
    ],
)
def test_invalid_or_oversized_requests_do_not_invoke_the_tool(
    source_files: tuple[CodingSourceFile, ...],
    instruction: str,
) -> None:
    registry, calls = _coding_registry(lambda _instruction, _files: _PATCH)

    with pytest.raises(CodingToolRequestError):
        CodingToolProposalService(registry).propose(
            "mcp.coding.propose",
            instruction,
            source_files,
        )

    assert calls == []


@pytest.mark.parametrize(
    "patch",
    [
        "not a unified diff",
        "--- a/src/main.py\n+++ b/src/main.py\n-no hunk\n",
        (
            "--- a/src/main.py\n"
            "+++ b/src/main.py\n"
            "@@ -1 +1 @@\n"
            "-old\n+new\n"
            "--- a/other.py\n"
            "+++ b/other.py\n"
            "@@ -1 +1 @@\n"
            "-old\n+new\n"
        ),
        (
            "--- a/../outside.py\n"
            "+++ b/../outside.py\n"
            "@@ -1 +1 @@\n"
            "-old\n+new\n"
        ),
        (
            "diff --git a/other.py b/other.py\n"
            "--- a/src/main.py\n"
            "+++ b/src/main.py\n"
            "@@ -1 +1 @@\n"
            "-old\n+new\n"
        ),
    ],
)
def test_tool_output_must_be_a_diff_for_only_selected_files(patch: str) -> None:
    registry, calls = _coding_registry(lambda _instruction, _files: patch)

    with pytest.raises(CodingToolOutputError):
        CodingToolProposalService(registry).propose(
            "mcp.coding.propose",
            "Update value",
            (CodingSourceFile("src/main.py", "value = 1\n"),),
        )

    assert len(calls) == 1


def test_oversized_patch_output_is_rejected() -> None:
    registry, calls = _coding_registry(
        lambda _instruction, _files: _PATCH + ("x" * 65_536),
        max_output_bytes=262_144,
    )

    with pytest.raises(CodingToolOutputError):
        CodingToolProposalService(registry).propose(
            "mcp.coding.propose",
            "Update value",
            (CodingSourceFile("src/main.py", "value = 1\n"),),
        )

    assert len(calls) == 1
