from .models import ClientRequest
from app.orchestrator import Orchestrator
from app.orchestrator.task import Task

class BusinessLayer:
    """
    The Business Layer acts as the gateway for external ClientRequests,
    translating them into internal Corporation Tasks.
    """
    def __init__(self, orchestrator: Orchestrator):
        self.orchestrator = orchestrator

    def process_request(
        self, 
        request: ClientRequest, 
        project_id: str, 
        agent_id: str | None = None
    ) -> Task:
        """
        Translates a ClientRequest into an internal Task via the Orchestrator.
        """
        if not isinstance(request, ClientRequest):
            raise TypeError("Only ClientRequest instances can be processed")

        return self.orchestrator.create_task(
            title=request.title,
            description=request.description,
            project_id=project_id,
            agent_id=agent_id
        )
