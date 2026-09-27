import pytest

from app.agents import Agent, AgentRegistry, Employee, EmployeeRegistry
from app.database import get_connection, initialize_database
from app.orchestrator import Orchestrator, Project, ProjectRegistry, Task, TaskRegistry
from app.orchestrator.dry_run import DryRunResult
from app.orchestrator.router import RoutingError
from app.providers import ProviderRegistry


@pytest.fixture
def routing_context():
    agent_registry = AgentRegistry()
    worker = Agent(
        id="local_worker",
        name="Local Worker",
        role="Local AI Worker",
        provider="ollama",
        model="llama3.2:3b",
        capabilities=["summarization"],
    )
    agent_registry.register(worker)

    employee_registry = EmployeeRegistry()
    employee = Employee(
        id="local_employee",
        name="Local Worker",
        role="Local AI Worker",
        agent=worker,
    )
    employee_registry.register(employee)

    project_registry = ProjectRegistry()
    project_registry.register(
        Project(id="test-project", name="Test Project")
    )
    task_registry = TaskRegistry()
    orchestrator = Orchestrator(
        agents=agent_registry,
        providers=ProviderRegistry(),
        tasks=task_registry,
        projects=project_registry,
        employees=employee_registry,
    )
    return (
        agent_registry,
        employee_registry,
        project_registry,
        task_registry,
        orchestrator,
    )


def test_task_routing_fields_default_to_none():
    task = Task(id="task-default", title="Default", description="No route")

    assert task.assigned_agent is None
    assert task.required_role is None
    assert task.required_capability is None


@pytest.mark.parametrize(
    ("routing_argument", "routing_value", "expected_route"),
    [
        ("role", "Local AI Worker", "employee_role"),
        ("capability", "summarization", "capability"),
    ],
)
def test_routing_requirement_persists_and_routes_after_registry_reload(
    routing_context, routing_argument, routing_value, expected_route
):
    agent_registry, employee_registry, _, _, orchestrator = routing_context
    task = orchestrator.create_task(
        title="Persisted routing",
        description="Route after reload",
        project_id="test-project",
        **{routing_argument: routing_value},
    )

    assert task.assigned_agent is None
    assert task.required_role == (
        routing_value if routing_argument == "role" else None
    )
    assert task.required_capability == (
        routing_value if routing_argument == "capability" else None
    )

    reloaded_tasks = TaskRegistry()
    reloaded_projects = ProjectRegistry()
    reloaded_task = reloaded_tasks.get(task.id)
    assert reloaded_task.assigned_agent is None
    assert reloaded_task.required_role == task.required_role
    assert reloaded_task.required_capability == task.required_capability

    reloaded_orchestrator = Orchestrator(
        agents=agent_registry,
        providers=ProviderRegistry(),
        tasks=reloaded_tasks,
        projects=reloaded_projects,
        employees=employee_registry,
    )
    result = reloaded_orchestrator.execute_task(reloaded_task, dry_run=True)

    assert isinstance(result, DryRunResult)
    assert result.selected_agent.id == "local_worker"
    assert result.routing_method == expected_route
    assert result.provider == "ollama"
    assert result.model == "llama3.2:3b"
    assert reloaded_tasks.get(task.id).assigned_agent is None
    assert reloaded_tasks.get(task.id).status == task.status


def test_explicit_agent_persists_as_explicit_routing(routing_context):
    _, _, _, _, orchestrator = routing_context
    task = orchestrator.create_task(
        "Explicit", "Explicit assignment", "test-project", agent_id="local_worker"
    )

    reloaded_task = TaskRegistry().get(task.id)
    assert reloaded_task.assigned_agent == "local_worker"
    assert reloaded_task.required_role is None
    assert reloaded_task.required_capability is None

    result = orchestrator.execute_task(reloaded_task, dry_run=True)
    assert isinstance(result, DryRunResult)
    assert result.routing_method == "explicit_agent"


def test_unrouted_task_errors_and_dry_run_override_is_non_mutating(routing_context):
    _, _, _, task_registry, orchestrator = routing_context
    task = orchestrator.create_task(
        "Unrouted", "No requirement", "test-project"
    )

    with pytest.raises(RoutingError, match="No suitable agent found"):
        orchestrator.execute_task(task, dry_run=True)

    result = orchestrator.execute_task(
        task, dry_run=True, capability="summarization"
    )
    assert isinstance(result, DryRunResult)
    assert result.routing_method == "capability"
    assert task_registry.get(task.id).assigned_agent is None
    assert task_registry.get(task.id).required_role is None
    assert task_registry.get(task.id).required_capability is None


def test_task_registry_update_persists_routing_requirements(routing_context):
    _, _, _, task_registry, orchestrator = routing_context
    task = orchestrator.create_task("Update", "Update routing", "test-project")
    task.required_role = "Local AI Worker"
    task_registry.update(task)

    reloaded = TaskRegistry().get(task.id)
    assert reloaded.assigned_agent is None
    assert reloaded.required_role == "Local AI Worker"
    assert reloaded.required_capability is None


def test_existing_tasks_migrate_with_null_routing_requirements():
    connection = get_connection()
    try:
        connection.execute("DROP TABLE tasks")
        connection.execute(
            """
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                assigned_agent TEXT,
                status TEXT NOT NULL,
                result TEXT,
                error TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO tasks (
                id, title, description, assigned_agent, status, result, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("legacy-task", "Legacy", "Existing task", "old-agent", "pending", None, None),
        )
        connection.commit()
    finally:
        connection.close()

    initialize_database()
    initialize_database()

    migrated = TaskRegistry().get("legacy-task")
    assert migrated.assigned_agent == "old-agent"
    assert migrated.required_role is None
    assert migrated.required_capability is None

    connection = get_connection()
    try:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
        }
        assert "required_role" in columns
        assert "required_capability" in columns
        assert connection.execute(
            "SELECT COUNT(*) FROM tasks WHERE id = 'legacy-task'"
        ).fetchone()[0] == 1
    finally:
        connection.close()


def test_create_task_rejects_empty_or_conflicting_routing(routing_context):
    _, _, _, _, orchestrator = routing_context

    with pytest.raises(ValueError, match="mutually exclusive"):
        orchestrator.create_task(
            "Conflicting",
            "Conflicting route",
            "test-project",
            role="Local AI Worker",
            capability="summarization",
        )

    with pytest.raises(ValueError, match="cannot be empty"):
        orchestrator.create_task(
            "Empty", "Empty role", "test-project", role=" "
        )
