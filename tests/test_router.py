from uuid import uuid4
import pytest
from app.agents import Agent, AgentRegistry, Employee, EmployeeRegistry
from app.orchestrator import Orchestrator, TaskRegistry, ProjectRegistry
from app.orchestrator.task import Task
from app.orchestrator.project import Project
from app.orchestrator.router import RoutingError

@pytest.fixture
def setup_corp():
    agent_reg = AgentRegistry()
    emp_reg = EmployeeRegistry()
    task_reg = TaskRegistry()
    proj_reg = ProjectRegistry()
    
    # Project for tasks
    proj = Project(id=f"proj-{uuid4().hex[:4]}", name="Test Project", description="Desc", status="active")
    proj_reg.register(proj)
    
    # Agents
    research_agent = Agent(id="agent-res", name="ResAgent", role="Researcher", provider="p1", model="m1", capabilities=["research"])
    dev_agent = Agent(id="agent-dev", name="DevAgent", role="Developer", provider="p1", model="m1", capabilities=["coding"])
    agent_reg.register(research_agent)
    agent_reg.register(dev_agent)
    
    # Employees
    res_emp = Employee(id="emp-res", name="Alice", role="Researcher")
    res_emp.assign_agent(research_agent)
    emp_reg.register(res_emp)
    
    dev_emp = Employee(id="emp-dev", name="Bob", role="Developer")
    dev_emp.assign_agent(dev_agent)
    emp_reg.register(dev_emp)
    
    # Mock provider registry to avoid actual AI calls
    class MockProviderRegistry:
        def get(self, id):
            return MockProvider()
    
    class MockProvider:
        def generate(self, model, prompt):
            return f"Response from {model} to {prompt}"
            
    provider_reg = MockProviderRegistry()
    
    orch = Orchestrator(agent_reg, provider_reg, task_reg, proj_reg, emp_reg)
    
    return orch, agent_reg, emp_reg, task_reg, proj_reg

def test_explicit_agent_preserved(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    task = orch.create_task("T1", "Desc 1", "proj-1", agent_id="agent-dev")
    
    # Try to route via role "Researcher", but explicit agent should win
    result_task = orch.execute_task(task, role="Researcher")
    
    assert result_task.assigned_agent == "agent-dev"
    assert result_task.status == "completed"

def test_route_by_role(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    task = orch.create_task("T2", "Desc 2", "proj-1")
    
    # Route by role "Researcher"
    result_task = orch.execute_task(task, role="Researcher")
    
    assert result_task.assigned_agent == "agent-res"
    assert result_task.status == "completed"

def test_route_by_capability(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    task = orch.create_task("T3", "Desc 3", "proj-1")
    
    # Route by capability "coding"
    result_task = orch.execute_task(task, capability="coding")
    
    assert result_task.assigned_agent == "agent-dev"
    assert result_task.status == "completed"

def test_no_matching_agent_error(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    task = orch.create_task("T4", "Desc 4", "proj-1")
    
    # Route by non-existent role and capability
    result_task = orch.execute_task(task, role="UnknownRole", capability="UnknownCap")
    
    assert result_task.status == "failed"
    assert "No suitable agent found" in result_task.error

def test_backward_compatibility_run_agent(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    # run_agent should still work regardless of routing
    res = orch.run_agent("agent-res", "Hello")
    assert "Response from m1 to Hello" in res

def test_backward_compatibility_run_employee(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    emp = emp_reg.get("emp-res")
    res = orch.run_employee(emp, "Hello")
    assert "Response from m1 to Hello" in res

def test_backward_compatibility_execute_task_explicit(setup_corp):
    orch, agent_reg, emp_reg, task_reg, proj_reg = setup_corp
    task = orch.create_task("T5", "Desc 5", "proj-1", agent_id="agent-res")
    # execute_task without role/cap should still work if agent is assigned
    result_task = orch.execute_task(task)
    assert result_task.status == "completed"
    assert result_task.assigned_agent == "agent-res"
