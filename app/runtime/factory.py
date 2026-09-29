from dataclasses import dataclass

from app.agents import Agent, AgentRegistry, Employee, EmployeeRegistry
from app.application import CorporationApplicationService
from app.corporation import Corporation, CorporationRegistry
from app.database import initialize_database
from app.node import Node, NodeRegistry
from app.orchestrator import Orchestrator, ProjectRegistry, TaskRegistry
from app.providers import OllamaProvider, ProviderRegistry

from .config import RuntimeConfig
from .initializer import RuntimeInitializer


@dataclass
class CorporationRuntime:
    corporation: Corporation
    node: Node
    agents: AgentRegistry
    employees: EmployeeRegistry
    providers: ProviderRegistry
    tasks: TaskRegistry
    projects: ProjectRegistry
    orchestrator: Orchestrator
    application_service: CorporationApplicationService


def create_corporation_runtime() -> CorporationRuntime:
    """Build the configured local Corporation runtime and application boundary."""
    initialize_database()

    corporation_registry = CorporationRegistry()
    node_registry = NodeRegistry()

    corporation_id = "corp_local"
    node_id = "node_local"

    corporation = Corporation(
        id=corporation_id,
        name="ERSELMETZ Local Corp",
    )
    corporation_registry.register(corporation)

    node = Node(
        id=node_id,
        corporation_id=corporation_id,
        name="Local Node 1",
    )
    node_registry.register(node)

    context = RuntimeConfig(
        corporation_id=corporation_id,
        node_id=node_id,
    ).to_context()
    RuntimeInitializer(corporation_registry, node_registry, context).initialize()

    agent_registry = AgentRegistry()
    provider_registry = ProviderRegistry()
    task_registry = TaskRegistry()
    project_registry = ProjectRegistry()

    provider_registry.register("ollama", OllamaProvider())

    local_worker = Agent(
        id="local_worker",
        name="Local Worker",
        role="Local AI Worker",
        provider="ollama",
        model="llama3.2:3b",
        capabilities=[
            "text_generation",
            "summarization",
            "classification",
        ],
        permissions=["read_files"],
    )
    agent_registry.register(local_worker)

    employee_registry = EmployeeRegistry()
    employee_registry.register(
        Employee(
            id="local_employee",
            name="Local Worker",
            role="Local AI Worker",
            responsibilities=["General task execution"],
            agent=local_worker,
        )
    )

    orchestrator = Orchestrator(
        agents=agent_registry,
        providers=provider_registry,
        tasks=task_registry,
        projects=project_registry,
        employees=employee_registry,
    )
    application_service = CorporationApplicationService(
        orchestrator,
        corporation=corporation,
        node=node,
    )

    return CorporationRuntime(
        corporation=corporation,
        node=node,
        agents=agent_registry,
        employees=employee_registry,
        providers=provider_registry,
        tasks=task_registry,
        projects=project_registry,
        orchestrator=orchestrator,
        application_service=application_service,
    )
