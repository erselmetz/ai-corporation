from unittest.mock import MagicMock

import pytest

from app.agent_runtime import (
    AgentRuntime, AgentRuntimeApprovalRequired, AgentRuntimeBudgetExceeded, AgentRuntimeError,
    AgentRuntimeStopped, RuntimeLimits, current_invocation,
    runtime_output_token_budget, runtime_timeout_seconds,
)
from app.agents import Agent, AgentRegistry
from app.orchestrator import Orchestrator
from app.providers import AIProvider, ProviderRegistry
from app.tools import Tool, ToolRegistry


class RuntimeProvider(AIProvider):
    def __init__(self):
        self.calls = []
        self.supports_streaming = True

    def generate(self, model, prompt):
        raise AssertionError("chat must use generate_chat")

    def generate_chat(self, model, messages):
        self.calls.append((model, messages, current_invocation()))
        return "A concise answer."

    def generate_chat_stream(self, model, messages):
        for value in ("A concise ", "answer."):
            self.calls.append((model, messages, current_invocation()))
            yield value


class CounterTool(Tool):
    def __init__(self, risk="read"):
        super().__init__("counter", "Counter", "Return a bounded count.", risk_class=risk,
                         input_schema={"type": "object", "properties": {
                             "count": {"type": "integer", "minimum": 0, "maximum": 10}},
                             "required": ["count"], "additionalProperties": False})
        self.calls = 0

    def execute(self, **kwargs):
        self.calls += 1
        return str(kwargs["count"])


def _orchestrator():
    agents = AgentRegistry()
    agents.register(Agent("agent_one", "One", "Assistant", "local", "model"))
    providers = ProviderRegistry()
    provider = RuntimeProvider()
    providers.register("local", provider)
    return Orchestrator(agents, providers, MagicMock(), MagicMock()), provider


def test_orchestrator_chat_and_stream_share_bounded_runtime_context():
    orchestrator, provider = _orchestrator()
    messages = [{"role": "system", "content": "Be helpful."},
                {"role": "user", "content": "hello"}]
    assert orchestrator.run_agent_chat("agent_one", messages) == "A concise answer."
    runtime = orchestrator.agent_runtime.last_trace()
    assert runtime["outcome"] == "completed"
    assert [step["step"] for step in runtime["steps"]] == ["classify", "plan", "answer"]
    assert orchestrator.agent_runtime.take_trace() == runtime
    assert orchestrator.agent_runtime.last_trace() is None
    assert provider.calls[-1][2] is not None
    assert provider.calls[-1][2].output_token_budget <= runtime["token_budget"]
    chunks = list(orchestrator.stream_agent_chat("agent_one", messages))
    assert chunks == ["A concise ", "answer."]
    assert all(call[2] is not None for call in provider.calls[-2:])
    assert orchestrator.agent_runtime.last_trace()["outcome"] == "completed"


def test_runtime_limits_are_bounded_and_stop_fails_closed_before_provider_call():
    with pytest.raises(ValueError):
        RuntimeLimits(max_steps=6)
    stopped = True
    runtime = AgentRuntime(stop_check=lambda: stopped)
    called = False

    def operation():
        nonlocal called
        called = True
        return "should not run"

    with pytest.raises(AgentRuntimeStopped):
        runtime.run_direct("agent_one", operation)
    assert called is False
    assert runtime.last_trace()["outcome"] == "stopped"


def test_runtime_stream_checks_stop_between_chunks_and_does_not_retry():
    stopped = False
    runtime = AgentRuntime(stop_check=lambda: stopped)

    def operation():
        yield "first"
        nonlocal stopped
        stopped = True
        yield "second"

    iterator = runtime.stream_direct("agent_one", operation)
    assert next(iterator) == "first"
    with pytest.raises(AgentRuntimeStopped):
        next(iterator)
    assert runtime.last_trace()["outcome"] == "stopped"


