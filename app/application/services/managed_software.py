"""Narrow, owner-confirmed user-scope management for Microsoft VS Code."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from types import SimpleNamespace

from app.database import get_connection

PACKAGE_ID = "Microsoft.VisualStudioCode"
SOURCE = "winget"
VERSION_RE = re.compile(r"\A[0-9]+(?:\.[0-9]+){1,3}\Z")
HASH_RE = re.compile(r"\A[0-9a-fA-F]{64}\Z")
MAX_OUTPUT = 65536
PREVIEW_SECONDS = 300


class SoftwareManagementError(RuntimeError):
    """A bounded, safe-to-display software management failure."""


@dataclass(frozen=True, slots=True)
class _Preview:
    digest: str
    action: str
    version: str | None
    expires: float
    previous_version: str | None
    installer_hash: str | None


class ManagedSoftwareService:
    """Manage only app-owned VS Code user installs through a fixed WinGet adapter.

    Package execution is never run elevated, package names/arguments are fixed,
    and existing installs are informational until this application has installed
    and recorded the package itself. Pending confirmations are process-local and
    short-lived; the managed-install provenance is kept in the application DB.
    """

    def __init__(self, *, runner=subprocess.run, clock=time.monotonic, executable=None):
        self._runner = runner
        self._clock = clock
        self._executable = executable or shutil.which("winget")
        self._lock = threading.RLock()
        self._previews: dict[str, _Preview] = {}
        connection = get_connection()
        try:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS managed_software (
                    package_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    source TEXT NOT NULL,
                    scope TEXT NOT NULL CHECK(scope = 'user'),
                    state TEXT NOT NULL CHECK(state IN ('managed','uncertain')),
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS managed_software_pins (
                    package_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS managed_software_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    from_version TEXT,
                    requested_version TEXT,
                    result_version TEXT,
                    preview_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            connection.commit()
        finally:
            connection.close()

    def status(self) -> dict:
        installed = self._installed()
        managed = self._managed()
        if installed is None:
            state, version = "unknown", None
        elif managed and managed["state"] == "uncertain":
            state, version = "ownership_uncertain", installed if isinstance(installed, str) else None
        elif installed is False:
            state, version = "not_installed", None
        else:
            version = installed
            state = "managed" if managed and managed["state"] == "managed" else "externally_managed"
        return {
            "package_id": PACKAGE_ID,
            "name": "Microsoft Visual Studio Code",
            "source": SOURCE,
            "scope": "user",
            "status": state,
            "installed_version": version,
            "managed_version": managed["version"] if managed else None,
            "pinned_version": self._pinned_version(),
            "dependent_workflows": [],
            "dependency_note": "No application registry dependencies are recorded; user/workspace reliance is outside detected data.",
            "recent_operations": self._recent_events(),
            "limitations": [
                "Only this exact package from the configured WinGet source is supported.",
                "Existing and uncertain installations are read-only; this app only manages installs it records itself.",
                "User settings, profiles and extensions are not read, backed up, or removed.",
                "Package operations can have installer side effects beyond this app's control; elevation and automatic retry are disabled.",
            ],
        }

    def preview(self, action: str, version: str | None = None) -> dict:
        if action not in {"install", "update", "version", "pin", "unpin", "remove"}:
            raise ValueError("Unsupported software operation")
        if action in {"install", "update", "version", "pin"}:
            if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
                raise ValueError("A supported exact version is required")
        elif version is not None:
            raise ValueError("This operation does not accept a version")
        with self._lock:
            self._prune()
            installed = self._installed()
            managed = self._managed()
            if installed is None:
                raise SoftwareManagementError("Installed package state could not be verified")
            if action == "install":
                if installed is not False:
                    raise SoftwareManagementError("An existing install is read-only and will not be adopted or replaced")
                if managed is not None and not (
                    managed["state"] == "uncertain" and managed["version"] == version
                ):
                    raise SoftwareManagementError("Managed install state needs owner review before another install")
            else:
                if not managed or managed["state"] != "managed":
                    raise SoftwareManagementError("Only an app-owned, verified user-scope install can be changed")
                if installed is False or installed != managed["version"]:
                    raise SoftwareManagementError("Installed version changed outside this app; management is blocked")
            if action in {"pin", "unpin", "remove"}:
                pinned = self._pinned_version()
                recorded_pin = self._pinned_version_record()
                if pinned is None:
                    raise SoftwareManagementError("Existing pin state could not be verified")
                if action == "pin" and pinned is not False and pinned != recorded_pin:
                    raise SoftwareManagementError("An existing external version pin is read-only")
                if action == "unpin" and (pinned is False or pinned != recorded_pin):
                    raise SoftwareManagementError("Only a verified pin created by this app can be removed")
                if action == "remove" and (pinned is not False or recorded_pin is not None):
                    raise SoftwareManagementError("Remove the version pin through a separate approved operation first")
            install_directory = self._installation_location() if action == "remove" else None
            if action == "remove" and not install_directory:
                raise SoftwareManagementError("The user-scope install directory could not be verified for removal review")
            selected = version
            installer_hash = None
            if action in {"install", "update", "version", "pin"}:
                available, installer_hash = self._catalog_version(selected)
                if not available:
                    raise SoftwareManagementError("The exact package version is not verified in the configured source")
                if action in {"update", "version"} and isinstance(installed, str) and _version_key(selected) <= _version_key(installed):
                    raise SoftwareManagementError("Only forward upgrades are supported; downgrades have no verified recovery path")
            previous = installed if isinstance(installed, str) else None
            plan = {
                "package_id": PACKAGE_ID,
                "name": "Microsoft Visual Studio Code",
                "source": SOURCE,
                "scope": "user",
                "action": action,
                "from_version": previous,
                "to_version": selected,
                "recovery_from_uncertain": bool(action == "install" and managed and managed["state"] == "uncertain"),
                "installer_sha256": installer_hash,
                "affected_dependents": [],
                "dependency_note": "No application registry dependencies are recorded; user/workspace reliance is outside detected data.",
                "preserved_data": ["%APPDATA%\\Code", "%USERPROFILE%\\.vscode", "%USERPROFILE%\\.vscode-shared"],
                "removed_install_directory": install_directory,
                "warnings": [
                    "The package installer is third-party code executed by WinGet; no administrator elevation is requested.",
                    "This preview expires in five minutes and must be explicitly confirmed by the local owner.",
                    "No user data folders are passed to the package manager and clean-up/purge options are never used.",
                    *(["Removal deletes the listed application directory; move any user work stored beneath it before confirming."] if action == "remove" else []),
                ],
            }
            raw = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
            digest = hashlib.sha256(raw).hexdigest()
            confirmation = uuid.uuid4().hex
            expires = self._clock() + PREVIEW_SECONDS
            self._previews[confirmation] = _Preview(digest, action, selected, expires, previous, installer_hash)
            return {**plan, "confirmation_id": confirmation, "preview_sha256": digest,
                    "expires_in_seconds": PREVIEW_SECONDS}

    def confirm(self, confirmation_id: str, preview_sha256: str) -> dict:
        with self._lock:
            self._prune()
            record = self._previews.get(confirmation_id)
            if not record or not isinstance(preview_sha256, str) or not hmac.compare_digest(
                    record.digest, preview_sha256):
                raise PermissionError("A current matching owner-confirmed preview is required")
            if _is_elevated_process():
                self._previews.pop(confirmation_id, None)
                raise PermissionError("Software changes are blocked when ERSELMETZ AI is running elevated")
            # Rebuild the safety-relevant observations before consuming approval.
            current = self.preview(record.action, record.version)
            if current["preview_sha256"] != record.digest or self._clock() >= record.expires:
                self._previews.pop(current["confirmation_id"], None)
                self._previews.pop(confirmation_id, None)
                raise PermissionError("The software preview is stale; review a new preview")
            self._previews.pop(current["confirmation_id"], None)
            self._previews.pop(confirmation_id, None)
            args = self._operation_args(record)
            try:
                result = self._run(args, timeout=600)
            except (OSError, subprocess.TimeoutExpired):
                self._mark_uncertain(record.version or record.previous_version or "unknown")
                response = {"status": "uncertain", "action": record.action,
                        "recovery": self._operation_recovery(record),
                        "message": "The package operation ended without a verified result; automatic retry is disabled."}
                self._record_event(record, response["status"], None)
                return response
            if result.returncode != 0:
                observed = self._installed()
                observed_version = observed if isinstance(observed, str) else None
                observed_pin = self._pinned_version() if record.action in {"pin", "unpin"} else None
                recorded_pin = self._pinned_version_record()
                expected_pin = recorded_pin if recorded_pin is not None else False
                pin_changed = (record.action in {"pin", "unpin"}
                               and (observed_pin is None or observed_pin != expected_pin))
                if observed_version != record.previous_version or pin_changed:
                    self._mark_uncertain(observed if isinstance(observed, str) else "unknown")
                    response = {"status": "uncertain", "action": record.action,
                            "recovery": self._operation_recovery(record),
                            "message": "The package operation failed after changing installation state; review recovery before any further change."}
                    self._record_event(record, response["status"], observed if isinstance(observed, str) else None)
                    return response
                response = {"status": "failed", "action": record.action,
                        "message": "The package manager did not complete the approved operation. No retry was attempted."}
                self._record_event(record, response["status"], record.previous_version)
                return response
            if record.action in {"install", "update", "version"}:
                observed = self._installed()
                if observed != record.version:
                    self._mark_uncertain(record.version or "unknown")
                    response = {"status": "uncertain", "action": record.action,
                            "recovery": self._operation_recovery(record),
                            "message": "The package manager returned success, but the requested version could not be verified."}
                    self._record_event(record, response["status"], observed if isinstance(observed, str) else None)
                    return response
                self._save_managed(observed)
                response = {"status": "completed", "action": record.action,
                        "version": observed, "recovery": None}
                self._record_event(record, response["status"], observed)
                return response
            if record.action == "remove":
                if self._installed() is not False:
                    self._mark_uncertain(record.previous_version or "unknown")
                    response = {"status": "uncertain", "action": record.action,
                            "recovery": self._operation_recovery(record),
                            "message": "Removal could not be verified; user data cleanup was not requested."}
                    self._record_event(record, response["status"], None)
                    return response
                self._delete_managed()
                response = {"status": "completed", "action": record.action,
                        "version": None, "recovery": self._recovery(record.previous_version)}
                self._record_event(record, response["status"], None)
                return response
            pinned = self._pinned_version()
            if record.action == "pin":
                if pinned != record.version:
                    self._mark_uncertain(record.previous_version or "unknown")
                    response = {"status": "uncertain", "action": record.action,
                            "message": "The pin operation returned success but could not be verified."}
                    self._record_event(record, response["status"], record.previous_version)
                    return response
                self._save_pin(record.version)
            elif record.action == "unpin":
                if pinned is not False:
                    self._mark_uncertain(record.previous_version or "unknown")
                    response = {"status": "uncertain", "action": record.action,
                            "message": "The pin removal returned success but could not be verified."}
                    self._record_event(record, response["status"], record.previous_version)
                    return response
                self._delete_pin()
            response = {"status": "completed", "action": record.action,
                    "version": record.version if record.action == "pin" else record.previous_version,
                    "recovery": None}
            self._record_event(record, response["status"], response["version"])
            return response

    def _command(self, *arguments, timeout=20):
        if not self._executable:
            raise SoftwareManagementError("WinGet is unavailable")
        return self._run([self._executable, *arguments], timeout=timeout)

    def _run(self, args, *, timeout):
        result = self._runner(args, capture_output=True, text=True, timeout=timeout,
                              check=False, shell=False)
        stdout = result.stdout if isinstance(result.stdout, str) else ""
        encoded = stdout.encode("utf-8", errors="replace")
        too_large = len(encoded) > MAX_OUTPUT
        bounded = encoded[:MAX_OUTPUT].decode("utf-8", errors="ignore")
        return SimpleNamespace(returncode=result.returncode, stdout=bounded,
                               stderr="", output_truncated=too_large)

    def _installed(self):
        # Pin selectors lack a scope filter, so refuse ambiguity when a
        # machine-wide copy also exists.
        machine = self._scope_install("machine")
        if machine is None or isinstance(machine, str):
            return None
        return self._scope_install("user")

    def _scope_install(self, scope):
        try:
            result = self._command("list", "--id", PACKAGE_ID, "--exact", "--scope", scope,
                                   "--details", "--disable-interactivity")
        except (SoftwareManagementError, subprocess.TimeoutExpired, OSError):
            return None
        output = result.stdout or ""
        if result.output_truncated:
            return None
        if "No installed package found" in output or "No package found" in output:
            return False
        if result.returncode != 0:
            return None
        if PACKAGE_ID not in output:
            return None
        match = (re.search(r"(?m)^Version:\s*([0-9]+(?:\.[0-9]+){1,3})\s*$", output)
                 or re.search(rf"(?m)^.*{re.escape(PACKAGE_ID)}\s+([0-9]+(?:\.[0-9]+){{1,3}})\s+.*$", output))
        return match.group(1) if match else None

    def _installation_location(self):
        try:
            result = self._command("list", "--id", PACKAGE_ID, "--exact", "--scope", "user",
                                   "--details", "--disable-interactivity")
        except (SoftwareManagementError, subprocess.TimeoutExpired, OSError):
            return None
        output = result.stdout if isinstance(result.stdout, str) else ""
        if result.returncode != 0 or result.output_truncated:
            return None
        match = re.search(r"(?mi)^\s*Installed Location:\s*([A-Za-z]:\\[^\r\n]{1,512})\s*$", output)
        return match.group(1).rstrip("\\") if match else None

    def _catalog_version(self, version):
        try:
            versions = self._command("show", "--id", PACKAGE_ID, "--exact", "--source", SOURCE,
                                     "--versions", "--locale", "en-US", "--disable-interactivity",
                                     "--accept-source-agreements")
            if versions.returncode != 0 or versions.output_truncated:
                return False, None
            listed = {line.strip() for line in (versions.stdout or "").splitlines()}
            if version not in listed:
                return False, None
            detail = self._command("show", "--id", PACKAGE_ID, "--exact", "--source", SOURCE,
                                   "--version", version, "--locale", "en-US",
                                   "--disable-interactivity", "--accept-source-agreements")
            if detail.returncode != 0:
                return False, None
            output = detail.stdout or ""
            if detail.output_truncated:
                return False, None
            id_ok = re.search(r"(?m)^Found Microsoft Visual Studio Code \[Microsoft\.VisualStudioCode\]$", output)
            version_ok = re.search(rf"(?m)^Version:\s*{re.escape(version)}\s*$", output)
            scope_ok = bool(re.search(r"(?im)^\s*Installer Url:\s*[^\r\n]*VSCodeUserSetup[^\r\n]*\.exe", output))
            digest = re.search(r"(?mi)^\s*Installer SHA256:\s*([0-9a-f]{64})\s*$", output)
            if not (id_ok and version_ok and scope_ok and digest and HASH_RE.fullmatch(digest.group(1))):
                return False, None
            return True, digest.group(1).lower()
        except (SoftwareManagementError, subprocess.TimeoutExpired, OSError):
            return False, None

    def _operation_args(self, preview):
        base = ["--id", PACKAGE_ID, "--exact", "--source", SOURCE,
                "--scope", "user", "--disable-interactivity"]
        if preview.action == "install":
            return [self._executable, "install", *base, "--version", preview.version,
                    "--accept-package-agreements", "--accept-source-agreements"]
        if preview.action in {"update", "version"}:
            return [self._executable, "upgrade", *base, "--version", preview.version,
                    "--accept-package-agreements", "--accept-source-agreements"]
        if preview.action == "remove":
            return [self._executable, "uninstall", *base, "--version", preview.previous_version]
        if preview.action == "pin":
            return [self._executable, "pin", "add", "--id", PACKAGE_ID, "--exact",
                    "--source", SOURCE, "--version", preview.version,
                    "--accept-source-agreements", "--disable-interactivity"]
        return [self._executable, "pin", "remove", "--id", PACKAGE_ID, "--exact",
                "--source", SOURCE, "--disable-interactivity"]

    def _managed(self):
        connection = get_connection()
        try:
            row = connection.execute("SELECT version, state FROM managed_software WHERE package_id=? AND source=? AND scope='user'",
                                     (PACKAGE_ID, SOURCE)).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def _save_managed(self, version):
        connection = get_connection()
        try:
            connection.execute("INSERT INTO managed_software(package_id,version,source,scope,state) VALUES(?,?,?,'user','managed') ON CONFLICT(package_id) DO UPDATE SET version=excluded.version, source=excluded.source, scope=excluded.scope, state='managed', updated_at=CURRENT_TIMESTAMP",
                               (PACKAGE_ID, version, SOURCE))
            connection.commit()
        finally:
            connection.close()

    def _mark_uncertain(self, version):
        self._save_managed(version)
        connection = get_connection()
        try:
            connection.execute("UPDATE managed_software SET state='uncertain' WHERE package_id=?", (PACKAGE_ID,))
            connection.commit()
        finally:
            connection.close()

    def _delete_managed(self):
        connection = get_connection()
        try:
            connection.execute("DELETE FROM managed_software WHERE package_id=?", (PACKAGE_ID,))
            connection.commit()
        finally:
            connection.close()

    def _pinned_version(self):
        try:
            result = self._command("pin", "list", "--id", PACKAGE_ID, "--exact", "--disable-interactivity")
        except (SoftwareManagementError, subprocess.TimeoutExpired, OSError):
            return None
        if result.returncode != 0:
            return None
        if result.output_truncated:
            return None
        output = result.stdout or ""
        if "There are no pins configured." in output or "No package pins found." in output:
            return False
        match = re.search(r"(?m)^.*Microsoft\.VisualStudioCode\s+([0-9]+(?:\.[0-9]+){1,3})\s*$", output)
        return match.group(1) if match else None

    def _save_pin(self, version):
        connection = get_connection()
        try:
            connection.execute("INSERT INTO managed_software_pins(package_id,version) VALUES(?,?) ON CONFLICT(package_id) DO UPDATE SET version=excluded.version, updated_at=CURRENT_TIMESTAMP",
                               (PACKAGE_ID, version))
            connection.commit()
        finally:
            connection.close()

    def _delete_pin(self):
        connection = get_connection()
        try:
            connection.execute("DELETE FROM managed_software_pins WHERE package_id=?", (PACKAGE_ID,))
            connection.commit()
        finally:
            connection.close()

    def _record_event(self, preview, status, result_version):
        connection = get_connection()
        try:
            connection.execute("INSERT INTO managed_software_events(action,status,from_version,requested_version,result_version,preview_sha256) VALUES(?,?,?,?,?,?)",
                               (preview.action, status, preview.previous_version, preview.version,
                                result_version, preview.digest))
            connection.execute("DELETE FROM managed_software_events WHERE id NOT IN (SELECT id FROM managed_software_events ORDER BY id DESC LIMIT 100)")
            connection.commit()
        finally:
            connection.close()

    def _pinned_version_record(self):
        connection = get_connection()
        try:
            row = connection.execute("SELECT version FROM managed_software_pins WHERE package_id=?", (PACKAGE_ID,)).fetchone()
            return row["version"] if row else None
        finally:
            connection.close()

    def _recent_events(self):
        connection = get_connection()
        try:
            rows = connection.execute("SELECT action,status,from_version,requested_version,result_version,preview_sha256,created_at FROM managed_software_events ORDER BY id DESC LIMIT 10").fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def _recovery(self, version):
        if not version:
            return None
        verified, digest = self._catalog_version(version)
        if not verified:
            return None
        return {"action": "install_exact_previous_version", "version": version,
                "source": SOURCE, "scope": "user", "installer_sha256": digest,
                "requires_new_preview_and_owner_confirmation": True}

    def _operation_recovery(self, preview):
        # WinGet has no verified exact-version downgrade contract for an
        # installed Inno package; exact reinstall is offered only after removal.
        return self._recovery(preview.previous_version) if preview.action == "remove" else None

    def _prune(self):
        now = self._clock()
        self._previews = {key: value for key, value in self._previews.items() if value.expires > now}


def _is_elevated_process() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return True


def _version_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))
