from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AvailabilityState(Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AvailabilityResult:
    state: AvailabilityState = AvailabilityState.UNKNOWN
    checked_at: datetime | None = None
    reason: str | None = None

    def __post_init__(self):
        if not isinstance(self.state, AvailabilityState):
            raise TypeError("state must be an AvailabilityState")
        if self.checked_at is not None:
            if not isinstance(self.checked_at, datetime):
                raise TypeError("checked_at must be a datetime")
            if self.checked_at.tzinfo is None or self.checked_at.utcoffset() is None:
                raise ValueError("checked_at must be timezone-aware")
        elif self.state is not AvailabilityState.UNKNOWN:
            raise ValueError("checked_at is required for a determined availability state")
        if self.reason is not None:
            if not isinstance(self.reason, str):
                raise TypeError("reason must be a string")
            if len(self.reason) > 160:
                raise ValueError("reason must not exceed 160 characters")
