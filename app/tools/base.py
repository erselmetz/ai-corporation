from abc import ABC, abstractmethod
from copy import deepcopy

TOOL_RISK_CLASSES = frozenset({"read", "write", "external", "control"})

class Tool(ABC):
    """
    Abstract base class for a Tool.
    A Tool represents an executable capability that an AI Agent can use.
    """
    def __init__(self, tool_id: str, name: str, description: str, *,
                 risk_class: str = "control", input_schema: dict | None = None):
        if not tool_id or not tool_id.strip():
            raise ValueError("Tool id cannot be empty")
        if not name or not name.strip():
            raise ValueError("Tool name cannot be empty")
        if not description or not description.strip():
            raise ValueError("Tool description cannot be empty")
            
        self.id = tool_id
        self.name = name
        self.description = description
        # Preserve unknown values for audit, but make their effective policy
        # fail closed as control-risk in ToolRegistry.
        self.risk_class = risk_class
        self.input_schema = deepcopy(input_schema or {
            "type": "object", "properties": {}, "required": [], "additionalProperties": False,
        })

    def preview(self, parameters: dict) -> dict:
        """Return a bounded, side-effect-free action summary for owner review."""
        if not isinstance(parameters, dict):
            raise TypeError("Tool parameters must be an object")
        return {"tool_id": self.id, "name": self.name,
                "risk_class": self.risk_class if isinstance(self.risk_class, str)
                    and self.risk_class in TOOL_RISK_CLASSES else "control",
                "summary": self.description[:256], "parameters": deepcopy(parameters)}

    def dry_run(self, parameters: dict) -> dict:
        """Default dry-run is a preview only; it never invokes execute()."""
        return {"executed": False, "preview": self.preview(parameters)}

    def undo(self, result) -> bool:
        """Tools opt into undo by overriding this method; default is unsupported."""
        return False

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """
        Execute the tool logic.
        :param kwargs: Arbitrary arguments passed to the tool.
        :return: The result of the tool execution as a string.
        """
        raise NotImplementedError("Tools must implement the execute method")
