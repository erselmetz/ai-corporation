"""Bounded, synchronous execution context shared by Agent chat entry points.

Runtime records contain operation metadata only; prompts, tool arguments and
provider responses are never retained here.
"""
from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Callable
from uuid import uuid4


class AgentRuntimeError(RuntimeError):
    pass


class AgentRuntimeStopped(AgentRuntimeError):
    pass


class AgentRuntimeBudgetExceeded(AgentRuntimeError):
    pass


class AgentRuntimeApprovalRequired(AgentRuntimeError):
    def __init__(self, tool_id: str, risk_class: str, preview: dict):
        super().__init__("This Agent action needs explicit owner approval")
        self.tool_id = tool_id
        self.risk_class = risk_class
        self.preview = preview


@dataclass(frozen=True, slots=True)
class RuntimeLimits:
    max_steps: int = 5
    total_timeout_seconds: float = 90.0
    step_timeout_seconds: float = 30.0
    token_budget: int = 2048
    step_token_budget: int = 512

    def __post_init__(self):
        if (type(self.max_steps) is not int or not 1 <= self.max_steps <= 5
                or type(self.token_budget) is not int or not 1 <= self.token_budget <= 8192
                or type(self.step_token_budget) is not int or not 1 <= self.step_token_budget <= self.token_budget
                or not 0 < self.step_timeout_seconds <= 120
                or not self.step_timeout_seconds <= self.total_timeout_seconds <= 300):
            raise ValueError("Agent Runtime limits are outside supported bounds")


@dataclass(frozen=True, slots=True)
class RuntimeInvocation:
    deadline: float
    step_deadline: float
    output_token_budget: int
    stop_check: Callable[[], bool]


_CURRENT_INVOCATION: ContextVar[RuntimeInvocation | None] = ContextVar(
    "ersel_agent_runtime_invocation", default=None)
_CURRENT_TRACE: ContextVar[dict | None] = ContextVar("ersel_agent_runtime_trace", default=None)


def current_invocation() -> RuntimeInvocation | None:
    return _CURRENT_INVOCATION.get()


def runtime_output_token_budget(default: int = 1024) -> int:
    invocation = current_invocation()
    return invocation.output_token_budget if invocation else default


def runtime_timeout_seconds(default: float = 120.0) -> float:
    invocation = current_invocation()
    if invocation is None:
        return default
    return max(0.05, min(default, invocation.step_deadline - monotonic()))


def _step_seconds(limits):
    """Authorized native local-only override; total turn and token caps remain."""
    from app.resources.context import native_model_seconds,native_scope,resource_lease,application_service
    requested=native_model_seconds.get();parent=resource_lease.get();service=application_service.get()
    if requested in {30,60,90} and native_scope.get() is not None and parent is not None and service is not None:
        route=next((a for a in parent[0].snapshot().allocations if a.id==parent[1]),None)
        if route is not None and route.provider_id=='ollama' and service.provider_is_local('ollama'):
            return min(float(requested),limits.total_timeout_seconds)
    return limits.step_timeout_seconds


def check_runtime_step() -> None:
    from app.resources.context import native_scope
    scope=native_scope.get()
    from app.resources.context import request_stop
    stop=request_stop.get()
    if (scope is not None and scope.cancelled) or (stop is not None and stop.is_set()):raise AgentRuntimeStopped('This request was stopped by the owner')
    invocation = current_invocation()
    if invocation is None:
        return
    if invocation.stop_check():
        raise AgentRuntimeStopped("Agent Runtime stopped by the owner")
    now = monotonic()
    if now >= invocation.step_deadline or now >= invocation.deadline:
        raise AgentRuntimeBudgetExceeded("Agent Runtime step timed out")


