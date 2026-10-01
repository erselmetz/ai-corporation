from dataclasses import dataclass
from typing import Literal, Protocol

UpdateType = Literal["development", "release"]


@dataclass(frozen=True)
class UpdateSummary:
    date: str
    type: UpdateType
    title: str
    summary: str


class UpdatesSourceUnavailable(Exception):
    pass


class UpdatesSource(Protocol):
    def list_updates(self) -> list[UpdateSummary]:
        ...


class UpdatesApplicationService:
    """Read-only use cases for manually curated Corporation updates."""

    def __init__(self, source: UpdatesSource):
        self._source = source

    def list_updates(self) -> list[UpdateSummary]:
        return self._source.list_updates()
