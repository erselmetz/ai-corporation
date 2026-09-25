from app.client import ClientRequest, BusinessLayer
from app.orchestrator import Orchestrator
from app.agents import Agent, AgentRegistry
from app.providers import OllamaProvider, ProviderRegistry
from app.orchestrator import TaskRegistry, ProjectRegistry
from app.database import initialize_database

def test_client_request_creation():
    req = ClientRequest(id="req_1", title="Help me", description="I need some code")
    assert req.id == "req_1"
    assert req.title == "Help me"
    assert req.description == "I need some code"

def test_client_request_validation():
    # Simple verification without pytest for the minimal runner
    try:
        ClientRequest(id="", title="T", description="D")
        raise AssertionError("Should have raised ValueError for empty id")
    except ValueError as e:
        assert "Client request id cannot be empty" in str(e)

    try:
        ClientRequest(id="  ", title="T", description="D")
        raise AssertionError("Should have raised ValueError for whitespace id")
    except ValueError as e:
        assert "Client request id cannot be empty" in str(e)

    try:
        ClientRequest(id="I", title="", description="D")
        raise AssertionError("Should have raised ValueError for empty title")
    except ValueError as e:
        assert "Client request title cannot be empty" in str(e)

    try:
        ClientRequest(id="I", title=" ", description="D")
        raise AssertionError("Should have raised ValueError for whitespace title")
    except ValueError as e:
        assert "Client request title cannot be empty" in str(e)

    try:
        ClientRequest(id="I", title="T", description="")
        raise AssertionError("Should have raised ValueError for empty description")
    except ValueError as e:
        assert "Client request description cannot be empty" in str(e)

    try:
        ClientRequest(id="I", title="T", description="  ")
        raise AssertionError("Should have raised ValueError for whitespace description")
    except ValueError as e:
        assert "Client request description cannot be empty" in str(e)

def test_business_layer_translation():
    initialize_database()
    agent_registry = AgentRegistry()
    provider_registry = ProviderRegistry()
    task_registry = TaskRegistry()
    projects = ProjectRegistry()
    
    # Setup required for orchestrator
    ollama = OllamaProvider()
    provider_registry.register("ollama", ollama)
    
    # Setup project
    from app.orchestrator.project import Project
    project_id = "PROJ-1"
    if not projects.exists(project_id):
        projects.register(Project(id=project_id, name="Test Project"))
    
    orchestrator = Orchestrator(
        agents=agent_registry,
        providers=provider_registry,
        tasks=task_registry,
        projects=projects,
    )
    
    business_layer = BusinessLayer(orchestrator)
    
    # Valid translation
    request = ClientRequest(id="req_1", title="Business Title", description="Business Desc")
    task = business_layer.process_request(
        request=request,
        project_id=project_id,
        agent_id="some_agent"
    )
    assert task.title == request.title
    assert task.description == request.description
    assert task.project_id == project_id
    assert task.assigned_agent == "some_agent"
    
    # Invalid input to business layer
    try:
        business_layer.process_request(request="not a request", project_id=project_id)
        raise AssertionError("Should have raised TypeError for invalid request input")
    except TypeError as e:
        assert "Only ClientRequest instances can be processed" in str(e)

if __name__ == "__main__":
    try:
        test_client_request_creation()
        test_client_request_validation()
        test_business_layer_translation()
        print("Client/Business layer tests passed!")
    except Exception as e:
        print(f"Tests failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
