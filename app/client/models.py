from dataclasses import dataclass

@dataclass
class ClientRequest:
    """
    Represents an external request entering the AI Corporation.
    """
    id: str
    title: str
    description: str

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("Client request id cannot be empty")
        if not self.title or not self.title.strip():
            raise ValueError("Client request title cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("Client request description cannot be empty")
