from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from app.application import (
    CorporationApplicationService,
    PlatformRegistryName,
    PlatformSourceState,
)
from app.capabilities import CapabilityEvidence, CapabilitySource
from app.database import get_connection
from app.runtime.factory import create_corporation_runtime
from app.tools import Tool, ToolRegistry


class OverviewTool(Tool):
    def execute(self, **kwargs) -> str:
        raise AssertionError("Platform overview executed a Tool")


def _registry_counts(report):
    return {item.registry: item for item in report.registries}


def _capability_sources(report):
    return {item.source: item for item in report.capability_sources}


def test_platform_overview_reports_registered_sources_and_metadata_without_side_effects():
    runtime = create_corporation_runtime()
    tools = ToolRegistry()
    tools.register(OverviewTool("overview-tool", "Overview Tool", "Returns fixed metadata."))
    application = CorporationApplicationService(
        runtime.orchestrator,
        corporation=runtime.corporation,
        node=runtime.node,
        tool_registry=tools,
    )
    before_agents = tuple(
        (agent.id, agent.provider, agent.model, tuple(agent.capabilities))
        for agent in runtime.agents.all()
    )
    before_employees = tuple(
        (employee.id, employee.role, tuple(employee.responsibilities), employee.agent.id)
        for employee in runtime.employees.all()
    )
    before_tasks = tuple(
        (task.id, task.status, task.assigned_agent) for task in runtime.tasks.all()
    )
    before_providers = tuple(runtime.providers.all())

    provider = runtime.providers.get("ollama")
    with (
        patch.object(
            provider,
            "generate",
            side_effect=AssertionError("Platform overview called a Provider"),
        ) as generate,
        patch.object(
            provider,
            "check_availability",
            side_effect=AssertionError("Platform overview checked Provider availability"),
        ) as check_availability,
        patch.object(
            provider,
            "api_key",
            "platform-overview-secret",
            create=True,
        ),
        patch.object(
            tools.get("overview-tool"),
            "execute",
            side_effect=AssertionError("Platform overview executed a Tool"),
        ) as execute,
    ):
        report = application.platform_overview()

    generate.assert_not_called()
    check_availability.assert_not_called()
    execute.assert_not_called()
    assert "platform-overview-secret" not in repr(report)
    assert report.identity == runtime.application_service.get_corporation_status()
    assert report.identity_state is PlatformSourceState.CONFIGURED
    assert report.observed_at.tzinfo is not None

    counts = _registry_counts(report)
    assert set(counts) == set(PlatformRegistryName)
    assert counts[PlatformRegistryName.EMPLOYEES].count == len(runtime.employees.all())
    assert counts[PlatformRegistryName.AGENTS].count == len(runtime.agents.all())
    assert counts[PlatformRegistryName.PROVIDERS].count == len(runtime.providers.all())
    assert counts[PlatformRegistryName.PROJECTS].count == len(runtime.projects.all())
    assert counts[PlatformRegistryName.TASKS].count == len(runtime.tasks.all())
    assert all(item.state is PlatformSourceState.CONFIGURED for item in counts.values())

    sources = _capability_sources(report)
    assert sources[CapabilitySource.AGENT].state is PlatformSourceState.CONFIGURED
    assert sources[CapabilitySource.AGENT].record_count == sum(
        record.source is CapabilitySource.AGENT
        for record in report.capability_catalog.records
    )
    assert sources[CapabilitySource.TOOL].state is PlatformSourceState.CONFIGURED
    assert sources[CapabilitySource.TOOL].record_count == 1
    assert sources[CapabilitySource.GEMINI_MODEL].state is PlatformSourceState.UNKNOWN
    assert sources[CapabilitySource.GEMINI_MODEL].record_count is None
    assert len(report.capability_catalog.records) <= 2_000

    agent_record = next(
        record
        for record in report.capability_catalog.records
        if record.source is CapabilitySource.AGENT
    )
    assert agent_record.evidence is CapabilityEvidence.AGENT_DECLARED
    assert agent_record.requirements
    assert agent_record.policy_boundaries

    tool_record = next(
        record
        for record in report.capability_catalog.records
        if record.source is CapabilitySource.TOOL
    )
    assert tool_record.evidence is CapabilityEvidence.TOOL_REGISTERED
    assert tool_record.requirements
    assert tool_record.policy_boundaries

    scope_record = next(
        record
        for record in report.capability_catalog.records
        if record.source is CapabilitySource.INTEGRATION_SCOPE
    )
    assert scope_record.evidence is CapabilityEvidence.SCOPE_ONLY
    assert scope_record.requirements is None
    assert scope_record.policy_boundaries
    assert report.limitations
    with pytest.raises(FrozenInstanceError):
        report.identity = None
    with pytest.raises(FrozenInstanceError):
        report.capability_catalog.records = ()

    assert tuple(
        (agent.id, agent.provider, agent.model, tuple(agent.capabilities))
        for agent in runtime.agents.all()
    ) == before_agents
    assert tuple(
        (employee.id, employee.role, tuple(employee.responsibilities), employee.agent.id)
        for employee in runtime.employees.all()
    ) == before_employees
    assert tuple(
        (task.id, task.status, task.assigned_agent) for task in runtime.tasks.all()
    ) == before_tasks
    assert tuple(runtime.providers.all()) == before_providers
    assert application._resource_manager is None
    assert application._tool_registry is tools
    assert application._task_collaboration is None
    assert application._capability_integration_workflow is None
    assert application._maintenance_workflow is None
    connection = get_connection()
    try:
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='platform_overviews'"
        ).fetchone() is None
    finally:
        connection.close()


