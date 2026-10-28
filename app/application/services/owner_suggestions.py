"""Opt-in, read-only suggestions derived from current local workflow state."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from threading import RLock

from app.database.connection import get_connection

PREFERENCE_VERSION = 1
MAX_SUGGESTIONS = 10
MAX_DISMISSED = 200
_CLOCK = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_ID = re.compile(r"^[a-f0-9]{24}$")
_LOCK = RLock()


class OwnerSuggestionsError(ValueError):
    pass


@dataclass(frozen=True)
class SuggestionPreferences:
    enabled: bool = False
    quiet_start: str = ""
    quiet_end: str = ""
    version: int = PREFERENCE_VERSION


def _migrate(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS owner_suggestion_preferences (
        owner_id TEXT PRIMARY KEY, preferences_json TEXT NOT NULL,
        dismissed_json TEXT NOT NULL, version INTEGER NOT NULL)""")


def _validate(values):
    if not isinstance(values, dict) or set(values) - {"enabled", "quiet_start", "quiet_end", "version"}:
        raise OwnerSuggestionsError("Unsupported suggestion preference fields")
    if values.get("version", PREFERENCE_VERSION) != PREFERENCE_VERSION:
        raise OwnerSuggestionsError("Stored suggestion preferences use an unsupported version")
    current = {"enabled": values.get("enabled", False),
               "quiet_start": values.get("quiet_start", ""),
               "quiet_end": values.get("quiet_end", "")}
    if type(current["enabled"]) is not bool:
        raise OwnerSuggestionsError("Suggestion enablement must be a boolean")
    for key in ("quiet_start", "quiet_end"):
        if current[key] is None:
            current[key] = ""
        if not isinstance(current[key], str) or (current[key] and not _CLOCK.fullmatch(current[key])):
            raise OwnerSuggestionsError("Quiet-period times must use 24-hour HH:MM format")
    if bool(current["quiet_start"]) != bool(current["quiet_end"]):
        raise OwnerSuggestionsError("Set both quiet-period times or leave both empty")
    if current["quiet_start"] and current["quiet_start"] == current["quiet_end"]:
        raise OwnerSuggestionsError("Quiet-period start and end must differ")
    return SuggestionPreferences(**current)


def _dismissed_values(raw):
    try:
        values = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str) and _ID.fullmatch(value)][-MAX_DISMISSED:]


