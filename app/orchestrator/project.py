from dataclasses import dataclass


@dataclass
class Project:
    id: str
    name: str
    description: str = ""
    status: str = "active"