class AgentRuntime:
    """A single bounded execution boundary for all Orchestrator chat calls."""

    def __init__(self, *, limits: RuntimeLimits | None = None,
                 stop_check: Callable[[], bool] | None = None,
                 clock: Callable[[], float] = monotonic):
        self.limits = limits or RuntimeLimits()
        self._stop_check = stop_check or (lambda: False)
        self._clock = clock
        self._lock = RLock()
        self._active: set[str] = set()

    def set_stop_check(self, stop_check: Callable[[], bool]) -> None:
        if not callable(stop_check):
            raise TypeError("stop_check must be callable")
        with self._lock:
            self._stop_check = stop_check

    def invoke_tool(self, registry, tool_id: str, arguments: dict, *, allow_read: bool = False,
                    autonomy_level: str | None = None,
                    progress: Callable[[str], None] | None = None):
        """Validate a registered tool and auto-run only explicitly read-only tools.

        Approval integration is intentionally deferred to the autonomy phase;
        any non-read risk is returned as a preview and is never executed here.
        """
        self.assert_available()
        try:
            risk = registry.risk_class(tool_id)
            validated = registry.validate_arguments(tool_id, arguments)
            preview = registry.preview(tool_id, validated)
            tool = registry.get(tool_id)
        except Exception:
            raise AgentRuntimeError("Tool is not registered or its request failed validation") from None
        if autonomy_level is not None and autonomy_level not in {
                "chat_only", "auto_safe", "ask_every_action"}:
            raise AgentRuntimeError("Autonomy preference is invalid; tool execution is blocked")
        read_allowed = (allow_read is True if autonomy_level is None
                        else autonomy_level == "auto_safe")
        if autonomy_level == "chat_only":
            raise AgentRuntimeError("Chat-only mode blocks tool execution")
        if risk != "read" or not read_allowed:
            trace = _CURRENT_TRACE.get()
            if trace is not None and len(trace.get("steps", ())) < self.limits.max_steps:
                _append_step(trace, tool_id[:64], "approval_required", risk,
                             0)
            raise AgentRuntimeApprovalRequired(tool_id, risk, preview)
        trace = _CURRENT_TRACE.get()
        if trace is None:
            raise AgentRuntimeError("Tool calls require an active Agent Runtime turn")
        if len(trace.get("steps", ())) >= self.limits.max_steps - 1:
            raise AgentRuntimeBudgetExceeded("Agent Runtime step budget exhausted")
        check_runtime_step()
        if progress:
            progress(f"Using {tool.name}...")
        started = self._clock()
        try:
            result = tool.execute(**validated)
            check_runtime_step()
        except AgentRuntimeError:
            raise
        except Exception:
            _append_step(trace, tool_id[:64], "failed", "registered tool", 0)
            raise AgentRuntimeError("Registered tool failed; raw diagnostics are omitted") from None
        if not isinstance(result, str) or len(result.encode("utf-8")) > 8192:
            _append_step(trace, tool_id[:64], "failed", "registered tool", 0)
            raise AgentRuntimeError("Registered tool returned an invalid or oversized result")
        _append_step(trace, tool_id[:64], "completed", "registered read-only tool",
                     max(0, int((self._clock() - started) * 1000)),
                     output_bytes=len(result.encode("utf-8")))
        return result

    def run_agentic(self, agent_id: str, planner: Callable[[tuple[dict, ...]], dict],
                    registry, *, allow_read_tools: bool = False,
                    autonomy_level: str | None = None,
                    progress: Callable[[str], None] | None = None):
        """Execute a synchronous plan/tool/observe loop within the shared limits.

        The planner is trusted adapter code around a model response. Its only
        accepted outputs are a final text answer or one registered tool call;
        output content is validated before any action can execute.
        """
        if not isinstance(agent_id, str) or not agent_id.strip() or not callable(planner):
            raise TypeError("Agent Runtime requires an Agent identity and planner")
        started = self._clock()
        deadline = started + self.limits.total_timeout_seconds
        run_id = uuid4().hex
        trace = {"run_id": run_id, "agent_id": agent_id[:128], "max_steps": self.limits.max_steps,
                 "token_budget": self.limits.token_budget, "steps": [], "outcome": "running"}
        _CURRENT_TRACE.set(trace)
        with self._lock:
            if self._stopped():
                trace.update(outcome="stopped", failure="Owner emergency stop is active.", elapsed_ms=0)
                raise AgentRuntimeStopped("Agent Runtime stopped by the owner")
            self._active.add(run_id)
        observations: list[dict] = []
        remaining_tokens = self.limits.token_budget
        try:
            _append_step(trace, "classify_plan", "completed", "bounded Agent Runtime planner", 0)
            operation_count = 0
            while operation_count < self.limits.max_steps:
                if self._stopped():
                    raise AgentRuntimeStopped("Agent Runtime stopped by the owner")
                if self._clock() >= deadline:
                    raise AgentRuntimeBudgetExceeded("Agent Runtime turn timed out")
                if remaining_tokens <= 0:
                    raise AgentRuntimeBudgetExceeded("Agent Runtime token budget exhausted")
                token_budget = min(self.limits.step_token_budget, remaining_tokens)
                remaining_tokens -= token_budget  # reserve conservatively; usage may be unknown
                now = self._clock()
                context_token = _CURRENT_INVOCATION.set(RuntimeInvocation(
                    deadline, min(deadline, now + self.limits.step_timeout_seconds),
                    token_budget, self._stopped))
                try:
                    decision = planner(tuple(dict(item) for item in observations))
                    check_runtime_step()
                finally:
                    _CURRENT_INVOCATION.reset(context_token)
                operation_count += 1
                if not isinstance(decision, dict) or not isinstance(decision.get("type"), str):
                    raise AgentRuntimeError("Agent planner returned an invalid structured decision")
                if decision["type"] == "answer":
                    if set(decision) != {"type", "text"} or not isinstance(decision.get("text"), str) \
                            or not decision["text"].strip() or len(decision["text"].encode("utf-8")) > 8192:
                        raise AgentRuntimeError("Agent planner returned an invalid final answer")
                    _append_step(trace, "answer", "completed", "configured Agent provider",
                                 max(0, int((self._clock() - now) * 1000)),
                                 output_bytes=len(decision["text"].encode("utf-8")))
                    trace.update(outcome="completed", elapsed_ms=max(0, int((self._clock() - started) * 1000)),
                                 remaining_token_budget=remaining_tokens)
                    return decision["text"]
                if (decision["type"] != "tool" or set(decision) != {"type", "tool_id", "arguments"}
                        or not isinstance(decision.get("tool_id"), str)
                        or not isinstance(decision.get("arguments"), dict)):
                    raise AgentRuntimeError("Agent planner returned an unsupported structured decision")
                tool_id = decision["tool_id"]
                _append_step(trace, "decide", "completed", "validated structured tool request",
                             max(0, int((self._clock() - now) * 1000)))
                context_token = _CURRENT_INVOCATION.set(RuntimeInvocation(
                    deadline, min(deadline, self._clock() + self.limits.step_timeout_seconds),
                    0, self._stopped))
                try:
                    result = self.invoke_tool(registry, tool_id, decision["arguments"],
                                              allow_read=allow_read_tools,
                                              autonomy_level=autonomy_level,
                                              progress=progress)
                finally:
                    _CURRENT_INVOCATION.reset(context_token)
                operation_count += 1
                observations.append({"tool_id": tool_id, "result": result, "untrusted": True})
                _append_step(trace, "observe", "completed", "tool result marked untrusted", 0,
                             output_bytes=len(result.encode("utf-8")))
                if len(observations) > self.limits.max_steps:
                    raise AgentRuntimeBudgetExceeded("Agent Runtime step budget exhausted")
            raise AgentRuntimeBudgetExceeded("Agent Runtime step budget exhausted before a final answer")
        except Exception as exc:
            trace["outcome"] = "stopped" if isinstance(exc, AgentRuntimeStopped) else "failed"
            trace["failure"] = _safe_failure(exc)
            trace["elapsed_ms"] = max(0, int((self._clock() - started) * 1000))
            raise
        finally:
            with self._lock:
                self._active.discard(run_id)

    def last_trace(self) -> dict | None:
        trace = _CURRENT_TRACE.get()
        return _copy_trace(trace) if trace is not None else None

    def take_trace(self) -> dict | None:
        """Return and clear the current request-context trace to prevent stale reuse."""
        trace = _CURRENT_TRACE.get()
        _CURRENT_TRACE.set(None)
        return _copy_trace(trace) if trace is not None else None

    def _stopped(self) -> bool:
        try:
            from app.resources.context import native_scope
            scope=native_scope.get()
            from app.resources.context import request_stop
            stop=request_stop.get()
            if (scope is not None and scope.cancelled) or (stop is not None and stop.is_set()):return True
            return self._stop_check() is True
        except Exception:
            # A missing/broken stop service blocks new runtime work.
            return True

    def _run(self, agent_id: str, operation: Callable, *, kind: str,
             progress: Callable[[str], None] | None = None):
        if not isinstance(agent_id, str) or not agent_id.strip() or not callable(operation):
            raise TypeError("Agent Runtime requires an Agent identity and operation")
        started = self._clock()
        deadline = started + self.limits.total_timeout_seconds
        token = uuid4().hex
        trace = {"run_id": token, "agent_id": agent_id[:128], "max_steps": self.limits.max_steps,
                 "token_budget": self.limits.token_budget, "steps": [], "outcome": "running"}
        _CURRENT_TRACE.set(trace)
        with self._lock:
            if self._stopped():
                trace["outcome"] = "stopped"
                trace["failure"] = "Owner emergency stop is active."
                trace["elapsed_ms"] = max(0, int((self._clock() - started) * 1000))
                raise AgentRuntimeStopped("Agent Runtime stopped by the owner")
            self._active.add(token)
        context_token: Token | None = None
        try:
            _append_step(trace, "classify", "completed", "direct response", 0)
            _append_step(trace, "plan", "completed", "one bounded response step", 0)
            if progress:
                progress("Answering...")
            if self._stopped():
                raise AgentRuntimeStopped("Agent Runtime stopped by the owner")
            now = self._clock()
            if now >= deadline:
                raise AgentRuntimeBudgetExceeded("Agent Runtime turn timed out")
            invocation = RuntimeInvocation(
                deadline=deadline,
                step_deadline=min(deadline, now + _step_seconds(self.limits)),
                output_token_budget=min(self.limits.step_token_budget, self.limits.token_budget),
                stop_check=self._stopped,
            )
            context_token = _CURRENT_INVOCATION.set(invocation)
            result = operation()
            check_runtime_step()
            elapsed = max(0, int((self._clock() - now) * 1000))
            output_bytes = len(result.encode("utf-8")) if isinstance(result, str) else 0
            if output_bytes > self.limits.token_budget * 4:
                raise AgentRuntimeBudgetExceeded("Agent Runtime output budget was reached")
            _append_step(trace, kind, "completed", "reviewed tool" if kind=='tool' else "configured Agent provider", elapsed,
                         output_bytes=output_bytes)
            trace["outcome"] = "completed"
            trace["elapsed_ms"] = max(0, int((self._clock() - started) * 1000))
            return result
        except Exception as exc:
            trace["outcome"] = "stopped" if isinstance(exc, AgentRuntimeStopped) else "failed"
            trace["failure"] = _safe_failure(exc)
            if len(trace["steps"]) < self.limits.max_steps:
                _append_step(trace, kind, "failed", "configured Agent provider", 0)
            trace["elapsed_ms"] = max(0, int((self._clock() - started) * 1000))
            raise
        finally:
            if context_token is not None:
                _CURRENT_INVOCATION.reset(context_token)
            with self._lock:
                self._active.discard(token)

    def run_direct(self, agent_id: str, operation: Callable, *, progress=None):
        return self._run(agent_id, operation, kind="answer", progress=progress)

    def run_tool_step(self,agent_id:str,operation:Callable,*,progress=None):
        """Bound a trusted approval-guarded callback; this grants no tool authority."""
        return self._run(agent_id,operation,kind='tool',progress=progress)

    def stream_direct(self, agent_id: str, operation: Callable, *, progress=None):
        """Run a provider stream under the same bounded context until it closes."""
        def stream():
            if not isinstance(agent_id, str) or not agent_id.strip() or not callable(operation):
                raise TypeError("Agent Runtime requires an Agent identity and operation")
            started = self._clock()
            deadline = started + self.limits.total_timeout_seconds
            run_id = uuid4().hex
            trace = {"run_id": run_id, "agent_id": agent_id[:128], "max_steps": self.limits.max_steps,
                     "token_budget": self.limits.token_budget, "steps": [], "outcome": "running"}
            _CURRENT_TRACE.set(trace)
            with self._lock:
                if self._stopped():
                    trace["outcome"] = "stopped"
                    trace["failure"] = "Owner emergency stop is active."
                    trace["elapsed_ms"] = max(0, int((self._clock() - started) * 1000))
                    raise AgentRuntimeStopped("Agent Runtime stopped by the owner")
                self._active.add(run_id)
            try:
                _append_step(trace, "classify", "completed", "direct response", 0)
                _append_step(trace, "plan", "completed", "one bounded response step", 0)
                if progress:
                    progress("Answering...")
                now = self._clock()
                invocation = RuntimeInvocation(
                    deadline, min(deadline, now + _step_seconds(self.limits)),
                    min(self.limits.step_token_budget, self.limits.token_budget), self._stopped)
                output_bytes = 0
                iterator = iter(operation())
                while True:
                    token = _CURRENT_INVOCATION.set(invocation)
                    try:
                        check_runtime_step()
                        try:
                            chunk = next(iterator)
                        except StopIteration:
                            break
                        check_runtime_step()
                    finally:
                        # Streaming generators may be advanced from different
                        # worker contexts. Set/reset for each synchronous step.
                        _CURRENT_INVOCATION.reset(token)
                    if isinstance(chunk, str):
                        output_bytes += len(chunk.encode("utf-8"))
                        if output_bytes > self.limits.token_budget * 4:
                            raise AgentRuntimeBudgetExceeded("Agent Runtime output budget was reached")
                    yield chunk
                _append_step(trace, "answer", "completed", "configured Agent provider",
                             max(0, int((self._clock() - now) * 1000)), output_bytes=output_bytes)
                trace["outcome"] = "completed"
            except Exception as exc:
                trace["outcome"] = "stopped" if isinstance(exc, AgentRuntimeStopped) else "failed"
                trace["failure"] = _safe_failure(exc)
                if len(trace["steps"]) < self.limits.max_steps:
                    _append_step(trace, "answer", "failed", "configured Agent provider", 0)
                raise
            finally:
                trace["elapsed_ms"] = max(0, int((self._clock() - started) * 1000))
                with self._lock:
                    self._active.discard(run_id)
        return stream()

    def assert_available(self) -> None:
        if self._stopped():
            raise AgentRuntimeStopped("Agent Runtime stopped by the owner")


def _append_step(trace: dict, step: str, status: str, source: str, duration_ms: int,
                 *, output_bytes: int | None = None):
    if len(trace["steps"]) >= 5:
        raise AgentRuntimeBudgetExceeded("Agent Runtime step budget exhausted")
    item = {"step": step, "status": status, "source": source,
            "duration_ms": max(0, int(duration_ms))}
    if output_bytes is not None:
        item["output_bytes"] = min(8192, max(0, int(output_bytes)))
    trace["steps"].append(item)


def _safe_failure(error: Exception) -> str:
    if isinstance(error, AgentRuntimeStopped):
        return "Owner emergency stop is active."
    if isinstance(error, AgentRuntimeBudgetExceeded):
        return "Agent Runtime time or step budget was reached."
    return "Agent Runtime provider step failed; no automatic retry occurred."


def _copy_trace(trace: dict) -> dict:
    return {**trace, "steps": [dict(item) for item in trace.get("steps", ())]}
