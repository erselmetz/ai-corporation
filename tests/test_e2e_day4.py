from app.agents import Agent, AgentRegistry
from app.providers import OllamaProvider, ProviderRegistry
from app.orchestrator import Orchestrator, TaskRegistry, ProjectRegistry, Project
from app.database import initialize_database

def test_e2e_provider_model_flow():
    # Setup
    initialize_database()
    
    agent_registry = AgentRegistry()
    provider_registry = ProviderRegistry()
    task_registry = TaskRegistry()
    projects = ProjectRegistry()
    
    # Create Project (handle existing)
    project_id = "PROJ-VERIFY"
    if not projects.exists(project_id):
        projects.register(Project(
            id=project_id,
            name="Verification Project",
            description="E2E Test Project"
        ))
    
    # Provider
    ollama = OllamaProvider()
    provider_registry.register("ollama", ollama)
    
    # Agent
    agent_id = "verify_agent"
    agent = Agent(
        id=agent_id,
        name="Verification Agent",
        role="Tester",
        provider="ollama",
        model="llama3.2:3b",
    )
    agent_registry.register(agent)
    
    # Orchestrator
    orchestrator = Orchestrator(
        agents=agent_registry,
        providers=provider_registry,
        tasks=task_registry,
        projects=projects,
    )
    
    # Task - use a unique ID for each run to avoid "already registered" errors
    import uuid
    task_id = f"VERIFY-{uuid.uuid4().hex[:6].upper()}"
    task_title = "E2E Verification"
    task_desc = "Verify the full provider/model flow by saying hello."
    
    # Use create_task but we must ensure we don't conflict.
    # create_task internally generates a UUID ID.
    task = orchestrator.create_task(
        title=task_title,
        description=task_desc,
        project_id=project_id,
        agent_id=agent_id
    )
    
    print(f"Starting Task: {task.id} ({task.title})")
    
    # Execute
    executed_task = orchestrator.execute_task(task)
    
    print(f"Task Status: {executed_task.status}")
    print(f"Task Result: {executed_task.result}")
    
    # Verifications
    assert executed_task.status == "completed", f"Task should be completed, got {executed_task.status}. Error: {executed_task.error}"
    assert executed_task.result is not None, "Task result should not be None"
    
    # Verify persistence via TaskRegistry
    persisted_task = task_registry.get(task.id)
    assert persisted_task.status == "completed", "Task status should be persisted as completed"
    assert persisted_task.result == executed_task.result, "Task result should be persisted"
    
    print("\nVerification successful!")

if __name__ == "__main__":
    try:
        test_e2e_provider_model_flow()
    except Exception as e:
        print(f"\nVerification failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
