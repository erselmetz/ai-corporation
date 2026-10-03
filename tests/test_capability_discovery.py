from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from app.capability_discovery import (
    MAX_CAPABILITY_CANDIDATES,
    CapabilityCandidate,
    CapabilityCandidateSource,
    CapabilityDiscoveryReport,
    CapabilityDiscoveryService,
)
from app.runtime.factory import create_corporation_runtime


def candidate(candidate_id: str = "candidate-1") -> CapabilityCandidate:
    return CapabilityCandidate(
        candidate_id=candidate_id,
        name="Read-only status integration",
        description="Read service status without changing remote state.",
        source_reference="caller-note:status-integration",
    )


def test_discovery_returns_immutable_caller_supplied_candidates_only() -> None:
    candidates = (candidate(), candidate("candidate-2"))

    report = CapabilityDiscoveryService().discover(candidates)

    assert report.candidates is candidates
    assert report.source is CapabilityCandidateSource.CALLER_SUPPLIED
    assert report.discovered_at.tzinfo == timezone.utc
    assert report.candidates[0].source_reference == "caller-note:status-integration"
    assert any("not independently verified" in item for item in report.limitations)
    assert any(
        "does not evaluate, rank, register, grant, or activate" in item
        for item in report.limitations
    )
    with pytest.raises(FrozenInstanceError):
        report.candidates = ()
    with pytest.raises(FrozenInstanceError):
        report.candidates[0].name = "Activated capability"


def test_application_service_exposes_review_only_discovery_without_mutating_runtime() -> None:
    runtime = create_corporation_runtime()
    agents_before = tuple(
        (agent.id, agent.provider, agent.model, tuple(agent.capabilities))
        for agent in runtime.agents.all()
    )
    providers_before = tuple(runtime.providers.all())
    tasks_before = tuple(task.id for task in runtime.tasks.all())

    report = runtime.application_service.discover_capabilities((candidate(),))

    assert report.candidates == (candidate(),)
    assert tuple(
        (agent.id, agent.provider, agent.model, tuple(agent.capabilities))
        for agent in runtime.agents.all()
    ) == agents_before
    assert tuple(runtime.providers.all()) == providers_before
    assert tuple(task.id for task in runtime.tasks.all()) == tasks_before


@pytest.mark.parametrize(
    ("value", "error", "message"),
    [
        ([], TypeError, "immutable tuple"),
        ((object(),), TypeError, "Expected CapabilityCandidate"),
        ((candidate(), candidate()), ValueError, "unique"),
        (
            tuple(
                candidate(f"candidate-{index}")
                for index in range(MAX_CAPABILITY_CANDIDATES + 1)
            ),
            ValueError,
            "count exceeds",
        ),
    ],
)
def test_discovery_rejects_invalid_candidate_collections(
    value: object,
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error, match=message):
        CapabilityDiscoveryService().discover(value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("candidate_id", "", "non-empty"),
        ("name", "x" * 257, "byte limit"),
        ("description", "bad\ninput", "control characters"),
        ("source_reference", "x" * 2049, "byte limit"),
    ],
)
def test_candidate_metadata_is_nonempty_bounded_and_single_line(
    field: str,
    value: str,
    message: str,
) -> None:
    fields = {
        "candidate_id": "candidate-1",
        "name": "Candidate",
        "description": "A candidate description.",
        "source_reference": "caller-note:1",
    }
    fields[field] = value

    with pytest.raises(ValueError, match=message):
        CapabilityCandidate(**fields)


def test_report_rejects_naive_timestamp_and_mutable_candidates() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        CapabilityDiscoveryReport(
            discovered_at=datetime(2026, 10, 4),
            candidates=(),
        )
    with pytest.raises(TypeError, match="immutable tuple"):
        CapabilityDiscoveryReport(
            discovered_at=datetime.now(timezone.utc),
            candidates=[],  # type: ignore[arg-type]
        )
