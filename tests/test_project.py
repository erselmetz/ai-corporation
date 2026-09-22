from app.orchestrator import Project, ProjectRegistry


def main():
    projects = ProjectRegistry()

    if not projects.exists("PROJECT-001"):
        project = Project(
            id="PROJECT-001",
            name="AI Corporation Internal",
            description="Internal AI Corporation development project",
        )

        projects.register(project)

    loaded = projects.get("PROJECT-001")

    print(f"🏢 Project: {loaded.name}")
    print(f"   ID: {loaded.id}")
    print(f"   Status: {loaded.status}")


if __name__ == "__main__":
    main()