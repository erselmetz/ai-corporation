from .models import Node
from app.corporation import CorporationRegistry

class NodeRegistry:
    """
    Registry for managing Node identities.
    """
    def __init__(self, corporation_registry: CorporationRegistry | None = None):
        self._nodes: dict[str, Node] = {}
        self.corporation_registry = corporation_registry

    def register(self, node: Node) -> None:
        """Registers a node identity."""
        if not isinstance(node, Node):
            raise TypeError("Only Node instances can be registered")
        
        if node.id in self._nodes:
            raise ValueError(f"Node already registered: {node.id}")
            
        if self.corporation_registry and not self.corporation_registry.exists(node.corporation_id):
            raise ValueError(f"Cannot register node: Corporation {node.corporation_id} does not exist")

        self._nodes[node.id] = node

    def get(self, node_id: str) -> Node:
        """Retrieves a node by its ID."""
        try:
            return self._nodes[node_id]
        except KeyError:
            raise ValueError(f"Node not found: {node_id}")

    def exists(self, node_id: str) -> bool:
        """Checks if a node identity exists."""
        return node_id in self._nodes

    def all(self) -> list[Node]:
        """Returns all registered nodes."""
        return list(self._nodes.values())

    def find_by_corporation(self, corporation_id: str) -> list[Node]:
        """Retrieves all nodes belonging to a specific corporation."""
        return [node for node in self._nodes.values() if node.corporation_id == corporation_id]
