"""Durable FIFO membership and claims, without automatic execution or replay."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import sqlite3

from app.database import get_connection
from app.resources.manager import identifier


def time(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Queue time must be timezone-aware")


class QueueState(str, Enum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"


@dataclass(frozen=True)
class QueueEntry:
    sequence: int
    id: str
    task_id: str
    state: QueueState
    worker_id: str | None
    claim_id: str | None
    resolution: str | None
    created_at: datetime
    updated_at: datetime


class ExecutionQueue:
    """Trusted application/Orchestrator callers authorize their own operations.

    Claims survive restart. Acknowledgement observes actual persisted Task state;
    it does not call a provider, prove outcomes, or guarantee exactly-once work.
    """
    def __init__(self, corporation_id):
        identifier(corporation_id)
        self._corporation_id = corporation_id

    @staticmethod
    def _entry(row):
        try:
            state = QueueState(row["state"])
            created = datetime.fromisoformat(row["created_at"])
            updated = datetime.fromisoformat(row["updated_at"])
            time(created); time(updated)
            identifier(row["id"]); identifier(row["task_id"])
            if updated < created or row["sequence"] < 1:
                raise ValueError("Invalid queue chronology")
            worker, claim = row["worker_id"], row["claim_id"]
            if (worker is None) != (claim is None):
                raise ValueError("Incomplete claim metadata")
            if worker is not None:
                identifier(worker); identifier(claim)
            if state in (QueueState.CLAIMED, QueueState.COMPLETED, QueueState.FAILED):
                identifier(worker); identifier(claim)
            if state is QueueState.QUEUED and (worker is not None or claim is not None):
                raise ValueError("Queued entry has claim metadata")
            if state is QueueState.ABANDONED and not row["resolution"]:
                raise ValueError("Missing human resolution")
            return QueueEntry(row["sequence"], row["id"], row["task_id"], state,
                              worker, claim, row["resolution"], created, updated)
        except (ValueError, TypeError, KeyError, IndexError):
            raise ValueError("Stored queue entry is invalid") from None

    def _read(self, connection, entry_id):
        identifier(entry_id)
        row = connection.execute("SELECT * FROM execution_queue WHERE corporation_id=? AND id=?",
                                 (self._corporation_id, entry_id)).fetchone()
        if row is None:
            raise KeyError("Queue entry unavailable")
        return self._entry(row)

    def get(self, entry_id):
        connection = get_connection()
        try:
            return self._read(connection, entry_id)
        finally:
            connection.close()

    def list(self, *, limit=50):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Queue list limit must be 1 to 100")
        connection = get_connection()
        try:
            return tuple(self._entry(row) for row in connection.execute(
                "SELECT * FROM execution_queue WHERE corporation_id=? ORDER BY sequence LIMIT ?",
                (self._corporation_id, limit)).fetchall())
        finally:
            connection.close()

    @staticmethod
    def _task_state(connection, task_id):
        row = connection.execute("SELECT status FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise ValueError("Task not found")
        if row["status"] not in ("pending", "running", "completed", "failed"):
            raise ValueError("Invalid persisted Task state")
        return row["status"]

    def enqueue(self, entry_id, task_id, *, now):
        identifier(entry_id); identifier(task_id); time(now)
        connection = get_connection()
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                if self._task_state(connection, task_id) != "pending":
                    raise ValueError("Only pending Tasks can be queued")
                connection.execute("INSERT INTO execution_queue (corporation_id,id,task_id,state,created_at,updated_at) VALUES (?,?,?,'queued',?,?)",
                                   (self._corporation_id, entry_id, task_id, now.isoformat(), now.isoformat()))
                return self._read(connection, entry_id)
        except sqlite3.IntegrityError:
            raise ValueError("Duplicate queue ID or Task membership") from None
        finally:
            connection.close()

    def claim_next(self, *, worker_id, claim_id, now):
        identifier(worker_id); identifier(claim_id); time(now)
        connection = get_connection()
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute("SELECT * FROM execution_queue WHERE corporation_id=? AND state='queued' ORDER BY sequence LIMIT 1",
                                         (self._corporation_id,)).fetchone()
                if row is None:
                    return None
                entry = self._entry(row)
                if now < entry.updated_at:
                    raise ValueError("Queue time precedes last update")
                if self._task_state(connection, entry.task_id) != "pending":
                    raise ValueError("FIFO head Task is no longer pending; human resolution required")
                connection.execute("UPDATE execution_queue SET state='claimed',worker_id=?,claim_id=?,updated_at=? WHERE sequence=?",
                                   (worker_id, claim_id, now.isoformat(), entry.sequence))
                return self._read(connection, entry.id)
        except sqlite3.IntegrityError:
            raise ValueError("Claim ID has already been used") from None
        finally:
            connection.close()

    def acknowledge(self, entry_id, *, worker_id, claim_id, now):
        identifier(worker_id); identifier(claim_id); time(now)
        connection = get_connection()
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                entry = self._read(connection, entry_id)
                if entry.state is not QueueState.CLAIMED or (entry.worker_id, entry.claim_id) != (worker_id, claim_id):
                    raise ValueError("Active matching claim required")
                if now < entry.updated_at:
                    raise ValueError("Queue time precedes last update")
                state = self._task_state(connection, entry.task_id)
                if state not in ("completed", "failed"):
                    raise ValueError("Task has no terminal execution outcome")
                connection.execute("UPDATE execution_queue SET state=?,updated_at=? WHERE sequence=?",
                                   (state, now.isoformat(), entry.sequence))
                return self._read(connection, entry_id)
        finally:
            connection.close()

    def abandon(self, entry_id, *, resolution, confirm=False, now):
        time(now)
        if confirm is not True or not isinstance(resolution, str) or not resolution.strip() or len(resolution.encode("utf-8")) > 1024:
            raise ValueError("Explicit human confirmation and bounded resolution required")
        connection = get_connection()
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                entry = self._read(connection, entry_id)
                if entry.state not in (QueueState.QUEUED, QueueState.CLAIMED) or now < entry.updated_at:
                    raise ValueError("Queue entry cannot be resolved in this state/time")
                connection.execute("UPDATE execution_queue SET state='abandoned',resolution=?,updated_at=? WHERE sequence=?",
                                   (resolution, now.isoformat(), entry.sequence))
                return self._read(connection, entry_id)
        finally:
            connection.close()
