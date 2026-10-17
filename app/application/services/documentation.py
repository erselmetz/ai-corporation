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


class DocumentationDocumentTooLarge(Exception):
    pass


class DocumentationSource(Protocol):
    def list_documents(self) -> list[DocumentationSummary]:
        ...

    def get_document(self, document_id: str) -> DocumentationDocument:
        ...

    def get_document_bounded(self, document_id: str, max_characters: int) -> DocumentationDocument:
        ...


class DocumentationApplicationService:
    """Read-only documentation use cases independent of the storage source."""

    def __init__(self, source: DocumentationSource):
        self._source = source

    def list_documents(self) -> list[DocumentationSummary]:
        return self._source.list_documents()

    def get_document(self, document_id: str) -> DocumentationDocument:
        return self._source.get_document(document_id)

    def get_document_bounded(self, document_id: str, max_characters: int) -> DocumentationDocument:
        bounded_reader = getattr(self._source, "get_document_bounded", None)
        if not callable(bounded_reader):
            raise DocumentationSourceUnavailable
        return bounded_reader(document_id, max_characters)
