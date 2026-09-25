from abc import ABC, abstractmethod

class Tool(ABC):
    """
    Abstract base class for a Tool.
    A Tool represents an executable capability that an AI Agent can use.
    """
    def __init__(self, tool_id: str, name: str, description: str):
        if not tool_id or not tool_id.strip():
            raise ValueError("Tool id cannot be empty")
        if not name or not name.strip():
            raise ValueError("Tool name cannot be empty")
        if not description or not description.strip():
            raise ValueError("Tool description cannot be empty")
            
        self.id = tool_id
        self.name = name
        self.description = description

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """
        Execute the tool logic.
        :param kwargs: Arbitrary arguments passed to the tool.
        :return: The result of the tool execution as a string.
        """
        raise NotImplementedError("Tools must implement the execute method")
