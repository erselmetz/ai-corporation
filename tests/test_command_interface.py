import pytest
from unittest.mock import MagicMock, patch
from app.interface.command import CommandInterface, CorporationContext
from app.orchestrator import Orchestrator, TaskRegistry, ProjectRegistry
from app.agents import Agent, AgentRegistry, EmployeeRegistry
from app.corporation import Corporation
from app.node import Node
from app.providers import ProviderRegistry
from app.orchestrator.dry_run import DryRunResult
from app.orchestrator.task import Task

@pytest.fixture
def mock_ctx():
    corp = MagicMock(spec=Corporation)
    corp.name = "Test Corp"
    corp.id = "corp-1"
    
    node = MagicMock(spec=Node)
    node.name = "Test Node"
    node.id = "node-1"
    
    orch = MagicMock(spec=Orchestrator)
    agent_reg = MagicMock(spec=AgentRegistry)
    emp_reg = MagicMock(spec=EmployeeRegistry)
    task_reg = MagicMock(spec=TaskRegistry)
    proj_reg = MagicMock(spec=ProjectRegistry)
    provider_reg = MagicMock(spec=ProviderRegistry)
    provider_reg.all.return_value = {}
    orch.agents = agent_reg
    orch.employees = emp_reg
    orch.tasks = task_reg
    orch.projects = proj_reg
    orch.providers = provider_reg
    
    return CorporationContext(
        corp=corp,
        node=node,
        orchestrator=orch,
        agent_registry=agent_reg,
        employee_registry=emp_reg,
        task_registry=task_reg,
        project_registry=proj_reg,
        provider_registry=provider_reg
    )

def test_help_command(mock_ctx):
    interface = CommandInterface(mock_ctx)
    with patch('builtins.print') as mock_print:
        interface.handle_command("help")
        # Check if a few key commands are mentioned
        printed_text = "".join([str(call.args[0]) for call in mock_print.call_args_list if call.args])
        assert "help" in printed_text
        assert "status" in printed_text
        assert "employees" in printed_text
        assert "agents" in printed_text
        assert "task" in printed_text
        assert "dry-run" in printed_text

def test_status_command(mock_ctx):
    interface = CommandInterface(mock_ctx)
    with patch('builtins.print') as mock_print:
        interface.handle_command("status")
        printed_text = "".join([call.args[0] for call in mock_print.call_args_list])
        assert "Test Corp" in printed_text
        assert "Test Node" in printed_text

def test_employees_command_empty(mock_ctx):
    mock_ctx.employee_registry.all.return_value = []
    interface = CommandInterface(mock_ctx)
    with patch('builtins.print') as mock_print:
        interface.handle_command("employees")
        mock_print.assert_any_call("No employees registered.")

def test_agents_command_empty(mock_ctx):
    mock_ctx.agent_registry.all.return_value = []
    interface = CommandInterface(mock_ctx)
    with patch('builtins.print') as mock_print:
        interface.handle_command("agents")
        mock_print.assert_any_call("No agents registered.")

def test_task_creation_command(mock_ctx):
    interface = CommandInterface(mock_ctx)
    mock_task = Task(
        id="TASK-123",
        title="Test Task",
        description="Create a new task",
    )
    mock_ctx.orchestrator.create_task.return_value = mock_task
    mock_ctx.project_registry.all.return_value = []
    mock_ctx.project_registry.exists.return_value = False
    
    with patch('builtins.print') as mock_print:
        interface.handle_command("task Create a new task")
        mock_ctx.orchestrator.create_task.assert_called_once()
        mock_print.assert_any_call("Task created: TASK-123 - Test Task")

def test_dry_run_command(mock_ctx):
    interface = CommandInterface(mock_ctx)
    mock_task = MagicMock(spec=Task)
    mock_task.id = "TASK-123"
    mock_ctx.task_registry.get.return_value = mock_task
    mock_dry_result = MagicMock(spec=DryRunResult)
    mock_dry_result.task_id = "TASK-123"
    mock_dry_result.task_title = "Task title"
    mock_dry_result.task_description = "Task description"
    mock_dry_result.selected_agent = Agent(
        id="agent-1",
        name="Worker",
        role="Worker role",
        provider="ollama",
        model="test-model",
    )
    mock_dry_result.selected_employee = None
    mock_dry_result.provider = "ollama"
    mock_dry_result.model = "test-model"
    mock_dry_result.routing_method = "explicit_agent"
    mock_dry_result.status = "ready"
    mock_ctx.orchestrator.execute_task.return_value = mock_dry_result

    with patch('builtins.print') as mock_print:
        interface.handle_command("dry-run TASK-123")
        mock_ctx.orchestrator.execute_task.assert_called_once_with(mock_task, dry_run=True)
        mock_print.assert_any_call(
            "\nDRY RUN RESULT\n"
            "Task: [TASK-123] Task title\n"
            "Description: Task description\n"
            "Employee: N/A\n"
            "Agent: Worker (Worker role)\n"
            "Provider: ollama\n"
            "Model: test-model\n"
            "Route: explicit_agent\n"
            "Status: ready"
        )

