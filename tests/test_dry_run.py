import pytest
from uuid import uuid4
from unittest.mock import MagicMock, patch
from app.agents import Agent, AgentRegistry, Employee, EmployeeRegistry
from app.orchestrator import Orchestrator, TaskRegistry, ProjectRegistry
from app.orchestrator.task import Task
from app.orchestrator.project import Project
from app.orchestrator.router import RoutingError
from app.orchestrator.dry_run import DryRunResult

@pytest.fixture
def setup_corp():
    agent_reg = AgentRegistry()
    emp_reg = EmployeeRegistry()
    task_reg = TaskRegistry()
    proj_reg = ProjectRegistry()
    
    # Project for tasks
    proj_id = f"proj-{uuid4().hex[:4]}"
    proj = Project(id=proj_id, name="Test Project", description="Desc", status="active")
    proj_reg.register(proj)
    
    research_agent = Agent(id="agent-res", name="ResAgent", role="Researcher", provider="p1", model="m1", capabilities=["research"])
    dev_agent = Agent(id="agent-dev", name="DevAgent", role="Developer", provider="p1", model="m1", capabilities=["coding"])
    agent_reg.register(research_agent)
    agent_reg.register(dev_agent)
    
    res_emp = Employee(id="emp-res", name="Alice", role="Researcher")
    res_emp.assign_agent(research_agent)
    emp_reg.register(res_emp)
    
    dev_emp = Employee(id="emp-dev", name="Bob", role="Developer")
    dev_emp.assign_agent(dev_agent)
    emp_reg.register(dev_emp)
    
    class MockProviderRegistry:
        def get(self, id):
            return MockProvider()
    
    class MockProvider:
        def generate(self, model, prompt):
            return f"Real Response from {model}"
            
    provider_reg = MockProviderRegistry()
    orch = Orchestrator(agent_reg, provider_reg, task_reg, proj_reg, emp_reg)
    
    return orch, agent_reg, emp_reg, task_reg, proj_reg

def test_dry_run_explicit_agent(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    proj = proj_reg.all()[0]
    task = orch.create_task("T1", "Desc 1", proj.id, agent_id="agent-dev")
    
    result = orch.execute_task(task, dry_run=True)
    
    assert isinstance(result, DryRunResult)
    assert result.selected_agent.id == "agent-dev"
    assert result.routing_method == "explicit_agent"
    assert result.status == "ready"

def test_dry_run_role_routing(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    proj = proj_reg.all()[0]
    task = orch.create_task("T2", "Desc 2", proj.id)
    
    result = orch.execute_task(task, role="Researcher", dry_run=True)
    
    assert isinstance(result, DryRunResult)
    assert result.selected_agent.id == "agent-res"
    assert result.selected_employee.id == "emp-res"
    assert result.routing_method == "employee_role"

def test_dry_run_capability_routing(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    proj = proj_reg.all()[0]
    task = orch.create_task("T3", "Desc 3", proj.id)
    
    result = orch.execute_task(task, capability="coding", dry_run=True)
    
    assert isinstance(result, DryRunResult)
    assert result.selected_agent.id == "agent-dev"
    assert result.routing_method == "capability"

def test_dry_run_invalid_explicit_agent(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    proj = proj_reg.all()[0]
    task = orch.create_task("T4", "Desc 4", proj.id, agent_id="invalid-agent")
    
    with pytest.raises(RoutingError):
        orch.execute_task(task, dry_run=True)

def test_dry_run_employee_without_agent(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    # Create employee with no agent
    lazy_emp = Employee(id="emp-lazy", name="Lazy", role="Slacker")
    emp_reg.register(lazy_emp)
    
    proj = proj_reg.all()[0]
    task = orch.create_task("T5", "Desc 5", proj.id)
    
    with pytest.raises(RoutingError):
        orch.execute_task(task, role="Slacker", dry_run=True)

def test_dry_run_no_matching_route(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    proj = proj_reg.all()[0]
    task = orch.create_task("T6", "Desc 6", proj.id)
    
    with pytest.raises(RoutingError):
        orch.execute_task(task, role="Ghost", capability="Magic", dry_run=True)

def test_dry_run_prevents_ai_call(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    proj = proj_reg.all()[0]
    task = orch.create_task("T7", "Desc 7", proj.id)
    
    # Patch run_agent to see if it's called
    with patch.object(Orchestrator, 'run_agent') as mock_run:
        orch.execute_task(task, role="Researcher", dry_run=True)
        mock_run.assert_not_called()

def test_normal_execution_calls_ai(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    proj = proj_reg.all()[0]
    task = orch.create_task("T8", "Desc 8", proj.id)
    
    with patch.object(Orchestrator, 'run_agent', return_value="Real Response") as mock_run:
        orch.execute_task(task, role="Researcher", dry_run=False)
        mock_run.assert_called_once()

def test_backward_compatibility_execute_task(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    proj = proj_reg.all()[0]
    task = orch.create_task("T9", "Desc 9", proj.id, agent_id="agent-res")
    
    # Existing call without dry_run should work as before
    result = orch.execute_task(task)
    
    assert isinstance(result, Task)
    assert result.status == "completed"
