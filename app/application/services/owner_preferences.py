"""Bounded local-owner presentation preferences, separate from capability policy."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from threading import RLock

from app.database.connection import get_connection

PREFERENCE_VERSION = 1
RETENTION_NOTICE = (
    "Preferences are stored without encryption in the local application database until you reset them "
    "or remove that database. They contain presentation choices only; no chat content or credentials are stored."
)
MODES = frozenset({"balanced", "concise", "friendly", "formal", "technical"})
DETAIL_LEVELS = frozenset({"brief", "standard", "detailed"})
LOCALES = frozenset({"en-US", "en-GB", "fil-PH"})
VOICE_MODES = frozenset({"off", "local"})
VOICE_LANGUAGES = frozenset({"en-US", "en-GB", "fil-PH"})
DEFAULTS = {
    "response_mode": "balanced", "locale": "en-US", "detail_level": "standard",
    "voice_mode": "off", "voice_language": "en-US", "voice_id": "",
}
_VOICE_ID = re.compile(r"^[^\x00-\x1f\x7f/\\]{1,160}$")
_LOCK = RLock()


class OwnerPreferencesError(ValueError):
    pass


@dataclass(frozen=True)
class OwnerPreferences:
    response_mode: str = DEFAULTS["response_mode"]
    locale: str = DEFAULTS["locale"]
    detail_level: str = DEFAULTS["detail_level"]
    voice_mode: str = DEFAULTS["voice_mode"]
    voice_language: str = DEFAULTS["voice_language"]
    voice_id: str = DEFAULTS["voice_id"]
    version: int = PREFERENCE_VERSION


def _validate(values):
    if not isinstance(values, dict) or set(values) - set(DEFAULTS) - {"version"}:
        raise OwnerPreferencesError("Unsupported preference fields")
    if "version" in values and values["version"] != PREFERENCE_VERSION:
        raise OwnerPreferencesError("Stored preferences use an unsupported version")
    result = dict(DEFAULTS)
    result.update(values)
    choices = {"response_mode": MODES, "locale": LOCALES, "detail_level": DETAIL_LEVELS,
               "voice_mode": VOICE_MODES, "voice_language": VOICE_LANGUAGES}
    for name, allowed in choices.items():
        if result[name] not in allowed:
            raise OwnerPreferencesError(f"Unsupported {name.replace('_', ' ')}")
    if not isinstance(result["voice_id"], str) or (result["voice_id"] and not _VOICE_ID.fullmatch(result["voice_id"])):
        raise OwnerPreferencesError("Voice identifier is invalid")
    return OwnerPreferences(**result)


def _migrate(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS owner_preferences_schema (
        version INTEGER NOT NULL)""")
    row = connection.execute("SELECT version FROM owner_preferences_schema").fetchone()
    if row is not None and row[0] > PREFERENCE_VERSION:
        raise OwnerPreferencesError("Stored preferences are from a newer application version")
    connection.execute("""CREATE TABLE IF NOT EXISTS owner_preferences (
        owner_id TEXT PRIMARY KEY, preferences_json TEXT NOT NULL, version INTEGER NOT NULL)""")
    if row is None:
        connection.execute("INSERT INTO owner_preferences_schema (version) VALUES (?)", (PREFERENCE_VERSION,))


class OwnerPreferencesService:
    """Stores only bounded display choices under the authenticated owner identity."""

    def get(self, owner_id: str) -> OwnerPreferences:
        with _LOCK:
            connection = get_connection()
            try:
                with connection:
                    _migrate(connection)
                    row = connection.execute("SELECT preferences_json, version FROM owner_preferences WHERE owner_id = ?",
                                             (owner_id,)).fetchone()
                    if row is None:
                        return OwnerPreferences()
                    if row["version"] > PREFERENCE_VERSION:
                        raise OwnerPreferencesError("Stored preferences are from a newer application version")
                    try:
                        values = json.loads(row["preferences_json"])
                    except (TypeError, json.JSONDecodeError):
                        raise OwnerPreferencesError("Stored preferences are invalid; reset them to defaults") from None
                    return _validate(values)
            finally:
                connection.close()

    def update(self, owner_id: str, changes: dict) -> OwnerPreferences:
        current = asdict(self.get(owner_id))
        current.pop("version")
        current.update(changes)
        preferences = _validate(current)
        with _LOCK:
            connection = get_connection()
            try:
                with connection:
                    _migrate(connection)
                    connection.execute("""INSERT INTO owner_preferences(owner_id, preferences_json, version)
                        VALUES (?, ?, ?) ON CONFLICT(owner_id) DO UPDATE SET
                        preferences_json=excluded.preferences_json, version=excluded.version""",
                        (owner_id, json.dumps(asdict(preferences) | {"version": PREFERENCE_VERSION},
                                              sort_keys=True, separators=(",", ":")), PREFERENCE_VERSION))
            finally:
                connection.close()
        return preferences

    def reset(self, owner_id: str) -> OwnerPreferences:
        with _LOCK:
            connection = get_connection()
            try:
                with connection:
                    _migrate(connection)
                    connection.execute("DELETE FROM owner_preferences WHERE owner_id = ?", (owner_id,))
            finally:
                connection.close()
        return OwnerPreferences()

    def export(self, owner_id: str) -> dict:
        return {"version": PREFERENCE_VERSION, "owner_id": owner_id,
                "preferences": asdict(self.get(owner_id)), "retention": RETENTION_NOTICE}

    def response_contract(self, owner_id: str) -> dict:
        """Return only allowlisted style instructions; never a routing or authority directive."""
        preferences = self.get(owner_id)
        modes = {
            "balanced": "Use a clear, balanced tone.",
            "concise": "Prefer concise answers while preserving necessary facts and safety details.",
            "friendly": "Use a warm, approachable tone while remaining direct and accurate.",
            "formal": "Use a professional, formal tone.",
            "technical": "Use precise technical language and explain specialized terms when useful.",
        }
        details = {
            "brief": "Keep the response brief unless the request requires essential detail.",
            "standard": "Use a standard level of detail.",
            "detailed": "Provide useful detail and explain the reasoning when appropriate.",
        }
        return {"locale": preferences.locale, "style": modes[preferences.response_mode],
                "detail": details[preferences.detail_level],
                "boundary": "These are presentation preferences only. They do not change provider/model selection, routing, permissions, approval, consent, or execution authority."}