class OwnerSuggestionService:
    """Stores owner controls and formats a small set of workflow-state suggestions."""

    def _row(self, connection, owner_id):
        _migrate(connection)
        return connection.execute(
            "SELECT preferences_json, dismissed_json, version FROM owner_suggestion_preferences WHERE owner_id = ?",
            (owner_id,),
        ).fetchone()

    def get_preferences(self, owner_id: str) -> SuggestionPreferences:
        with _LOCK:
            connection = get_connection()
            try:
                with connection:
                    row = self._row(connection, owner_id)
                    if row is None:
                        return SuggestionPreferences()
                    if row["version"] > PREFERENCE_VERSION:
                        raise OwnerSuggestionsError("Stored suggestion preferences are from a newer application version")
                    try:
                        values = json.loads(row["preferences_json"])
                    except (TypeError, json.JSONDecodeError):
                        raise OwnerSuggestionsError("Stored suggestion preferences are invalid") from None
                    return _validate(values)
            finally:
                connection.close()

    def update_preferences(self, owner_id: str, changes: dict) -> SuggestionPreferences:
        if not isinstance(changes, dict) or set(changes) - {"enabled", "quiet_start", "quiet_end"}:
            raise OwnerSuggestionsError("Unsupported suggestion preference fields")
        current = asdict(self.get_preferences(owner_id))
        current.pop("version")
        current.update(changes)
        preferences = _validate(current)
        with _LOCK:
            connection = get_connection()
            try:
                with connection:
                    row = self._row(connection, owner_id)
                    dismissed = _dismissed_values(row["dismissed_json"]) if row is not None else []
                    connection.execute("""INSERT INTO owner_suggestion_preferences
                        (owner_id, preferences_json, dismissed_json, version) VALUES (?, ?, ?, ?)
                        ON CONFLICT(owner_id) DO UPDATE SET preferences_json=excluded.preferences_json,
                        version=excluded.version""",
                        (owner_id, json.dumps(asdict(preferences), sort_keys=True, separators=(",", ":")),
                         json.dumps(dismissed[-MAX_DISMISSED:]), PREFERENCE_VERSION))
            finally:
                connection.close()
        return preferences

    @staticmethod
    def _suggestion_id(workflow_id, item_id, state, uncertain):
        key = f"{workflow_id}\0{item_id}\0{state}\0{int(uncertain)}".encode("utf-8")
        return hashlib.sha256(key).hexdigest()[:24]

    def _current(self, workflow_service, generated_at):
        messages = {
            "blocked": ("Review a blocked workflow item", "Inspect its recorded reason before deciding what to do."),
            "failed": ("Inspect a failed workflow item", "Review the recorded workflow state before deciding whether to retry."),
            "interrupted": ("Inspect interrupted work", "Its provider outcome may be unknown; inspect it before retrying."),
            "review": ("Review recorded worker output", "The existing workflow is waiting for its review step."),
        }
        result = []
        reports = sorted(workflow_service.list(), key=lambda item: item.get("created_at", ""), reverse=True)
        for workflow in reports:
            for item in workflow.get("items", []):
                state = item.get("state")
                uncertain = item.get("uncertain") is True and state in {"failed", "interrupted", "running"}
                if state == "interrupted":
                    uncertain = True
                if uncertain:
                    title, reason = ("Inspect work with an unknown outcome",
                                     "The provider outcome is uncertain; inspect before retrying.")
                elif state in messages:
                    title, reason = messages[state]
                else:
                    continue
                suggestion_id = self._suggestion_id(workflow["id"], item["id"], state, uncertain)
                item_events = [event.get("at") for event in workflow.get("events", [])
                               if event.get("item_id") == item["id"] and isinstance(event.get("at"), str)]
                result.append({
                    "id": suggestion_id,
                    "title": title,
                    "reason": reason,
                    "state": state,
                    "source": {"kind": "local workflow record", "workflow_id": workflow["id"],
                               "work_item_id": item["id"],
                               "last_changed_at": item_events[-1] if item_events else None},
                    "observed_at": generated_at,
                    "href": "native:Workflow map",
                })
                if len(result) >= MAX_SUGGESTIONS:
                    return result
        return result

    def list_suggestions(self, owner_id: str, workflow_service, *, now=None) -> dict:
        preferences = self.get_preferences(owner_id)
        generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        if not preferences.enabled:
            return {"enabled": False, "quiet_start": preferences.quiet_start,
                    "quiet_end": preferences.quiet_end, "generated_at": generated_at,
                    "suggestions": []}
        suggestions = self._current(workflow_service, generated_at)
        current_ids = {item["id"] for item in suggestions}
        with _LOCK:
            connection = get_connection()
            try:
                with connection:
                    row = self._row(connection, owner_id)
                    dismissed = _dismissed_values(row["dismissed_json"]) if row is not None else []
            finally:
                connection.close()
        dismissed_ids = set(dismissed) & current_ids
        return {"enabled": True, "quiet_start": preferences.quiet_start,
                "quiet_end": preferences.quiet_end, "generated_at": generated_at,
                "suggestions": [item for item in suggestions if item["id"] not in dismissed_ids]}

    def dismiss(self, owner_id: str, suggestion_id: str, workflow_service, *, now=None) -> bool:
        if not isinstance(suggestion_id, str) or not _ID.fullmatch(suggestion_id):
            raise OwnerSuggestionsError("Suggestion identifier is invalid")
        current = self.list_suggestions(owner_id, workflow_service, now=now)
        if not current["enabled"] or suggestion_id not in {item["id"] for item in current["suggestions"]}:
            raise OwnerSuggestionsError("Suggestion is no longer current")
        with _LOCK:
            connection = get_connection()
            try:
                with connection:
                    row = self._row(connection, owner_id)
                    dismissed = _dismissed_values(row["dismissed_json"]) if row else []
                    stored_preferences = json.loads(row["preferences_json"]) if row else asdict(SuggestionPreferences())
                    current_ids = {item["id"] for item in current["suggestions"]}
                    dismissed = [value for value in dismissed if value in current_ids]
                    if suggestion_id not in dismissed:
                        dismissed.append(suggestion_id)
                    connection.execute("""INSERT INTO owner_suggestion_preferences
                        (owner_id, preferences_json, dismissed_json, version) VALUES (?, ?, ?, ?)
                        ON CONFLICT(owner_id) DO UPDATE SET dismissed_json=excluded.dismissed_json""",
                        (owner_id, json.dumps(_validate(stored_preferences).__dict__, sort_keys=True),
                         json.dumps(dismissed[-MAX_DISMISSED:]), PREFERENCE_VERSION))
            finally:
                connection.close()
        return True
