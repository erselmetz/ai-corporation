from unittest.mock import MagicMock

import pytest

from app.agents import Agent, AgentRegistry, Employee, EmployeeRegistry
from app.application import CorporationApplicationService, DryRunSummary, TaskSummary
from app.corporation import Corporation
from app.node import Node
from app.orchestrator import Orchestrator, ProjectRegistry, TaskRegistry
from app.providers import AIProvider, ProviderRegistry


class RecordingProvider(AIProvider):
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def generate(self, model: str, prompt: str) -> str:
        self.calls.append((model, prompt))
        return f"{model}: {prompt}"


@pytest.fixture
def application_setup():
    agents = AgentRegistry()
    worker = Agent(
        id="worker",
        name="Worker",
        role="Task Worker",
        provider="test-provider",
        model="test-model",
        capabilities=["summarization"],
    )
    agents.register(worker)

    employees = EmployeeRegistry()
    employees.register(
        Employee(
            id="employee",
            name="Task Employee",
            role="Task Worker",
            agent=worker,
        )
    )

    provider = RecordingProvider()
    providers = ProviderRegistry()
    providers.register("test-provider", provider)

    orchestrator = Orchestrator(
        agents=agents,
        providers=providers,
        tasks=TaskRegistry(),
        projects=ProjectRegistry(),
        employees=employees,
    )
    return CorporationApplicationService(orchestrator), orchestrator, provider


def test_application_service_coordinates_task_use_cases_without_registry_contract(
    application_setup,
):
    application, orchestrator, provider = application_setup

    created = application.create_task(
        title="Summarize",
        description="Summarize a report",
        role="Task Worker",
    )

    assert isinstance(created, TaskSummary)
    assert created.status == "pending"
    assert created.required_role == "Task Worker"
    assert created.project_id == "default_proj"
    assert orchestrator.tasks.get(created.id).required_role == "Task Worker"
    assert application.get_task(created.id) == created
    assert application.list_tasks() == [created]
    assert not hasattr(created, "registry")
    assert not hasattr(created, "assigned_agent_object")

    preview = application.dry_run_task(created.id)

    assert isinstance(preview, DryRunSummary)
    assert preview.selected_agent_id == "worker"
    assert preview.selected_employee_id == "employee"
    assert preview.routing_method == "employee_role"
    assert preview.status == "ready"
    assert provider.calls == []
    assert orchestrator.tasks.get(created.id).status.value == "pending"
    assert orchestrator.tasks.get(created.id).assigned_agent is None

    completed = application.execute_task(created.id)

    assert completed.status == "completed"
    assert completed.result == "test-model: Summarize a report"
    assert provider.calls == [("test-model", "Summarize a report")]


def test_application_service_uses_existing_validation(application_setup):
    application, _, _ = application_setup
    application.create_task(
        title="Task",
        description="Description",
    )

    with pytest.raises(ValueError, match="Routing options are mutually exclusive"):
        application.create_task(
            title="Invalid",
            description="Conflicting routes",
            project_id="default_proj",
            agent_id="worker",
            role="Task Worker",
        )


def test_application_service_returns_read_only_corporation_status_summary():
    orchestrator = MagicMock(spec=Orchestrator)
    corporation = Corporation(id="corp_local", name="ERSELMETZ Local Corp")
    node = Node(
        id="node_local",
        corporation_id=corporation.id,
        name="Local Node 1",
    )
    application = CorporationApplicationService(
        orchestrator,
        corporation=corporation,
        node=node,
    )

    status = application.get_corporation_status()

    assert status.corporation_id == corporation.id
    assert status.corporation_name == corporation.name
    assert status.node_id == node.id
    assert status.node_name == node.name
    assert not hasattr(status, "registry")
    assert orchestrator.method_calls == []
