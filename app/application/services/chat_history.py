"""Opt-in durable owner chat history with truthful restart recovery.

Nothing is stored unless the owner opts in for one conversation. Stored text is not
encrypted. A turn left pending by a restart is reported as uncertain and is never
replayed; the owner must review it. Credentials are never stored by this module.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock

from app.database.connection import get_connection

MIN_RETENTION = timedelta(hours=1)
MAX_RETENTION = timedelta(days=90)
MAX_DURABLE_CONVERSATIONS = 200
STORAGE_NOTICE = (
    "History is stored unencrypted in the local application database until it expires "
    "or you delete it. Deleting removes this conversation's stored messages only; it does "
    "not remove knowledge you retained separately, recall text already sent to a provider, "
    "or change Tasks created from it."
)
RECOVERY_NOTICE = (
    "This conversation was recovered after a restart and is read-only. A turn still "
    "pending when the app stopped may or may not have reached the provider; it is not "
    "replayed. Review it, then start a new conversation to continue."
)


class ChatHistoryError(RuntimeError):
    pass


class HistoryNotFound(ValueError):
    pass


def _v1(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS chat_history (
        id TEXT PRIMARY KEY, corporation_id TEXT NOT NULL, owner_id TEXT NOT NULL,
        agent_id TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS chat_history_messages (
        conversation_id TEXT NOT NULL, seq INTEGER NOT NULL, id TEXT NOT NULL,
        role TEXT NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL,
        created_at TEXT NOT NULL, PRIMARY KEY (conversation_id, id),
        UNIQUE (conversation_id, seq))""")


def _v2(connection):
    connection.execute("ALTER TABLE chat_history ADD COLUMN origin TEXT NOT NULL DEFAULT 'owned-chat'")
    connection.execute("ALTER TABLE chat_history_messages ADD COLUMN review TEXT")


MIGRATIONS = (_v1, _v2)


def apply_migrations(connection, up_to=None):
    connection.execute("CREATE TABLE IF NOT EXISTS chat_history_schema (version INTEGER NOT NULL)")
    row = connection.execute("SELECT version FROM chat_history_schema").fetchone()
    current = row[0] if row else 0
    target = len(MIGRATIONS) if up_to is None else up_to
    if current > len(MIGRATIONS):
        raise ChatHistoryError("Stored chat history is from a newer application version")
    with connection:
        for number in range(current, target):
            MIGRATIONS[number](connection)
            connection.execute("DELETE FROM chat_history_schema")
            connection.execute("INSERT INTO chat_history_schema (version) VALUES (?)", (number + 1,))


def _utc(now):
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("A timezone-aware time is required")
    return now.astimezone(timezone.utc)


