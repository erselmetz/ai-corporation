from dataclasses import dataclass

@dataclass
class Node:
    """
    Represents a physical or software installation participating in an AI Corporation.
    
    Architectural Distinction:
    Corporation Identity: "Who is this AI Corporation?"
    Node Identity: "Which physical/software installation is participating in the Corporation?"
    """
    id: str
    corporation_id: str
    name: str

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("Node id cannot be empty")
        if not self.corporation_id or not self.corporation_id.strip():
            raise ValueError("Corporation id cannot be empty")
        if not self.name or not self.name.strip():
            raise ValueError("Node name cannot be empty")
