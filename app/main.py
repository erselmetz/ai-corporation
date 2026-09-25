from app.agents import Agent, AgentRegistry, EmployeeRegistry
from app.orchestrator import Orchestrator, TaskRegistry
from app.providers import OllamaProvider, ProviderRegistry
from app.database import initialize_database
from app.orchestrator import ProjectRegistry
from app.corporation import Corporation, CorporationRegistry
from app.node import Node, NodeRegistry
from app.runtime import RuntimeConfig, RuntimeInitializer


def main(interactive: bool = True):
    initialize_database()

    # --- Runtime Identity Initialization ---
    corp_registry = CorporationRegistry()
    node_registry = NodeRegistry()

    # Setup local identities for development
    corp_id = "corp_local"
    node_id = "node_local"

    corp = Corporation(id=corp_id, name="ERSELMETZ Local Corp")
    corp_registry.register(corp)

    node = Node(id=node_id, corporation_id=corp_id, name="Local Node 1")
    node_registry.register(node)

    # Initialize runtime context
    config = RuntimeConfig(corporation_id=corp_id, node_id=node_id)
    context = config.to_context()
    
    initializer = RuntimeInitializer(corp_registry, node_registry, context)
    initializer.initialize()

    # Existing startup logic
    agent_registry = AgentRegistry()
    provider_registry = ProviderRegistry()
    task_registry = TaskRegistry()
    projects = ProjectRegistry()
    # Providers
    ollama = OllamaProvider()

    provider_registry.register("ollama", ollama)

    # Agents
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
        permissions=[
            "read_files",
        ],
    )

    agent_registry.register(local_worker)

    # Orchestrator
    orchestrator = Orchestrator(
        agents=agent_registry,
        providers=provider_registry,
        tasks=task_registry,
        projects=projects,
    )

    print("ERSELMETZ AI CORPORATION")
    print(f"Corporation: {corp.name} ({corp_id})")
    print(f"Node: {node.name} ({node_id})")
    print("HR Department: ONLINE")
    print("Provider Department: ONLINE")
    print("Orchestrator: ONLINE")
    print()

    if interactive:
        from app.interface.command import CommandInterface, CorporationContext
        ctx = CorporationContext(
            corp=corp,
            node=node,
            orchestrator=orchestrator,
            agent_registry=agent_registry,
            employee_registry=EmployeeRegistry(), # In main.py, employees are not yet registered, but we pass the registry
            task_registry=task_registry,
            project_registry=projects,
        )
        shell = CommandInterface(ctx)
        shell.run()



if __name__ == "__main__":
    main()