def test_unknown_command(mock_ctx):
    interface = CommandInterface(mock_ctx)
    with patch('builtins.print') as mock_print:
        interface.handle_command("unknown_cmd")
        mock_print.assert_any_call("Unknown command: unknown_cmd")

def test_empty_input(mock_ctx):
    interface = CommandInterface(mock_ctx)
    with patch('builtins.print') as mock_print:
        # The loop handles empty input by continuing, but we test handle_command with empty
        # though usually parts = user_input.split() handles it.
        # Let's verify handle_command doesn't crash.
        interface.handle_command("")
        # Nothing should be printed as it's an empty string and splitting fails or produces empty list

def test_invalid_task_id(mock_ctx):
    interface = CommandInterface(mock_ctx)
    mock_ctx.task_registry.get.side_effect = ValueError("Task not found")
    
    with patch('builtins.print') as mock_print:
        interface.handle_command("dry-run INVALID-ID")
        mock_print.assert_any_call("Error performing dry-run: Task not found")

def test_exit_command(mock_ctx):
    interface = CommandInterface(mock_ctx)
    interface.handle_command("exit")
    assert interface._running is False

def test_quit_command(mock_ctx):
    interface = CommandInterface(mock_ctx)
    interface.handle_command("quit")
    assert interface._running is False

def test_provider_list_empty(mock_ctx):
    mock_ctx.provider_registry.all.return_value = {}
    interface = CommandInterface(mock_ctx)
    with patch('builtins.print') as mock_print:
        interface.handle_command("provider list")
        mock_print.assert_any_call("No providers registered.")

def test_providers_command(mock_ctx):
    mock_ctx.provider_registry.all.return_value = {}
    interface = CommandInterface(mock_ctx)
    with patch('builtins.print') as mock_print:
        interface.handle_command("providers")
        mock_print.assert_any_call("No providers registered.")

def test_provider_add_command(mock_ctx):
    interface = CommandInterface(mock_ctx)
    with patch('builtins.print') as mock_print:
        interface.handle_command("provider add test_p TestProvider")
        mock_ctx.provider_registry.register.assert_called_once()
        mock_print.assert_any_call("Provider added: OllamaProvider (TestProvider)")

def test_model_set_command(mock_ctx):
    interface = CommandInterface(mock_ctx)
    mock_agent = MagicMock()
    mock_ctx.agent_registry.get.return_value = mock_agent
    mock_ctx.provider_registry.exists.return_value = True
    
    with patch('builtins.print') as mock_print:
        interface.handle_command("model set worker_1 ollama gemma4:26b")
        mock_ctx.agent_registry.get.assert_called_once_with("worker_1")
        mock_ctx.provider_registry.exists.assert_called_once_with("ollama")
        assert mock_agent.provider == "ollama"
        assert mock_agent.model == "gemma4:26b"
        mock_print.assert_any_call("Model updated for agent worker_1: ollama/gemma4:26b")

def test_task_creation_with_agent(mock_ctx):
    interface = CommandInterface(mock_ctx)
    mock_task = Task(
        id="TASK-001",
        title="Research AI",
        description="Research AI",
    )
    mock_ctx.orchestrator.create_task.return_value = mock_task
    mock_ctx.project_registry.all.return_value = []
    mock_ctx.project_registry.exists.return_value = False

    with patch('builtins.print') as mock_print:
        interface.handle_command('task "Research AI" --agent local_worker')
        mock_ctx.orchestrator.create_task.assert_called_once_with(
            title="Research AI",
            description="Research AI",
            project_id="default_proj",
            agent_id="local_worker"
        )
        mock_print.assert_any_call("Task created: TASK-001 - Research AI")

def test_task_creation_with_role(mock_ctx):
    interface = CommandInterface(mock_ctx)
    mock_task = Task(
        id="TASK-002",
        title="Handle Work",
        description="Handle Work",
    )
    mock_ctx.orchestrator.create_task.return_value = mock_task
    mock_ctx.project_registry.all.return_value = []
    mock_ctx.project_registry.exists.return_value = False

    with patch('builtins.print') as mock_print:
        interface.handle_command('task "Handle Work" --role "Local AI Worker"')
        mock_ctx.orchestrator.create_task.assert_called_once_with(
            title="Handle Work",
            description="Handle Work",
            project_id="default_proj",
            role="Local AI Worker"
        )
        mock_print.assert_any_call("Task created: TASK-002 - Handle Work")

