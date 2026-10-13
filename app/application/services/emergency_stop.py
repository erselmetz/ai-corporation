"""Process-local emergency stop latch for explicitly configured local mode."""
from datetime import datetime, timezone
import threading


class EmergencyStopService:
    def __init__(self, *, clock=None):
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self._stopped_at: str | None = None

    @property
    def stopped(self) -> bool:
        with self._lock:
            return self._stopped_at is not None

    def stop(self) -> dict:
        with self._lock:
            if self._stopped_at is None:
                self._stopped_at = self._now()
            return self.snapshot()

    def resume(self) -> dict:
        with self._lock:
            self._stopped_at = None
            return self.snapshot()

    def snapshot(self) -> dict:
        with self._lock:
            return {"stopped": self._stopped_at is not None,
                    "stopped_at": self._stopped_at,
                    "persistence": "process_only",
                    "remote_cancellation": "unknown"}

    def _now(self) -> str:
        value = self._clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Emergency stop clock must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat()
