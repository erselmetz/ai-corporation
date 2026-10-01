from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DocumentationSummary:
    id: str
    title: str


@dataclass(frozen=True)
class DocumentationDocument:
    id: str
    title: str
    content: str


class DocumentationNotFound(Exception):
    pass


class DocumentationSourceUnavailable(Exception):
    pass


class DocumentationSource(Protocol):
    def list_documents(self) -> list[DocumentationSummary]:
        ...

    def get_document(self, document_id: str) -> DocumentationDocument:
        ...


class DocumentationApplicationService:
    """Read-only documentation use cases independent of the storage source."""

    def __init__(self, source: DocumentationSource):
        self._source = source

    def list_documents(self) -> list[DocumentationSummary]:
        return self._source.list_documents()

    def get_document(self, document_id: str) -> DocumentationDocument:
        return self._source.get_document(document_id)