def test_platform_overview_reports_missing_sources_as_unavailable_and_gemini_as_unknown():
    runtime = create_corporation_runtime()
    runtime.orchestrator.employees = None
    runtime.orchestrator.agents = None
    application = CorporationApplicationService(runtime.orchestrator)

    report = application.platform_overview()

    assert report.identity is None
    assert report.identity_state is PlatformSourceState.UNAVAILABLE
    counts = _registry_counts(report)
    assert counts[PlatformRegistryName.EMPLOYEES].state is PlatformSourceState.UNAVAILABLE
    assert counts[PlatformRegistryName.EMPLOYEES].count is None
    assert counts[PlatformRegistryName.AGENTS].state is PlatformSourceState.UNAVAILABLE
    assert counts[PlatformRegistryName.AGENTS].count is None
    assert all(
        counts[name].state is PlatformSourceState.CONFIGURED
        for name in (
            PlatformRegistryName.PROVIDERS,
            PlatformRegistryName.PROJECTS,
            PlatformRegistryName.TASKS,
        )
    )
    sources = _capability_sources(report)
    assert sources[CapabilitySource.AGENT].state is PlatformSourceState.UNAVAILABLE
    assert sources[CapabilitySource.AGENT].record_count is None
    assert sources[CapabilitySource.TOOL].state is PlatformSourceState.UNAVAILABLE
    assert sources[CapabilitySource.TOOL].record_count is None
    assert sources[CapabilitySource.GEMINI_MODEL].state is PlatformSourceState.UNKNOWN
    assert not any(
        record.source in (CapabilitySource.AGENT, CapabilitySource.TOOL, CapabilitySource.GEMINI_MODEL)
        for record in report.capability_catalog.records
    )
    assert application._tool_registry is None
    assert application._resource_manager is None
    assert application._task_collaboration is None
    assert application._capability_integration_workflow is None
    assert application._maintenance_workflow is None


def test_platform_overview_distinguishes_an_explicitly_configured_empty_tool_registry():
    runtime = create_corporation_runtime()
    tools = ToolRegistry()
    application = CorporationApplicationService(
        runtime.orchestrator,
        tool_registry=tools,
    )

    report = application.platform_overview()

    tool_source = _capability_sources(report)[CapabilitySource.TOOL]
    assert tool_source.state is PlatformSourceState.CONFIGURED
    assert tool_source.record_count == 0
    assert not any(
        record.source is CapabilitySource.TOOL
        for record in report.capability_catalog.records
    )


def test_platform_overview_fails_explicitly_when_capability_metadata_exceeds_its_bound(
    monkeypatch,
):
    from app import capabilities

    runtime = create_corporation_runtime()
    monkeypatch.setattr(capabilities, "MAX_CAPABILITY_RECORDS", 2)

    with pytest.raises(ValueError, match="record limit"):
        runtime.application_service.platform_overview()


def test_platform_overview_rejects_unbounded_identity_output():
    runtime = create_corporation_runtime()
    runtime.corporation.name = "x" * 513

    with pytest.raises(ValueError, match="identity fields"):
        runtime.application_service.platform_overview()
