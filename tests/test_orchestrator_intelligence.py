from app.agents import Employee, Agent, AgentRegistry
from app.providers import OllamaProvider, ProviderRegistry
from app.orchestrator import Orchestrator, TaskRegistry, ProjectRegistry, Project
from app.database import initialize_database

def test_orchestrator_run_employee():
    # Setup
    initialize_database()
    agent_registry = AgentRegistry()
    provider_registry = ProviderRegistry()
    task_registry = TaskRegistry()
    projects = ProjectRegistry()
    
    # Provider
    ollama = OllamaProvider()
    provider_registry.register("ollama", ollama)
    
    # Agent
    agent = Agent(
        id="tech_agent_1",
        name="Tech Agent 1",
        role="Executor",
        provider="ollama",
        model="llama3.2:3b",
    )
    agent_registry.register(agent)
    
    # Employee
    employee = Employee(
        id="emp_1",
        name="John AI",
        role="Junior Developer",
        responsibilities=["Write code"],
        agent=agent
    )
    
    orchestrator = Orchestrator(
        agents=agent_registry,
        providers=provider_registry,
        tasks=task_registry,
        projects=projects,
    )
    
    # Execute via employee
    result = orchestrator.run_employee(employee, "Say hello")
    assert result is not None
    assert len(result) > 0

def test_orchestrator_run_employee_no_agent():
    initialize_database()
    agent_registry = AgentRegistry()
    provider_registry = ProviderRegistry()
    task_registry = TaskRegistry()
    projects = ProjectRegistry()
    
    employee = Employee(
        id="emp_no_agent",
        name="Agentless AI",
        role="Trainee",
        responsibilities=["Learning"],
        agent=None
    )
    
    orchestrator = Orchestrator(
        agents=agent_registry,
        providers=provider_registry,
        tasks=task_registry,
        projects=projects,
    )
    
    try:
        orchestrator.run_employee(employee, "Say hello")
        raise AssertionError("Should have raised RuntimeError for employee without agent")
    except RuntimeError as e:
        assert "Employee 'Agentless AI' has no assigned agent" in str(e)

def test_backward_compatibility():
    # Ensure run_agent still works
    initialize_database()
    agent_registry = AgentRegistry()
    provider_registry = ProviderRegistry()
    task_registry = TaskRegistry()
    projects = ProjectRegistry()
    
    ollama = OllamaProvider()
    provider_registry.register("ollama", ollama)
    
    agent = Agent(
        id="tech_agent_1",
        name="Tech Agent 1",
        role="Executor",
        provider="ollama",
        model="llama3.2:3b",
    )
    agent_registry.register(agent)
    
    orchestrator = Orchestrator(
        agents=agent_registry,
        providers=provider_registry,
        tasks=task_registry,
        projects=projects,
    )
    
    result = orchestrator.run_agent("tech_agent_1", "Say hello")
    assert result is not None
    assert len(result) > 0

if __name__ == "__main__":
    # Simple runner for non-pytest environments
    try:
        test_orchestrator_run_employee()
        print("test_orchestrator_run_employee passed")
        
        # This one uses pytest.raises, so we call it via pytest or wrap it
        try:
            test_orchestrator_run_employee_no_agent()
            print("test_orchestrator_run_employee_no_agent passed")
        except Exception as e:
            print(f"test_orchestrator_run_employee_no_agent failed with unexpected error: {e}")
                
        test_backward_compatibility()
        print("test_backward_compatibility passed")
        
        print("\nOrchestrator Intelligence tests passed!")
    except Exception as e:
        print(f"\nTests failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
