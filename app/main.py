from app.agents import Agent, AgentRegistry
from app.orchestrator import Orchestrator, TaskRegistry
from app.providers import OllamaProvider, ProviderRegistry
from app.database import initialize_database
from app.orchestrator import ProjectRegistry


def main():
    initialize_database()

    agent_registry = AgentRegistry()
    provider_registry = ProviderRegistry()
    task_registry = TaskRegistry()
    projects = ProjectRegistry()
    # Providers
    ollama = OllamaProvider(
        model="llama3.2:3b",
    )

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

    print("🏢 ERSELMETZ AI CORPORATION")
    print("HR Department: ONLINE")
    print("🧠 Provider Department: ONLINE")
    print("🎯 Orchestrator: ONLINE")
    print()


if __name__ == "__main__":
    main()