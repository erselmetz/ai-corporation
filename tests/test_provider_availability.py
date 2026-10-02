from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from unittest.mock import Mock

import httpx
import pytest

from app.orchestrator.task import Task, TaskStatus
from app.providers import (
    AIProvider,
    AvailabilityResult,
    AvailabilityState,
    OllamaProvider,
)
from app.resources import ModelLimit, ProviderLimit, ResourceLimits
from app.runtime.factory import create_corporation_runtime


class GenerationOnlyProvider(AIProvider):
    def __init__(self):
        self.calls = []

    def generate(self, model, prompt):
        self.calls.append((model, prompt))
        return "Deterministic response"


class AvailableProvider(GenerationOnlyProvider):
    def check_availability(self):
        return AvailabilityResult(
            AvailabilityState.AVAILABLE,
            datetime.now(timezone.utc),
        )


def test_generation_only_provider_remains_compatible_and_defaults_to_unknown():
    provider = GenerationOnlyProvider()

    result = provider.check_availability()

    assert result == AvailabilityResult()
    assert result.state is AvailabilityState.UNKNOWN
    assert result.checked_at is None
    assert provider.generate("model", "prompt") == "Deterministic response"
    assert provider.calls == [("model", "prompt")]


def test_availability_result_is_immutable_and_requires_aware_timestamp():
    result = AvailabilityResult(
        AvailabilityState.AVAILABLE,
        datetime.now(timezone.utc),
    )

    with pytest.raises(FrozenInstanceError):
        result.state = AvailabilityState.UNKNOWN
    with pytest.raises(ValueError, match="required"):
        AvailabilityResult(AvailabilityState.AVAILABLE)
    with pytest.raises(ValueError, match="timezone-aware"):
        AvailabilityResult(AvailabilityState.AVAILABLE, datetime.now())
    with pytest.raises(ValueError, match="160 characters"):
        AvailabilityResult(reason="x" * 161)


def test_application_service_checks_registered_provider_without_side_effects():
    runtime = create_corporation_runtime()
    runtime.providers.remove("ollama")
    provider = AvailableProvider()
    runtime.providers.register("ollama", provider)
    runtime.tasks.register(
        Task("availability-task", "Work", "Description", assigned_agent="local_worker")
    )
    resource_manager = runtime.application_service.resource_manager(
        ResourceLimits(
            2,
            (ProviderLimit("ollama", 2),),
            (ModelLimit("ollama", "llama3.2:3b", 2),),
        )
    )
    tasks_before = tuple(runtime.tasks.all())
    assignments_before = tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    )
    resources_before = resource_manager.snapshot()

    result = runtime.application_service.check_provider_availability("ollama")

    assert result.state is AvailabilityState.AVAILABLE
    assert result.checked_at is not None and result.checked_at.utcoffset().total_seconds() == 0
    assert tuple(runtime.tasks.all()) == tasks_before
    assert runtime.tasks.get("availability-task").status is TaskStatus.PENDING
    assert tuple(
        (agent.id, agent.provider, agent.model) for agent in runtime.agents.all()
    ) == assignments_before
    assert resource_manager.snapshot() == resources_before
    assert provider.calls == []


def test_missing_provider_is_not_reported_as_unknown():
    runtime = create_corporation_runtime()

    with pytest.raises(ValueError, match="Provider not found: missing"):
        runtime.application_service.check_provider_availability("missing")


def test_ollama_success_uses_lightweight_endpoint_and_bounded_timeout(monkeypatch):
    response = httpx.Response(
        200,
        request=httpx.Request("GET", "http://localhost:11434/api/tags"),
    )
    get = Mock(return_value=response)
    monkeypatch.setattr(httpx, "get", get)
    provider = OllamaProvider("http://localhost:11434/")

    result = provider.check_availability()

    assert result.state is AvailabilityState.AVAILABLE
    assert result.checked_at is not None
    get.assert_called_once_with(
        "http://localhost:11434/api/tags",
        timeout=2.0,
    )


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (
            httpx.TimeoutException("token=secret timeout at C:\\private\\url"),
            "Provider availability check timed out.",
        ),
        (
            httpx.ConnectError("token=secret at C:\\private\\url"),
            "Provider service could not be reached.",
        ),
    ],
)
def test_ollama_expected_failures_are_unavailable_without_exception_details(
    monkeypatch, failure, reason
):
    get = Mock(side_effect=failure)
    monkeypatch.setattr(httpx, "get", get)

    result = OllamaProvider().check_availability()

    assert result.state is AvailabilityState.UNAVAILABLE
    assert result.reason == reason
    assert "secret" not in result.reason
    assert "C:\\" not in result.reason
    assert result.checked_at is not None


def test_ollama_unsuccessful_http_status_is_unavailable_without_response_body(monkeypatch):
    response = httpx.Response(
        503,
        text="Authorization: Bearer secret-token",
        request=httpx.Request("GET", "http://localhost:11434/api/tags"),
    )
    monkeypatch.setattr(httpx, "get", Mock(return_value=response))

    result = OllamaProvider().check_availability()

    assert result.state is AvailabilityState.UNAVAILABLE
    assert result.reason == "Provider service returned an unsuccessful response."
    assert "secret-token" not in result.reason


def test_ollama_unexpected_programming_error_is_not_hidden(monkeypatch):
    monkeypatch.setattr(httpx, "get", Mock(side_effect=RuntimeError("programming defect")))

    with pytest.raises(RuntimeError, match="programming defect"):
        OllamaProvider().check_availability()
