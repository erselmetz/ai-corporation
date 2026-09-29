from app.runtime import create_corporation_runtime


def main(interactive: bool = True) -> None:
    runtime = create_corporation_runtime()

    print("ERSELMETZ AI CORPORATION")
    print(
        f"Corporation: {runtime.corporation.name} "
        f"({runtime.corporation.id})"
    )
    print(f"Node: {runtime.node.name} ({runtime.node.id})")
    print("HR Department: ONLINE")
    print("Provider Department: ONLINE")
    print("Orchestrator: ONLINE")
    print()

    if interactive:
        from app.interface.command import CommandInterface, CorporationContext

        context = CorporationContext(
            corp=runtime.corporation,
            node=runtime.node,
            orchestrator=runtime.orchestrator,
            agent_registry=runtime.agents,
            employee_registry=runtime.employees,
            task_registry=runtime.tasks,
            project_registry=runtime.projects,
            provider_registry=runtime.providers,
        )
        shell = CommandInterface(context, runtime.application_service)
        shell.run()


if __name__ == "__main__":
    main()