def test_task_creation_with_capability(mock_ctx):
    interface = CommandInterface(mock_ctx)
    mock_task = Task(
        id="TASK-003",
        title="Summarize docs",
        description="Summarize docs",
    )
    mock_ctx.orchestrator.create_task.return_value = mock_task
    mock_ctx.project_registry.all.return_value = []
    mock_ctx.project_registry.exists.return_value = False

    with patch('builtins.print') as mock_print:
        interface.handle_command('task "Summarize docs" --capability summarization')
        mock_ctx.orchestrator.create_task.assert_called_once_with(
            title="Summarize docs",
            description="Summarize docs",
            project_id="default_proj",
            capability="summarization"
        )
        mock_print.assert_any_call("Task created: TASK-003 - Summarize docs")

def test_task_creation_missing_routing_value(mock_ctx):
    interface = CommandInterface(mock_ctx)
    for flag in ("--agent", "--role", "--capability"):
        with patch('builtins.print') as mock_print:
            interface.handle_command(f'task "test description" {flag}')
            mock_print.assert_any_call(f"Error: '{flag}' requires a value.")

def test_task_creation_multiple_routing_options_rejected(mock_ctx):
    interface = CommandInterface(mock_ctx)
    cases = [
        'task "test" --agent local_worker --role Developer',
        'task "test" --role Developer --capability coding',
        'task "test" --agent local_worker --capability coding',
    ]
    for cmd in cases:
        with patch('builtins.print') as mock_print:
            interface.handle_command(cmd)
            mock_print.assert_any_call("Error: Routing options (--agent, --role, --capability) are mutually exclusive.")

def test_task_creation_without_routing_preserves_behavior(mock_ctx):
    interface = CommandInterface(mock_ctx)
    mock_task = Task(
        id="TASK-004",
        title="Standard task",
        description="Standard task",
    )
    mock_ctx.orchestrator.create_task.return_value = mock_task
    mock_ctx.project_registry.all.return_value = []
    mock_ctx.project_registry.exists.return_value = False

    with patch('builtins.print') as mock_print:
        interface.handle_command('task "Standard task"')
        mock_ctx.orchestrator.create_task.assert_called_once_with(
            title="Standard task",
            description="Standard task",
            project_id="default_proj",
        )
        mock_print.assert_any_call("Task created: TASK-004 - Standard task")

def test_dry_run_with_agent(mock_ctx):
    interface = CommandInterface(mock_ctx)
    mock_task = MagicMock(spec=Task)
    mock_task.id = "TASK-100"
    mock_ctx.task_registry.get.return_value = mock_task
    mock_dry = MagicMock(spec=DryRunResult)
    mock_dry.task_id = "TASK-100"
    mock_dry.task_title = "Task title"
    mock_dry.task_description = "Task description"
    mock_dry.selected_agent = Agent(
        id="local_worker",
        name="Local Worker",
        role="Local AI Worker",
        provider="ollama",
        model="test-model",
    )
    mock_dry.selected_employee = None
    mock_dry.provider = "ollama"
    mock_dry.model = "test-model"
    mock_dry.routing_method = "explicit_agent"
    mock_dry.status = "ready"
    mock_ctx.orchestrator.execute_task.return_value = mock_dry

    with patch('builtins.print') as mock_print:
        interface.handle_command("dry-run TASK-100 --agent local_worker")
        mock_ctx.orchestrator.execute_task.assert_called_once_with(
            mock_task,
            dry_run=True,
            agent_id="local_worker"
        )
        mock_print.assert_any_call(
            "\nDRY RUN RESULT\n"
            "Task: [TASK-100] Task title\n"
            "Description: Task description\n"
            "Employee: N/A\n"
            "Agent: Local Worker (Local AI Worker)\n"
            "Provider: ollama\n"
            "Model: test-model\n"
            "Route: explicit_agent\n"
            "Status: ready"
        )

