"""Encrypted, bounded local application backups for Task 168."""
from __future__ import annotations

import base64
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import sqlite3
import tempfile
import threading
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from app.database.init import CURRENT_CONFIGURATION_VERSION

MAGIC = b"ERSELBK1"
FORMAT_VERSION = 1
MAX_DATABASE_BYTES = 48 * 1024 * 1024
MAX_BACKUP_BYTES = 72 * 1024 * 1024
MAX_PASSPHRASE_LENGTH = 1024
CONFIGURATION_TABLES = frozenset({
    "owner_preferences_schema",
    "owner_preferences",
    "owner_suggestion_preferences",
    "local_first_run",
    "managed_software_pins",
})
SUPPORTED_APP_TABLES = frozenset({
    "agent_memory", "capability_audit_events", "chat_history", "chat_history_messages",
    "chat_history_schema", "conversation_memory", "corporation_knowledge",
    "corporation_knowledge_provenance", "corporation_knowledge_readers",
    "documentation_draft_documents", "documentation_draft_versions", "execution_queue",
    "operator_conversations", "operator_positions", "operator_resource_limits",
    "operator_task_proposals",
    "managed_software", "managed_software_events", "managed_software_pins",
    "local_first_run", "owner_preferences", "owner_preferences_schema", "owner_suggestion_preferences",
    "owner_knowledge", "project_knowledge", "project_memory", "projects", "task_logs", "tasks",
})
_SECRET_COLUMN = re.compile(r"(?:secret|password|credential|api[_-]?key|access[_-]?token|refresh[_-]?token)", re.I)
_SECRET_VALUE = re.compile(
    r"(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|authorization)\b\s*[:=]\s*)(?:bearer\s+)?[^\s,;\"']+"
    r"|\b(?:AIza[0-9A-Za-z_-]{20,}|(?:sk|ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{16,})\b"
    r"|\bBearer\s+[A-Za-z0-9._~+/-]{16,}={0,2}",
)


class BackupError(ValueError):
    """A safe, operator-facing backup or restore failure."""


