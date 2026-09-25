from dataclasses import dataclass

@dataclass
class Corporation:
    """
    Represents the identity of one AI Corporation instance.
    This is the highest level of organizational identity.
    
    Architectural Distinction:
    Corporation Identity: "Who is this AI Corporation?"
    (Future) Node/Installation Identity: "Which physical/software installation 
    is participating in the Corporation network?"
    """
    id: str
    name: str

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("Corporation id cannot be empty")
        if not self.name or not self.name.strip():
            raise ValueError("Corporation name cannot be empty")
