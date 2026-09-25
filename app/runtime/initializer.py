from typing import Optional
from .models import RuntimeContext
from app.corporation import CorporationRegistry
from app.node import NodeRegistry
from .manager import RuntimeContextManager

class RuntimeInitializer:
    """
    Handles the initialization of the Corporation's runtime identity.
    """
    def __init__(
        self, 
        corporation_registry: CorporationRegistry, 
        node_registry: NodeRegistry, 
        context: RuntimeContext
    ):
        self.corporation_registry = corporation_registry
        self.node_registry = node_registry
        self.context = context
        self._validated = False

    def initialize(self) -> RuntimeContext:
        """
        Validates the provided runtime context against registries and returns it.
        """
        manager = RuntimeContextManager(self.corporation_registry, self.node_registry)
        if manager.validate_context(self.context):
            self._validated = True
            return self.context
        
        raise RuntimeError("Runtime context validation failed")

    @property
    def is_initialized(self) -> bool:
        return self._validated