class ChatHistoryService:
    def __init__(self, corporation_id: str):
        self._corporation_id = corporation_id
        self._active: set[str] = set()
        self._lock = RLock()
        self._ready = False

    def _connect(self):
        connection = get_connection()
        try:
            if not self._ready:
                apply_migrations(connection)
                self._ready = True
        except Exception:
            connection.close()
            raise
        return connection

    def is_active(self, conversation_id):
        return conversation_id in self._active

    def _guard(self, operation):
        try:
            return operation()
        except ChatHistoryError:
            raise
        except Exception:
            raise ChatHistoryError("Chat history could not be saved") from None

    def enable(self, owner, conversation_id, agent_id, status, messages, *, expires_at, opt_in, now):
        if opt_in is not True:
            raise ValueError("Explicit history opt-in is required")
        now, expires_at = _utc(now), _utc(expires_at)
        if not MIN_RETENTION <= expires_at - now <= MAX_RETENTION:
            raise ValueError("Expiry must be between 1 hour and 90 days from now")
        if any(m["status"] == "pending" for m in messages):
            raise ValueError("Wait for the current turn before enabling history")
        with self._lock:
            connection = self._connect()
            try:
                with connection:
                    if connection.execute("SELECT 1 FROM chat_history WHERE id = ?", (conversation_id,)).fetchone():
                        raise ValueError("History is already enabled for this conversation")
                    count = connection.execute(
                        "SELECT COUNT(*) FROM chat_history WHERE corporation_id = ? AND owner_id = ?",
                        (self._corporation_id, owner)).fetchone()[0]
                    if count >= MAX_DURABLE_CONVERSATIONS:
                        raise ValueError("Durable conversation limit reached; delete some history")
                    connection.execute(
                        "INSERT INTO chat_history (id, corporation_id, owner_id, agent_id, status, "
                        "created_at, expires_at) VALUES (?,?,?,?,?,?,?)",
                        (conversation_id, self._corporation_id, owner, agent_id, status,
                         now.isoformat(), expires_at.isoformat()))
                    for seq, m in enumerate(messages):
                        connection.execute(
                            "INSERT INTO chat_history_messages (conversation_id, seq, id, role, content, "
                            "status, created_at) VALUES (?,?,?,?,?,?,?)",
                            (conversation_id, seq, m["id"], m["role"], m["content"], m["status"], now.isoformat()))
            finally:
                connection.close()
            self._active.add(conversation_id)
        return {"conversation_id": conversation_id, "expires_at": expires_at.isoformat(),
                "notice": STORAGE_NOTICE}

    def record_message(self, conversation_id, message_id, role, content, status, now):
        def write():
            connection = self._connect()
            try:
                with connection:
                    seq = connection.execute(
                        "SELECT COALESCE(MAX(seq), -1) + 1 FROM chat_history_messages WHERE conversation_id = ?",
                        (conversation_id,)).fetchone()[0]
                    connection.execute(
                        "INSERT INTO chat_history_messages (conversation_id, seq, id, role, content, status, "
                        "created_at) VALUES (?,?,?,?,?,?,?)",
                        (conversation_id, seq, message_id, role, content, status, _utc(now).isoformat()))
            finally:
                connection.close()
        self._guard(write)

    def update_status(self, conversation_id, message_id, status):
        def write():
            connection = self._connect()
            try:
                with connection:
                    connection.execute(
                        "UPDATE chat_history_messages SET status = ? WHERE conversation_id = ? AND id = ?",
                        (status, conversation_id, message_id))
            finally:
                connection.close()
        self._guard(write)

    def close(self, conversation_id):
        def write():
            connection = self._connect()
            try:
                with connection:
                    connection.execute("UPDATE chat_history SET status = 'closed' WHERE id = ?", (conversation_id,))
            finally:
                connection.close()
        self._guard(write)

    def _purge(self, connection, now):
        with connection:
            expired = [r[0] for r in connection.execute(
                "SELECT id FROM chat_history WHERE expires_at <= ?", (_utc(now).isoformat(),))]
            for identifier in expired:
                connection.execute("DELETE FROM chat_history_messages WHERE conversation_id = ?", (identifier,))
                connection.execute("DELETE FROM chat_history WHERE id = ?", (identifier,))
                self._active.discard(identifier)

    def list(self, owner, now):
        with self._lock:
            connection = self._connect()
            try:
                self._purge(connection, now)
                rows = connection.execute(
                    "SELECT * FROM chat_history WHERE corporation_id = ? AND owner_id = ? ORDER BY created_at, id",
                    (self._corporation_id, owner)).fetchall()
                items = []
                for row in rows:
                    pending = connection.execute(
                        "SELECT COUNT(*) FROM chat_history_messages WHERE conversation_id = ? AND status = 'pending'",
                        (row["id"],)).fetchone()[0]
                    live = row["id"] in self._active
                    items.append({"id": row["id"], "agent_id": row["agent_id"], "status": row["status"],
                                  "expires_at": row["expires_at"], "live": live,
                                  "needs_review": 0 if live else pending})
                return {"items": items, "notice": STORAGE_NOTICE}
            finally:
                connection.close()

    def _owned(self, connection, owner, conversation_id):
        row = connection.execute(
            "SELECT * FROM chat_history WHERE id = ? AND corporation_id = ? AND owner_id = ?",
            (conversation_id, self._corporation_id, owner)).fetchone()
        if row is None:
            raise HistoryNotFound("Conversation history not found")
        return row

    def get(self, owner, conversation_id, now):
        with self._lock:
            connection = self._connect()
            try:
                self._purge(connection, now)
                row = self._owned(connection, owner, conversation_id)
                live = conversation_id in self._active
                messages = []
                for m in connection.execute(
                        "SELECT * FROM chat_history_messages WHERE conversation_id = ? ORDER BY seq",
                        (conversation_id,)):
                    uncertain = m["status"] == "pending" and not live
                    messages.append({"id": m["id"], "role": m["role"], "content": m["content"],
                                     "status": "uncertain" if uncertain else m["status"],
                                     "needs_review": uncertain, "review": m["review"]})
                return {"id": row["id"], "agent_id": row["agent_id"], "status": row["status"],
                        "expires_at": row["expires_at"], "origin": row["origin"], "live": live,
                        "read_only": not live, "messages": messages,
                        "recovery_notice": None if live else RECOVERY_NOTICE}
            finally:
                connection.close()

    def review(self, owner, conversation_id, message_id, now):
        with self._lock:
            connection = self._connect()
            try:
                self._purge(connection, now)
                self._owned(connection, owner, conversation_id)
                if conversation_id in self._active:
                    raise ValueError("Live conversations have no uncertain turns to review")
                with connection:
                    cursor = connection.execute(
                        "UPDATE chat_history_messages SET status = 'interrupted', review = 'owner-reviewed' "
                        "WHERE conversation_id = ? AND id = ? AND status = 'pending'",
                        (conversation_id, message_id))
                    if cursor.rowcount != 1:
                        raise ValueError("Message is not awaiting review")
            finally:
                connection.close()
        return self.get(owner, conversation_id, now)

    def delete(self, owner, conversation_id):
        with self._lock:
            connection = self._connect()
            try:
                self._owned(connection, owner, conversation_id)
                with connection:
                    connection.execute("DELETE FROM chat_history_messages WHERE conversation_id = ?", (conversation_id,))
                    connection.execute("DELETE FROM chat_history WHERE id = ?", (conversation_id,))
            finally:
                connection.close()
            self._active.discard(conversation_id)
        return {"deleted": conversation_id, "notice": STORAGE_NOTICE}

    def delete_all(self, owner):
        with self._lock:
            connection = self._connect()
            try:
                with connection:
                    ids = [r[0] for r in connection.execute(
                        "SELECT id FROM chat_history WHERE corporation_id = ? AND owner_id = ?",
                        (self._corporation_id, owner))]
                    for identifier in ids:
                        connection.execute("DELETE FROM chat_history_messages WHERE conversation_id = ?", (identifier,))
                        connection.execute("DELETE FROM chat_history WHERE id = ?", (identifier,))
                        self._active.discard(identifier)
            finally:
                connection.close()
        return {"deleted": len(ids), "notice": STORAGE_NOTICE}