def test_dry_run_with_role(mock_ctx):
    interface = CommandInterface(mock_ctx)
    mock_task = MagicMock(spec=Task)
    mock_task.id = "TASK-101"
    mock_ctx.task_registry.get.return_value = mock_task
    mock_dry = MagicMock(spec=DryRunResult)
    mock_dry.task_id = "TASK-101"
    mock_dry.task_title = "Task title"
    mock_dry.task_description = "Task description"
    mock_dry.selected_agent = Agent(
        id="local_worker",
        name="Local Worker",
        role="Local AI Worker",
        provider="ollama",
        model="test-model",
    )
    mock_dry.selected_employee = None
    mock_dry.provider = "ollama"
    mock_dry.model = "test-model"
    mock_dry.routing_method = "employee_role"
    mock_dry.status = "ready"
    mock_ctx.orchestrator.execute_task.return_value = mock_dry

    with patch('builtins.print') as mock_print:
        interface.handle_command('dry-run TASK-101 --role "Local AI Worker"')
        mock_ctx.orchestrator.execute_task.assert_called_once_with(
            mock_task,
            dry_run=True,
            role="Local AI Worker"
        )
        mock_print.assert_any_call(
            "\nDRY RUN RESULT\n"
            "Task: [TASK-101] Task title\n"
            "Description: Task description\n"
            "Employee: N/A\n"
            "Agent: Local Worker (Local AI Worker)\n"
            "Provider: ollama\n"
            "Model: test-model\n"
            "Route: employee_role\n"
            "Status: ready"
        )

def test_dry_run_with_capability(mock_ctx):
    interface = CommandInterface(mock_ctx)
    mock_task = MagicMock(spec=Task)
    mock_task.id = "TASK-102"
    mock_ctx.task_registry.get.return_value = mock_task
    mock_dry = MagicMock(spec=DryRunResult)
    mock_dry.task_id = "TASK-102"
    mock_dry.task_title = "Task title"
    mock_dry.task_description = "Task description"
    mock_dry.selected_agent = Agent(
        id="local_worker",
        name="Local Worker",
        role="Local AI Worker",
        provider="ollama",
        model="test-model",
    )
    mock_dry.selected_employee = None
    mock_dry.provider = "ollama"
    mock_dry.model = "test-model"
    mock_dry.routing_method = "capability"
    mock_dry.status = "ready"
    mock_ctx.orchestrator.execute_task.return_value = mock_dry

    with patch('builtins.print') as mock_print:
        interface.handle_command("dry-run TASK-102 --capability summarization")
        mock_ctx.orchestrator.execute_task.assert_called_once_with(
            mock_task,
            dry_run=True,
            capability="summarization"
        )
        mock_print.assert_any_call(
            "\nDRY RUN RESULT\n"
            "Task: [TASK-102] Task title\n"
            "Description: Task description\n"
            "Employee: N/A\n"
            "Agent: Local Worker (Local AI Worker)\n"
            "Provider: ollama\n"
            "Model: test-model\n"
            "Route: capability\n"
            "Status: ready"
        )

def test_dry_run_missing_routing_value(mock_ctx):
    interface = CommandInterface(mock_ctx)
    for flag in ("--agent", "--role", "--capability"):
        with patch('builtins.print') as mock_print:
            interface.handle_command(f"dry-run TASK-103 {flag}")
            mock_print.assert_any_call(f"Error: '{flag}' requires a value.")

def test_dry_run_multiple_routing_options_rejected(mock_ctx):
    interface = CommandInterface(mock_ctx)
    cases = [
        "dry-run TASK-104 --agent local_worker --role Developer",
        "dry-run TASK-104 --role Developer --capability coding",
        "dry-run TASK-104 --agent local_worker --capability coding",
    ]
    for cmd in cases:
        with patch('builtins.print') as mock_print:
            interface.handle_command(cmd)
            mock_print.assert_any_call("Error: Routing options (--agent, --role, --capability) are mutually exclusive.")

def test_dry_run_invalid_task_id(mock_ctx):
    interface = CommandInterface(mock_ctx)
    mock_ctx.task_registry.get.side_effect = ValueError("Task not found: TASK-NONEXIST")

    with patch('builtins.print') as mock_print:
        interface.handle_command("dry-run TASK-NONEXIST")
        mock_print.assert_any_call("Error performing dry-run: Task not found: TASK-NONEXIST")

def test_dry_run_no_routing_information_routing_error(mock_ctx):
    interface = CommandInterface(mock_ctx)
    mock_task = MagicMock(spec=Task)
    mock_task.id = "TASK-UNROUTED"
    mock_ctx.task_registry.get.return_value = mock_task
    from app.orchestrator.router import RoutingError
    mock_ctx.orchestrator.execute_task.side_effect = RoutingError(
        "No suitable agent found for task 'TASK-UNROUTED'. Requested role: None, Requested capability: None"
    )

    with patch('builtins.print') as mock_print:
        interface.handle_command("dry-run TASK-UNROUTED")
        mock_print.assert_any_call(
            "Error performing dry-run: No suitable agent found for task 'TASK-UNROUTED'. Requested role: None, Requested capability: None"
        )
