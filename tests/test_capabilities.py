from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import FrozenInstanceError

import pytest

from app.agents import Agent, AgentRegistry
from app.capabilities import (
    CapabilityEvidence,
    CapabilityRegistry,
    CapabilitySource,
)
from app.integrations.gemini_catalog import (
    GeminiCatalogAuditEvent,
    GeminiCatalogAuditStatus,
    GeminiModel,
    GeminiModelCapability,
    GeminiModelCatalogResult,
)
from app.integrations.models import IntegrationCapability
from app.tools import Tool, ToolRegistry


class ExampleTool(Tool):
    def __init__(self) -> None:
        super().__init__("report-tool", "Report tool", "Returns a fixed report.")

    def execute(self, **kwargs: object) -> str:
        del kwargs
        return "report"


def make_registries() -> tuple[AgentRegistry, ToolRegistry]:
    agents = AgentRegistry()
    agents.register(
        Agent(
            id="agent-1",
            name="Research Agent",
            role="researcher",
            provider="ollama",
            model="local-model",
            capabilities=["summarize", "review", "summarize"],
        )
    )
    tools = ToolRegistry()
    tools.register(ExampleTool())
    return agents, tools


def make_gemini_catalog(
    retrieved_at: datetime | None = None,
) -> GeminiModelCatalogResult:
    observed_at = retrieved_at or datetime.now(timezone.utc)
    event = GeminiCatalogAuditEvent(
        service="gemini",
        operation="list_models",
        status=GeminiCatalogAuditStatus.SUCCEEDED,
        occurred_at=observed_at,
        pages_requested=1,
        model_count=2,
        has_more=True,
        failure_code=None,
    )
    return GeminiModelCatalogResult(
        models=(
            GeminiModel(
                model_id="models/gemini-example",
                capabilities=(GeminiModelCapability.GENERATE_CONTENT,),
            ),
            GeminiModel(
                model_id="models/metadata-unknown",
                capabilities=None,
            ),
        ),
        has_more=True,
        retrieved_at=observed_at,
        audit_event=event,
    )


def test_registry_aggregates_sources_without_granting_or_mutating_capabilities() -> None:
    agents, tools = make_registries()
    agent = agents.get("agent-1")
    catalog = make_gemini_catalog()
    registry = CapabilityRegistry(agents, tools)

    snapshot = registry.snapshot(gemini_catalog=catalog)

    agent_records = [
        record for record in snapshot.records if record.source is CapabilitySource.AGENT
    ]
    assert [record.capability for record in agent_records] == ["review", "summarize"]
    assert all(
        record.evidence is CapabilityEvidence.AGENT_DECLARED
        and record.owner_id == "agent-1"
        and record.owner_name == "Research Agent"
        and record.requirements
        for record in agent_records
    )
    tool_record = next(
        record for record in snapshot.records if record.source is CapabilitySource.TOOL
    )
    assert tool_record.capability == "tool.execute"
    assert tool_record.source_id == "report-tool"
    assert tool_record.description == "Returns a fixed report."
    assert "does not authorize" in tool_record.policy_boundaries[0]

    scope_records = [
        record
        for record in snapshot.records
        if record.source is CapabilitySource.INTEGRATION_SCOPE
    ]
    assert len(scope_records) == len(IntegrationCapability)
    assert all(record.evidence is CapabilityEvidence.SCOPE_ONLY for record in scope_records)
    assert all(record.requirements is None for record in scope_records)
    assert all("grants no permission" in record.policy_boundaries[0] for record in scope_records)

    gemini_records = [
        record
        for record in snapshot.records
        if record.source is CapabilitySource.GEMINI_MODEL
    ]
    assert len(gemini_records) == 1
    assert gemini_records[0].source_id == "models/gemini-example"
    assert all(
        record.source_id != "models/metadata-unknown" for record in gemini_records
    )
    assert gemini_records[0].capability == "generateContent"
    assert gemini_records[0].evidence is CapabilityEvidence.SERVICE_REPORTED
    assert gemini_records[0].observed_at == catalog.retrieved_at
    assert snapshot.gemini_catalog_model_count == 2
    assert snapshot.gemini_catalog_has_more is True
    assert snapshot.gemini_catalog_retrieved_at == catalog.retrieved_at
    assert snapshot.generated_at.tzinfo == timezone.utc
    assert agent.capabilities == ["summarize", "review", "summarize"]
    assert agent.provider == "ollama"
    assert agent.model == "local-model"
    assert tools.all()[0].id == "report-tool"
    assert "does not establish" in gemini_records[0].policy_boundaries[0]
    with pytest.raises(FrozenInstanceError):
        snapshot.records = ()


def test_registry_does_not_call_gemini_or_claim_unprovided_metadata() -> None:
    agents, tools = make_registries()

    snapshot = CapabilityRegistry(agents, tools).snapshot()

    assert snapshot.gemini_catalog_retrieved_at is None
    assert snapshot.gemini_catalog_model_count is None
    assert snapshot.gemini_catalog_has_more is None
    assert not any(record.source is CapabilitySource.GEMINI_MODEL for record in snapshot.records)


def test_supplied_gemini_snapshot_freshness_is_visible_without_refresh() -> None:
    agents, tools = make_registries()
    observed_at = datetime.now(timezone.utc) - timedelta(days=7)

    snapshot = CapabilityRegistry(agents, tools).snapshot(
        gemini_catalog=make_gemini_catalog(observed_at)
    )

    gemini_record = next(
        record for record in snapshot.records if record.source is CapabilitySource.GEMINI_MODEL
    )
    assert gemini_record.observed_at == observed_at
    assert gemini_record.observed_at < snapshot.generated_at
    assert snapshot.gemini_catalog_has_more is True


def test_registry_fails_explicitly_when_source_metadata_exceeds_bounds() -> None:
    agents = AgentRegistry()
    agents.register(
        Agent(
            id="large-agent",
            name="Large Agent",
            role="researcher",
            provider="ollama",
            model="local-model",
            capabilities=["x" * 513],
        )
    )

    with pytest.raises(ValueError, match="capability is invalid"):
        CapabilityRegistry(agents, ToolRegistry()).snapshot()
