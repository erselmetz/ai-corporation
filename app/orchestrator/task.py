from dataclasses import dataclass
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskFailureCategory(str, Enum):
    UNKNOWN = "unknown"
    ROUTING = "routing"
    EXECUTION = "execution"


@dataclass
class Task:
    id: str
    title: str
    description: str
    project_id: str | None = None
    assigned_agent: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    error: str | None = None
    required_role: str | None = None
    required_capability: str | None = None
    failure_category: TaskFailureCategory | None = None