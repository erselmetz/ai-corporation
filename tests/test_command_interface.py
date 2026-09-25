import pytest
from unittest.mock import MagicMock, patch
from app.interface.command import CommandInterface, CorporationContext
from app.orchestrator import Orchestrator, TaskRegistry, ProjectRegistry
from app.agents import AgentRegistry, EmployeeRegistry
from app.corporation import Corporation
from app.node import Node
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
    
    return CorporationContext(
        corp=corp,
        node=node,
        orchestrator=orch,
        agent_registry=agent_reg,
        employee_registry=emp_reg,
        task_registry=task_reg,
        project_registry=proj_reg
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
    mock_task = MagicMock(spec=Task)
    mock_task.id = "TASK-123"
    mock_task.title = "Test Task"
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
    mock_dry_result.__str__.return_value = "DRY RUN RESULT: Ready"
    mock_ctx.orchestrator.execute_task.return_value = mock_dry_result
    
    with patch('builtins.print') as mock_print:
        interface.handle_command("dry-run TASK-123")
        mock_ctx.orchestrator.execute_task.assert_called_once_with(mock_task, dry_run=True)
        mock_print.assert_any_call("\nDRY RUN RESULT: Ready")

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
