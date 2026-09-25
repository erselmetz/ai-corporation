from dataclasses import dataclass

@dataclass
class RuntimeContext:
    """
    Represents the current runtime identity of the AI Corporation instance.
    
    This context answers: "Which Corporation and which Node is this running application instance?"
    """
    corporation_id: str
    node_id: str

    def __post_init__(self) -> None:
        if not self.corporation_id or not self.corporation_id.strip():
            raise ValueError("Corporation id cannot be empty")
        if not self.node_id or not self.node_id.strip():
            raise ValueError("Node id cannot be empty")
