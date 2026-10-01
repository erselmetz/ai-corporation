import re
from pathlib import Path

from app.application.services.documentation import (
    DocumentationDocument,
    DocumentationNotFound,
    DocumentationSourceUnavailable,
    DocumentationSummary,
)

_DOCUMENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")


class MarkdownDocumentationSource:
    """Read top-level Markdown documents from one configured directory."""

    def __init__(self, root: Path):
        self._root = root

    def list_documents(self) -> list[DocumentationSummary]:
        root = self._resolved_root()
        try:
            entries = sorted(root.iterdir(), key=lambda entry: entry.name.casefold())
        except OSError as exc:
            raise DocumentationSourceUnavailable from exc

        documents: list[DocumentationSummary] = []
        for entry in entries:
            if (
                entry.name.startswith(".")
                or entry.suffix != ".md"
                or entry.is_symlink()
                or not entry.is_file()
            ):
                continue
            document_id = entry.stem
            if not _DOCUMENT_ID.fullmatch(document_id):
                continue
            try:
                content = self._read_content(root, document_id)
            except DocumentationNotFound:
                continue
            documents.append(
                DocumentationSummary(
                    id=document_id,
                    title=self._title(content, document_id),
                )
            )
        return documents

    def get_document(self, document_id: str) -> DocumentationDocument:
        root = self._resolved_root()
        content = self._read_content(root, document_id)
        return DocumentationDocument(
            id=document_id,
            title=self._title(content, document_id),
            content=content,
        )

    def _resolved_root(self) -> Path:
        if self._root.is_symlink():
            raise DocumentationSourceUnavailable
        try:
            root = self._root.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise DocumentationSourceUnavailable from exc
        if not root.is_dir():
            raise DocumentationSourceUnavailable
        return root

    @staticmethod
    def _read_content(root: Path, document_id: str) -> str:
        if not _DOCUMENT_ID.fullmatch(document_id):
            raise DocumentationNotFound

        candidate = root / f"{document_id}.md"
        if candidate.is_symlink():
            raise DocumentationNotFound
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise DocumentationNotFound from exc
        if resolved.parent != root or resolved.suffix != ".md" or not resolved.is_file():
            raise DocumentationNotFound

        try:
            return resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise DocumentationSourceUnavailable from exc

    @staticmethod
    def _title(content: str, document_id: str) -> str:
        for line in content.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                if title:
                    return title
        return document_id.replace("-", " ").replace("_", " ").title()