def test_tool_schema_preview_risk_and_read_only_execution_fail_closed():
    registry = ToolRegistry()
    read_tool = CounterTool()
    registry.register(read_tool)
    description = registry.describe("counter")
    assert description["risk_class"] == "read"
    assert description["supports_dry_run"] is True
    assert description["supports_undo"] is False
    assert registry.preview("counter", {"count": 2})["risk_class"] == "read"
    assert read_tool.calls == 0
    assert read_tool.dry_run({"count": 2})["executed"] is False

    runtime = AgentRuntime()
    assert runtime.run_direct("agent_one", lambda: runtime.invoke_tool(
        registry, "counter", {"count": 2}, allow_read=True)) == "2"
    assert read_tool.calls == 1
    assert runtime.last_trace()["steps"][-2]["step"] == "counter"
    with pytest.raises(ValueError, match="schema"):
        registry.validate_arguments("counter", {"count": 2, "extra": "x"})
    with pytest.raises(ValueError, match="schema"):
        registry.validate_arguments("counter", {"count": 2, "api_key": "hidden"})


def test_unknown_and_non_read_tool_risks_are_control_and_require_approval():
    registry = ToolRegistry()
    unknown = CounterTool(risk=["unknown"])
    registry.register(unknown)
    assert registry.risk_class("counter") == "control"
    runtime = AgentRuntime()
    with pytest.raises(AgentRuntimeApprovalRequired) as raised:
        runtime.run_direct("agent_one", lambda: runtime.invoke_tool(
            registry, "counter", {"count": 1}))
    assert raised.value.risk_class == "control"
    assert unknown.calls == 0


def test_runtime_provider_budgets_are_exposed_only_during_an_invocation():
    assert current_invocation() is None
    runtime = AgentRuntime(limits=RuntimeLimits(step_token_budget=123))
    observed = runtime.run_direct("agent_one", lambda: (
        runtime_output_token_budget(), runtime_timeout_seconds()))
    assert observed[0] == 123
    assert 0 < observed[1] <= 30
    assert current_invocation() is None


def test_agentic_runtime_validates_tool_decisions_and_records_untrusted_observation():
    registry = ToolRegistry()
    tool = CounterTool()
    registry.register(tool)
    runtime = AgentRuntime()
    seen = []

    def planner(observations):
        seen.append(observations)
        if not observations:
            assert runtime_output_token_budget() > 0
            return {"type": "tool", "tool_id": "counter", "arguments": {"count": 3}}
        assert observations[0]["untrusted"] is True
        return {"type": "answer", "text": "It is three."}

    assert runtime.run_agentic("agent_one", planner, registry, allow_read_tools=True) == "It is three."
    trace = runtime.last_trace()
    assert trace["outcome"] == "completed"
    assert [step["step"] for step in trace["steps"]] == [
        "classify_plan", "decide", "counter", "observe", "answer"]
    assert tool.calls == 1
    assert seen[1][0] == {"tool_id": "counter", "result": "3", "untrusted": True}


def test_agentic_runtime_denies_non_read_actions_without_approval_and_never_repairs_output():
    registry = ToolRegistry()
    tool = CounterTool(risk="external")
    registry.register(tool)
    runtime = AgentRuntime()
    calls = 0

    def planner(_observations):
        nonlocal calls
        calls += 1
        return {"type": "tool", "tool_id": "counter", "arguments": {"count": 2}}

    with pytest.raises(AgentRuntimeApprovalRequired) as raised:
        runtime.run_agentic("agent_one", planner, registry, allow_read_tools=True)
    assert raised.value.risk_class == "external"
    assert tool.calls == 0
    assert calls == 1

    calls = 0

    def malformed(_observations):
        nonlocal calls
        calls += 1
        return {"type": "tool", "tool_id": "counter", "arguments": {}, "extra": "retry"}

    with pytest.raises(AgentRuntimeError, match="unsupported structured decision"):
        runtime.run_agentic("agent_one", malformed, registry)
    assert calls == 1
    assert tool.calls == 0