class DataPortabilityService:
    def __init__(self, database_path: str | Path, *, recovery_directory: str | Path | None = None):
        self.database_path = Path(database_path).resolve()
        self.recovery_directory = (
            Path(recovery_directory).resolve() if recovery_directory is not None
            else self._default_recovery_directory()
        )
        self._lock = threading.RLock()

    @staticmethod
    def _default_recovery_directory() -> Path:
        if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
            root = Path(os.environ["LOCALAPPDATA"])
        else:
            root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        return root / "ERSELMETZ AI" / "backups"

    @staticmethod
    def _quote(identifier: str) -> str:
        if not identifier or "\x00" in identifier:
            raise BackupError("Backup contains an invalid database identifier")
        return '"' + identifier.replace('"', '""') + '"'

    @staticmethod
    def _derive(passphrase: str, salt: bytes) -> bytes:
        if not isinstance(passphrase, str) or not 12 <= len(passphrase) <= MAX_PASSPHRASE_LENGTH:
            raise BackupError("Use a passphrase between 12 and 1024 characters")
        return Scrypt(salt=salt, length=32, n=2**14, r=8, p=1).derive(passphrase.encode("utf-8"))

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _check_database_size(connection: sqlite3.Connection) -> None:
        pages = int(connection.execute("PRAGMA page_count").fetchone()[0])
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        if pages * page_size > MAX_DATABASE_BYTES:
            raise BackupError("Application data exceeds the supported backup size")

    @staticmethod
    def _schema(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        tables = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for name, sql in tables:
            columns = connection.execute(f"PRAGMA table_info({DataPortabilityService._quote(name)})").fetchall()
            result[name] = {
                "sql": sql,
                "columns": [row["name"] for row in columns],
            }
        return result

    def preview(self, *, include_private_data: bool = False) -> dict[str, Any]:
        with self._lock:
            if not self.database_path.is_file():
                raise BackupError("Application database is not available")
            with closing(self._connect(self.database_path)) as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version != CURRENT_CONFIGURATION_VERSION:
                    raise BackupError("Application database schema is not supported for backup")
                schema = self._schema(connection)
                if include_private_data:
                    for table_details in schema.values():
                        if any(_SECRET_COLUMN.search(column) for column in table_details["columns"]):
                            raise BackupError("A database field may contain credentials; backup stopped without exporting data")
                    if not set(schema).issubset(SUPPORTED_APP_TABLES):
                        raise BackupError("Application database contains unsupported tables; backup stopped without exporting data")
                    included = sorted(schema)
                    excluded = ["Operating system credentials, provider data, model files, and external service data are not stored in this application database and are not included."]
                    counts = {
                        table: int(connection.execute(f"SELECT COUNT(*) FROM {self._quote(table)}").fetchone()[0])
                        for table in included
                    }
                else:
                    included = sorted(CONFIGURATION_TABLES.intersection(schema))
                    counts = {
                        table: int(connection.execute(f"SELECT COUNT(*) FROM {self._quote(table)}").fetchone()[0])
                        for table in included
                    }
                    excluded = [
                        "Tasks, projects, conversations, messages, memories, knowledge, audit records, execution state, and other private app content (not selected).",
                        "Operating system credentials, provider data, model files, and external service data (outside this database).",
                    ]
                return {
                    "schema_version": version,
                    "include_private_data": bool(include_private_data),
                    "included_tables": included,
                    "included_row_counts": counts,
                    "excluded": excluded,
                    "diagnostics": {
                        "application": "ERSELMETZ AI",
                        "backup_format": FORMAT_VERSION,
                        "configuration_schema": version,
                        "platform": platform.system() or "unknown",
                        "python": platform.python_version(),
                    },
                    "max_database_bytes": MAX_DATABASE_BYTES,
                }

    def diagnostics(self) -> dict[str, Any]:
        """Return safe runtime/schema metadata without raw records or local paths."""
        with self._lock:
            if not self.database_path.is_file():
                raise BackupError("Application database is not available")
            with closing(self._connect(self.database_path)) as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            return {
                "application": "ERSELMETZ AI",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "configuration_schema": version,
                "backup_format": FORMAT_VERSION,
                "platform": platform.system() or "unknown",
                "python": platform.python_version(),
                "included": ["application and schema version metadata"],
                "excluded": [
                    "Credentials, provider health, model inventory, hardware measurements, user records, logs, paths, and external service data."
                ],
            }

    @staticmethod
    def _create_filtered_database(source: Path, destination: Path, tables: list[str], *, private: bool) -> dict[str, int]:
        with closing(DataPortabilityService._connect(source)) as source_db, closing(DataPortabilityService._connect(destination)) as target_db:
            schema = DataPortabilityService._schema(source_db)
            if any(table not in schema for table in tables):
                raise BackupError("Backup table list does not match its database")
            target_db.execute("PRAGMA user_version = " + str(CURRENT_CONFIGURATION_VERSION))
            for table in tables:
                target_db.execute(schema[table]["sql"])
            for row in source_db.execute("SELECT type, name, tbl_name, sql FROM sqlite_master WHERE type IN ('index','trigger') AND sql IS NOT NULL ORDER BY type, name"):
                if row["tbl_name"] in tables:
                    target_db.execute(row["sql"])
            counts: dict[str, int] = {}
            for table in tables:
                columns = schema[table]["columns"]
                if private and any(_SECRET_COLUMN.search(column) for column in columns):
                    raise BackupError("A database field may contain credentials; backup stopped without exporting data")
                names = ",".join(DataPortabilityService._quote(column) for column in columns)
                values_sql = ",".join("?" for _ in columns)
                read = source_db.execute(f"SELECT {names} FROM {DataPortabilityService._quote(table)}")
                count = 0
                for row in read:
                    values = list(row)
                    if private:
                        if any(isinstance(value, (bytes, bytearray, memoryview)) for value in values):
                            raise BackupError("Binary fields cannot be safely scanned for credentials; backup stopped")
                        values = [
                            _SECRET_VALUE.sub(lambda match: (match.group(1) or "") + "[REDACTED]", value)
                            if isinstance(value, str) else value
                            for value in values
                        ]
                    target_db.execute(
                        f"INSERT INTO {DataPortabilityService._quote(table)} ({names}) VALUES ({values_sql})",
                        values,
                    )
                    count += 1
                counts[table] = count
            source_has_sequence = source_db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
            ).fetchone()
            target_has_sequence = target_db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
            ).fetchone()
            if source_has_sequence and target_has_sequence:
                for name, sequence in source_db.execute(
                    "SELECT name, seq FROM sqlite_sequence WHERE name IN (" + ",".join("?" for _ in tables) + ")",
                    tables,
                ) if tables else ():
                    updated = target_db.execute("UPDATE sqlite_sequence SET seq=? WHERE name=?", (sequence, name))
                    if updated.rowcount == 0:
                        target_db.execute("INSERT INTO sqlite_sequence(name,seq) VALUES(?,?)", (name, sequence))
            target_db.commit()
            result = target_db.execute("PRAGMA quick_check").fetchone()[0]
            if result != "ok":
                raise BackupError("Backup database integrity verification failed")
            return counts

    def _build_backup(self, passphrase: str, *, include_private_data: bool) -> bytes:
        preview = self.preview(include_private_data=include_private_data)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="erse-backup-") as directory:
            source = Path(directory) / "source.db"
            with closing(self._connect(self.database_path)) as current, closing(self._connect(source)) as copy:
                self._check_database_size(current)
                current.backup(copy)
                self._check_database_size(copy)
            stage = Path(directory) / "backup.db"
            tables = preview["included_tables"]
            row_counts = self._create_filtered_database(source, stage, tables, private=include_private_data)
            raw_database = stage.read_bytes()
            if len(raw_database) > MAX_DATABASE_BYTES:
                raise BackupError("Application data exceeds the supported backup size")
            manifest = {
                "format_version": FORMAT_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "schema_version": preview["schema_version"],
                "include_private_data": include_private_data,
                "included_tables": tables,
                "row_counts": row_counts,
                "excluded": preview["excluded"],
                "diagnostics": preview["diagnostics"],
                "database_sha256": hashlib.sha256(raw_database).hexdigest(),
            }
            plaintext = json.dumps({
                "manifest": manifest,
                "database": base64.b64encode(raw_database).decode("ascii"),
            }, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
            salt = secrets.token_bytes(16)
            nonce = secrets.token_bytes(12)
            key = self._derive(passphrase, salt)
            result = MAGIC + salt + nonce + AESGCM(key).encrypt(nonce, plaintext, MAGIC)
            if len(result) > MAX_BACKUP_BYTES:
                raise BackupError("Encrypted backup exceeds the supported file size")
            return result

    def export(self, passphrase: str, *, include_private_data: bool = False) -> bytes:
        with self._lock:
            return self._build_backup(passphrase, include_private_data=include_private_data)

    def _read_backup(self, payload: bytes, passphrase: str) -> tuple[dict[str, Any], bytes]:
        if not isinstance(payload, bytes) or not MAGIC == payload[:len(MAGIC)] or len(payload) > MAX_BACKUP_BYTES or len(payload) < len(MAGIC) + 16 + 12 + 16:
            raise BackupError("Backup file is invalid or exceeds the supported size")
        key = self._derive(passphrase, payload[len(MAGIC):len(MAGIC) + 16])
        nonce = payload[len(MAGIC) + 16:len(MAGIC) + 28]
        try:
            plaintext = AESGCM(key).decrypt(nonce, payload[len(MAGIC) + 28:], MAGIC)
        except InvalidTag:
            raise BackupError("Backup verification failed; check the passphrase and file integrity") from None
        if len(plaintext) > MAX_DATABASE_BYTES * 2:
            raise BackupError("Decrypted backup exceeds the supported size")
        try:
            document = json.loads(plaintext)
            manifest = document["manifest"]
            database = base64.b64decode(document["database"], validate=True)
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            raise BackupError("Backup file contents are invalid") from None
        if (not isinstance(manifest, dict) or manifest.get("format_version") != FORMAT_VERSION
                or manifest.get("schema_version") != CURRENT_CONFIGURATION_VERSION
                or not isinstance(manifest.get("included_tables"), list)
                or len(database) > MAX_DATABASE_BYTES
                or not secrets.compare_digest(hashlib.sha256(database).hexdigest(), str(manifest.get("database_sha256", "")))):
            raise BackupError("Backup schema or integrity check failed")
        return manifest, database

    def inspect(self, payload: bytes, passphrase: str) -> dict[str, Any]:
        with self._lock:
            manifest, database = self._read_backup(payload, passphrase)
            with tempfile.TemporaryDirectory(prefix="erse-inspect-") as directory:
                path = Path(directory) / "backup.db"
                path.write_bytes(database)
                with closing(self._connect(path)) as connection:
                    if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise BackupError("Backup database integrity verification failed")
                    if connection.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') LIMIT 1").fetchone():
                        raise BackupError("Backup contains unsupported database objects")
                    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                    if version != manifest["schema_version"]:
                        raise BackupError("Backup schema does not match its verified manifest")
                    schema = self._schema(connection)
                    if (sorted(schema) != sorted(manifest["included_tables"])
                            or not set(schema).issubset(SUPPORTED_APP_TABLES)):
                        raise BackupError("Backup table list does not match its verified manifest")
                    counts = {
                        table: int(connection.execute(f"SELECT COUNT(*) FROM {self._quote(table)}").fetchone()[0])
                        for table in schema
                    }
                    if counts != manifest.get("row_counts"):
                        raise BackupError("Backup row counts do not match its verified manifest")
            return {
                "created_at": manifest["created_at"],
                "schema_version": manifest["schema_version"],
                "include_private_data": manifest["include_private_data"],
                "included_tables": manifest["included_tables"],
                "row_counts": manifest["row_counts"],
                "excluded": manifest["excluded"],
                "diagnostics": manifest["diagnostics"],
                "verified": True,
            }

    def restore(self, payload: bytes, passphrase: str, *, confirmed: bool) -> dict[str, str]:
        if confirmed is not True:
            raise BackupError("Explicit restore confirmation is required")
        with self._lock:
            self.inspect(payload, passphrase)
            manifest, database = self._read_backup(payload, passphrase)
            with tempfile.TemporaryDirectory(prefix="erse-restore-") as directory:
                stage = Path(directory) / "restore.db"
                stage.write_bytes(database)
                with closing(self._connect(stage)) as staged:
                    if staged.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise BackupError("Backup database integrity verification failed")
                    version = int(staged.execute("PRAGMA user_version").fetchone()[0])
                    schema = self._schema(staged)
                    if (version != CURRENT_CONFIGURATION_VERSION or sorted(schema) != sorted(manifest["included_tables"])
                            or not set(schema).issubset(SUPPORTED_APP_TABLES)
                            or staged.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') LIMIT 1").fetchone()):
                        raise BackupError("Backup is incompatible with this application version")
                self.database_path.parent.mkdir(parents=True, exist_ok=True)
                self.recovery_directory.mkdir(parents=True, exist_ok=True)
                recovery_payload = self._build_backup(passphrase, include_private_data=True)
                self._read_backup(recovery_payload, passphrase)
                recovery_path = self.recovery_directory / (
                    "pre-restore-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4) + ".erselbackup"
                )
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                descriptor = os.open(recovery_path, flags, 0o600)
                try:
                    with os.fdopen(descriptor, "wb") as output:
                        output.write(recovery_payload)
                        output.flush()
                        os.fsync(output.fileno())
                except OSError:
                    recovery_path.unlink(missing_ok=True)
                    raise BackupError("Could not create the encrypted pre-restore recovery copy") from None
                try:
                    if manifest["include_private_data"]:
                        # SQLite's online backup replaces the database transactionally without renaming an open file.
                        with closing(self._connect(stage)) as staged, closing(self._connect(self.database_path)) as target:
                            staged.backup(target)
                            if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                                raise BackupError("Restored database integrity verification failed")
                    else:
                        self._restore_configuration(stage, manifest["included_tables"])
                except (OSError, sqlite3.Error, BackupError) as error:
                    raise BackupError("Restore could not be safely applied; the original data was preserved and an encrypted recovery copy was created (" + type(error).__name__ + ")") from None
            return {"status": "restored", "requires_restart": "true", "recovery_copy": recovery_path.name}

    def _restore_configuration(self, staged_path: Path, tables: list[str]) -> None:
        if not set(tables).issubset(CONFIGURATION_TABLES):
            raise BackupError("Backup contains unsupported configuration data")
        with closing(self._connect(staged_path)) as source, closing(self._connect(self.database_path)) as target:
            source_schema = self._schema(source)
            target_schema = self._schema(target)
            for table in tables:
                if table not in source_schema:
                    raise BackupError("Backup configuration table is missing")
                if table in target_schema and source_schema[table]["columns"] != target_schema[table]["columns"]:
                    raise BackupError("Backup configuration schema is incompatible")
            target.execute("BEGIN IMMEDIATE")
            try:
                for table in tables:
                    if table not in target_schema:
                        target.execute(source_schema[table]["sql"])
                        for index in source.execute("SELECT sql FROM sqlite_master WHERE type IN ('index','trigger') AND tbl_name=? AND sql IS NOT NULL", (table,)):
                            target.execute(index[0])
                    quoted = self._quote(table)
                    target.execute(f"DELETE FROM {quoted}")
                    columns = source_schema[table]["columns"]
                    names = ",".join(self._quote(column) for column in columns)
                    values_sql = ",".join("?" for _ in columns)
                    for row in source.execute(f"SELECT {names} FROM {quoted}"):
                        target.execute(f"INSERT INTO {quoted} ({names}) VALUES ({values_sql})", tuple(row))
                target.commit()
            except BaseException:
                target.rollback()
                raise
