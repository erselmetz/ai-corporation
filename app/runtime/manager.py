from .models import RuntimeContext
from app.corporation import CorporationRegistry
from app.node import NodeRegistry

class RuntimeContextManager:
    """
    Manages and validates the current runtime context of the AI Corporation.
    """
    def __init__(
        self, 
        corporation_registry: CorporationRegistry, 
        node_registry: NodeRegistry
    ):
        self.corporation_registry = corporation_registry
        self.node_registry = node_registry

    def validate_context(self, context: RuntimeContext) -> bool:
        """
        Validates the runtime context against the registries.
        
        Ensures:
        1. The Corporation exists.
        2. The Node exists.
        3. The Node belongs to the specified Corporation.
        """
        if not self.corporation_registry.exists(context.corporation_id):
            raise ValueError(f"Corporation {context.corporation_id} not found in registry")
            
        if not self.node_registry.exists(context.node_id):
            raise ValueError(f"Node {context.node_id} not found in registry")
            
        node = self.node_registry.get(context.node_id)
        if node.corporation_id != context.corporation_id:
            raise ValueError(
                f"Node {node.id} does not belong to Corporation {context.corporation_id} "
                f"(belongs to {node.corporation_id})"
            )
            
        return True
