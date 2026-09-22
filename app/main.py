from app.agents import Agent, AgentRegistry


def main():
    registry = AgentRegistry()

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

    registry.register(local_worker)

    print("🏢 ERSELMETZ AI CORPORATION")
    print("HR Department: ONLINE")
    print()

    for agent in registry.all():
        print(f"👤 {agent.describe()}")
        print(f"   Capabilities: {', '.join(agent.capabilities)}")
        print(f"   Permissions: {', '.join(agent.permissions)}")


if __name__ == "__main__":
    main()