import json
from datetime import date
from pathlib import Path
from typing import cast

from app.application.services.updates import (
    UpdateSummary,
    UpdateType,
    UpdatesSourceUnavailable,
)

_UPDATE_FIELDS = {"date", "type", "title", "summary"}
_UPDATE_TYPES = {"development", "release"}


class CuratedUpdatesManifest:
    """Load validated update records from one explicitly configured JSON file."""

    def __init__(self, manifest_path: Path):
        self._manifest_path = manifest_path

    def list_updates(self) -> list[UpdateSummary]:
        try:
            payload = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise UpdatesSourceUnavailable from exc

        if not isinstance(payload, dict) or set(payload) != {"items"}:
            raise UpdatesSourceUnavailable
        entries = payload["items"]
        if not isinstance(entries, list):
            raise UpdatesSourceUnavailable

        updates = [self._parse_entry(entry) for entry in entries]
        updates.sort(key=lambda item: date.fromisoformat(item.date), reverse=True)
        return updates

    @staticmethod
    def _parse_entry(entry: object) -> UpdateSummary:
        if not isinstance(entry, dict) or set(entry) != _UPDATE_FIELDS:
            raise UpdatesSourceUnavailable

        entry_date = entry["date"]
        entry_type = entry["type"]
        title = entry["title"]
        summary = entry["summary"]
        if (
            not isinstance(entry_date, str)
            or not isinstance(entry_type, str)
            or not isinstance(title, str)
            or not isinstance(summary, str)
            or not title.strip()
            or not summary.strip()
            or entry_type not in _UPDATE_TYPES
        ):
            raise UpdatesSourceUnavailable

        try:
            parsed_date = date.fromisoformat(entry_date)
        except ValueError as exc:
            raise UpdatesSourceUnavailable from exc
        if parsed_date.isoformat() != entry_date:
            raise UpdatesSourceUnavailable

        return UpdateSummary(
            date=entry_date,
            type=cast(UpdateType, entry_type),
            title=title,
            summary=summary,
        )
