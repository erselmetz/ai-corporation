"""Private, versioned documentation drafts; this service never publishes files."""
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
import difflib
import hashlib
from pathlib import Path
import sqlite3
import threading
from uuid import uuid4


class DocumentationReviewConflict(Exception):
    pass


class DocumentationReviewNotFound(Exception):
    pass


@dataclass(frozen=True)
class DocumentationDraftVersion:
    document_id: str
    title: str
    version: int
    content: str
    digest: str
    provenance: str
    created_by: str
    created_at: str
    reviewer: str | None
    approved_at: str | None
    diff: str
    recovered_from_version: int | None


class DocumentationReviewService:
    """SQLite-backed append-only review history, separate from published Markdown."""

    MAX_DOCUMENTS = 100
    MAX_VERSIONS = 50
    MAX_CONTENT = 32768

    def __init__(self, database_path: str | Path | None = None, *, clock=None):
        self._path = Path(database_path) if database_path is not None else Path("projects") / "ai_corporation.db"
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(str(self._path), timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _session(self):
        db = self._connect()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _initialize(self):
        with self._session() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS documentation_draft_documents (
                id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, title TEXT NOT NULL,
                current_version INTEGER NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS documentation_draft_versions (
                document_id TEXT NOT NULL, version INTEGER NOT NULL, content TEXT NOT NULL,
                digest TEXT NOT NULL, provenance TEXT NOT NULL, created_by TEXT NOT NULL,
                created_at TEXT NOT NULL, reviewer TEXT, approved_at TEXT, diff TEXT NOT NULL,
                recovered_from_version INTEGER, PRIMARY KEY(document_id, version),
                FOREIGN KEY(document_id) REFERENCES documentation_draft_documents(id))""")

    @staticmethod
    def _validate_text(value, name, maximum, *, minimum=1):
        if not isinstance(value, str) or not minimum <= len(value) <= maximum or not value.strip():
            raise ValueError(f"{name} must contain {minimum} to {maximum} characters")
        return value

    def _read_version(self, db, document_id, version):
        row = db.execute("SELECT d.title, v.* FROM documentation_draft_documents d JOIN documentation_draft_versions v ON d.id=v.document_id WHERE d.id=? AND v.version=?",
                         (document_id, version)).fetchone()
        if row is None:
            raise DocumentationReviewNotFound("Documentation draft version unavailable")
        return DocumentationDraftVersion(
            row["document_id"], row["title"], row["version"], row["content"], row["digest"],
            row["provenance"], row["created_by"], row["created_at"], row["reviewer"],
            row["approved_at"], row["diff"], row["recovered_from_version"])

    def _append(self, db, document_id, title, content, provenance, actor, previous, recovered_from=None):
        version = previous.version + 1 if previous else 1
        if version > self.MAX_VERSIONS:
            raise DocumentationReviewConflict("Documentation version history is full")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        before = previous.content.splitlines(keepends=True) if previous else []
        diff = "".join(difflib.unified_diff(before, content.splitlines(keepends=True),
                                           fromfile=f"v{previous.version}" if previous else "/dev/null",
                                           tofile=f"v{version}", n=3))
        created_at = self._clock().astimezone(timezone.utc).isoformat()
        if previous is None:
            db.execute("INSERT INTO documentation_draft_documents VALUES (?, ?, ?, ?)",
                       (document_id, actor, title, version))
        else:
            db.execute("UPDATE documentation_draft_documents SET current_version=? WHERE id=?",
                       (version, document_id))
        db.execute("INSERT INTO documentation_draft_versions VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)",
                   (document_id, version, content, digest, provenance, actor, created_at, diff, recovered_from))
        return self._read_version(db, document_id, version)

    def create(self, *, title, content, provenance, actor):
        title = self._validate_text(title, "Title", 200)
        content = self._validate_text(content, "Content", self.MAX_CONTENT)
        provenance = self._validate_text(provenance, "Provenance", 1024)
        actor = self._validate_text(actor, "Actor", 256)
        with self._lock, self._session() as db:
            count = db.execute("SELECT COUNT(*) FROM documentation_draft_documents").fetchone()[0]
            if count >= self.MAX_DOCUMENTS:
                raise DocumentationReviewConflict("Documentation draft limit reached")
            return self._append(db, uuid4().hex, title, content, provenance, actor, None)

    def get(self, document_id, *, actor):
        with self._session() as db:
            row = db.execute("SELECT owner_id, current_version FROM documentation_draft_documents WHERE id=?", (document_id,)).fetchone()
            if row is None or row["owner_id"] != actor:
                raise DocumentationReviewNotFound("Documentation draft unavailable")
            return self._read_version(db, document_id, row["current_version"])

    def history(self, document_id, *, actor):
        with self._session() as db:
            row = db.execute("SELECT owner_id FROM documentation_draft_documents WHERE id=?", (document_id,)).fetchone()
            if row is None or row["owner_id"] != actor:
                raise DocumentationReviewNotFound("Documentation draft unavailable")
            versions = db.execute("SELECT version FROM documentation_draft_versions WHERE document_id=? ORDER BY version DESC", (document_id,)).fetchall()
            return [self._read_version(db, document_id, item["version"]) for item in versions]

    def update(self, document_id, *, expected_version, title, content, provenance, actor):
        title = self._validate_text(title, "Title", 200)
        content = self._validate_text(content, "Content", self.MAX_CONTENT)
        provenance = self._validate_text(provenance, "Provenance", 1024)
        with self._lock, self._session() as db:
            row = db.execute("SELECT owner_id, current_version FROM documentation_draft_documents WHERE id=?", (document_id,)).fetchone()
            if row is None or row["owner_id"] != actor:
                raise DocumentationReviewNotFound("Documentation draft unavailable")
            if row["current_version"] != expected_version:
                raise DocumentationReviewConflict("Documentation draft version changed")
            previous = self._read_version(db, document_id, expected_version)
            return self._append(db, document_id, title, content, provenance, actor, previous)

    def approve(self, document_id, *, version, digest, actor):
        with self._lock, self._session() as db:
            row = db.execute("SELECT owner_id, current_version FROM documentation_draft_documents WHERE id=?", (document_id,)).fetchone()
            if row is None or row["owner_id"] != actor:
                raise DocumentationReviewNotFound("Documentation draft unavailable")
            if row["current_version"] != version:
                raise DocumentationReviewConflict("Only the current exact version can be approved")
            current = self._read_version(db, document_id, version)
            if not isinstance(digest, str) or not hashlib.sha256(current.content.encode("utf-8")).hexdigest() == digest or current.digest != digest:
                raise DocumentationReviewConflict("Documentation draft digest changed")
            approved_at = self._clock().astimezone(timezone.utc).isoformat()
            db.execute("UPDATE documentation_draft_versions SET reviewer=?, approved_at=? WHERE document_id=? AND version=? AND approved_at IS NULL",
                       (actor, approved_at, document_id, version))
            return self._read_version(db, document_id, version)

    def recover(self, document_id, *, source_version, expected_version, actor):
        with self._lock, self._session() as db:
            row = db.execute("SELECT owner_id, current_version FROM documentation_draft_documents WHERE id=?", (document_id,)).fetchone()
            if row is None or row["owner_id"] != actor:
                raise DocumentationReviewNotFound("Documentation draft unavailable")
            if row["current_version"] != expected_version:
                raise DocumentationReviewConflict("Documentation draft version changed")
            source = self._read_version(db, document_id, source_version)
            current = self._read_version(db, document_id, expected_version)
            return self._append(db, document_id, current.title, source.content,
                                f"Recovery from version {source_version}; original provenance: {source.provenance}",
                                actor, current, source_version)
