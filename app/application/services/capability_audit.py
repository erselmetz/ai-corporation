"""Metadata-only local audit trail with fixed fields, bounded retention, and scoped reads."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import re
import sqlite3
from pathlib import Path
import threading
from uuid import uuid4

from app.database.connection import DATABASE_PATH


class CapabilityAuditError(RuntimeError):
    pass


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CAPABILITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_DECISIONS = frozenset({"allow", "deny", "unknown"})
_ACTIONS = frozenset({"authorization", "enabled", "disabled", "granted", "revoked",
                      "approval_requested", "approval_confirmed", "execution_started",
                      "executed", "stale", "expired"})
_RESULTS = frozenset({"allowed", "denied", "pending", "success", "failure",
                      "stale", "expired", "not_run", "unknown"})


def _actor_reference(actor: str) -> str:
    return "actor:" + hashlib.sha256(actor.encode("utf-8", errors="replace")).hexdigest()[:32]


class CapabilityAuditService:
    RETENTION = timedelta(days=30)
    MAX_EVENTS = 10_000
    MAX_BATCH = 100
    MAX_INSPECTION_LIMIT = 200

    def __init__(self, database_path: str | Path | None = None, *, clock=None):
        self._path = Path(database_path) if database_path is not None else DATABASE_PATH
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self._ready = False

    @contextmanager
    def _connection(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(self._path), timeout=5)
        db.row_factory = sqlite3.Row
        try:
            if not self._ready:
                db.execute("""CREATE TABLE IF NOT EXISTS capability_audit_events (
                    event_id TEXT PRIMARY KEY, actor_ref TEXT NOT NULL,
                    capability_id TEXT NOT NULL, permission_decision TEXT NOT NULL,
                    action_state TEXT NOT NULL, result_state TEXT NOT NULL,
                    safe_reference TEXT, created_at TEXT NOT NULL)""")
                db.execute("CREATE INDEX IF NOT EXISTS idx_capability_audit_created "
                           "ON capability_audit_events(created_at, event_id)")
                db.commit()
                self._ready = True
            yield db
        finally:
            db.close()

    def record(self, *, actor_id: str, capability_id: str,
               permission_decision: str, action_state: str, result_state: str,
               safe_reference: str | None = None) -> dict:
        return self.record_many(({"actor_id": actor_id, "capability_id": capability_id,
                                  "permission_decision": permission_decision,
                                  "action_state": action_state, "result_state": result_state,
                                  "safe_reference": safe_reference},))[0]

    def record_many(self, events) -> tuple[dict, ...]:
        events = tuple(events)
        if not 1 <= len(events) <= self.MAX_BATCH:
            raise ValueError("Audit batch must contain 1 to 100 events")
        now = self._now()
        prepared = []
        for event in events:
            actor = event.get("actor_id") if isinstance(event, dict) else None
            capability = event.get("capability_id") if isinstance(event, dict) else None
            decision = event.get("permission_decision") if isinstance(event, dict) else None
            action = event.get("action_state") if isinstance(event, dict) else None
            result = event.get("result_state") if isinstance(event, dict) else None
            if not isinstance(actor, str) or not actor.strip():
                raise ValueError("Audit actor is invalid")
            if not isinstance(capability, str) or not _CAPABILITY.fullmatch(capability):
                raise ValueError("Audit capability is invalid")
            if decision not in _DECISIONS or action not in _ACTIONS or result not in _RESULTS:
                raise ValueError("Audit decision or state is invalid")
            reference = event.get("safe_reference")
            if not isinstance(reference, str) or not _IDENTIFIER.fullmatch(reference):
                reference = None
            actor_ref = _actor_reference(actor)
            prepared.append({"event_id": uuid4().hex, "actor_ref": actor_ref,
                             "capability_id": capability, "permission_decision": decision,
                             "action_state": action, "result_state": result,
                             "safe_reference": reference, "created_at": now.isoformat()})
        cutoff = (now - self.RETENTION).isoformat()
        try:
            with self._lock, self._connection() as db:
                with db:
                    db.executemany("""INSERT INTO capability_audit_events
                        (event_id, actor_ref, capability_id, permission_decision,
                         action_state, result_state, safe_reference, created_at)
                        VALUES (:event_id, :actor_ref, :capability_id, :permission_decision,
                                :action_state, :result_state, :safe_reference, :created_at)""",
                                   prepared)
                    self._prune(db, cutoff)
        except (OSError, sqlite3.Error):
            raise CapabilityAuditError("Capability audit event could not be stored") from None
        return tuple(dict(item) for item in prepared)

    def list_events(self, *, actor_id: str | None = None, limit: int = 100) -> tuple[dict, ...]:
        if type(limit) is not int or not 1 <= limit <= self.MAX_INSPECTION_LIMIT:
            raise ValueError("Audit inspection limit must be between 1 and 200")
        now = self._now()
        cutoff = (now - self.RETENTION).isoformat()
        if actor_id is not None and (not isinstance(actor_id, str) or not actor_id.strip()):
            raise ValueError("Audit actor is invalid")
        actor_ref = None if actor_id is None else _actor_reference(actor_id)
        try:
            with self._lock, self._connection() as db:
                with db:
                    self._prune(db, cutoff)
                    if actor_ref is None:
                        rows = db.execute("""SELECT event_id, actor_ref, capability_id,
                            permission_decision, action_state, result_state, safe_reference, created_at
                            FROM capability_audit_events ORDER BY created_at DESC, event_id DESC LIMIT ?""",
                                          (limit,)).fetchall()
                    else:
                        rows = db.execute("""SELECT event_id, actor_ref, capability_id,
                            permission_decision, action_state, result_state, safe_reference, created_at
                            FROM capability_audit_events WHERE actor_ref=?
                            ORDER BY created_at DESC, event_id DESC LIMIT ?""",
                                          (actor_ref, limit)).fetchall()
        except (OSError, sqlite3.Error):
            raise CapabilityAuditError("Capability audit history is unavailable") from None
        return tuple(dict(row) for row in rows)

    def _prune(self, db, cutoff: str) -> None:
        db.execute("DELETE FROM capability_audit_events WHERE created_at < ?", (cutoff,))
        db.execute("""DELETE FROM capability_audit_events WHERE event_id IN (
            SELECT event_id FROM capability_audit_events
            ORDER BY created_at DESC, event_id DESC LIMIT -1 OFFSET ?)""",
                   (self.MAX_EVENTS,))

    def _now(self) -> datetime:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Audit clock must return a timezone-aware datetime")
        return now.astimezone(timezone.utc)
