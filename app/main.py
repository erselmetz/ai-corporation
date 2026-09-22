from app.agents import Agent, AgentRegistry
from app.orchestrator import Orchestrator, TaskRegistry
from app.providers import OllamaProvider, ProviderRegistry
from app.database import initialize_database


def main():
    initialize_database()

    agent_registry = AgentRegistry()
    provider_registry = ProviderRegistry()
    task_registry = TaskRegistry()

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
    )

    print("🏢 ERSELMETZ AI CORPORATION")
    print("HR Department: ONLINE")
    print("🧠 Provider Department: ONLINE")
    print("🎯 Orchestrator: ONLINE")
    print()

    # Create Task
    task = orchestrator.create_task(
    title="Corporation Introduction",
    description=(
        "You are the Local Worker of Erselmetz AI Corporation. "
        "Introduce yourself in one short sentence."
    ),
    agent_id="local_worker",
)

    print(f"📋 Task: {task.id}")
    print(f"   Title: {task.title}")
    print(f"   Status: {task.status.value}")
    print()

    # Execute Task
    task = orchestrator.execute_task(task)

    print()
    print("📦 Stored Tasks:")

    for stored_task in task_registry.all():
        print(
            f"   {stored_task.id} | "
            f"{stored_task.title} | "
            f"{stored_task.status.value}"
        )   

    print(f"📋 Task Status: {task.status.value}")

    if task.result:
        print(f"🤖 Result: {task.result}")

    if task.error:
        print(f"❌ Error: {task.error}")


if __name__ == "__main__":
    main()