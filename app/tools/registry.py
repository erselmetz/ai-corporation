from .base import Tool

class ToolRegistry:
    """
    Registry for managing available tools in the Corporation.
    """
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Registers a tool in the registry."""
        if not isinstance(tool, Tool):
            raise TypeError("Only Tool instances can be registered")
        
        if tool.id in self._tools:
            raise ValueError(f"Tool already registered: {tool.id}")
            
        self._tools[tool.id] = tool

    def get(self, tool_id: str) -> Tool:
        """Retrieves a tool by its ID."""
        try:
            return self._tools[tool_id]
        except KeyError:
            raise ValueError(f"Tool not found: {tool_id}")

    def exists(self, tool_id: str) -> bool:
        """Checks if a tool exists in the registry."""
        return tool_id in self._tools

    def all(self) -> list[Tool]:
        """Returns all registered tools."""
        return list(self._tools.values())
