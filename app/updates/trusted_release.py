"""Owner-triggered verification and staging for the pinned GitHub release origin."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization

from app.database.connection import DATABASE_PATH

RELEASES_API = "https://api.github.com/repos/erselmetz/ai-corporation/releases/latest"
PUBLIC_KEY_DER = "MCowBQYDK2VwAyEAzt6RxiEwcC77/sZ50IZTc5CEfOBxtNomA/uJC3Zw7s8="
CURRENT_APP_VERSION = os.environ.get("ERSELMETZ_APP_VERSION", "0.1.0")
CURRENT_CONFIGURATION_VERSION = 1
MAX_METADATA_BYTES = 64 * 1024
MAX_INSTALLER_BYTES = 2 * 1024 * 1024 * 1024
ALLOWED_DOWNLOAD_HOSTS = frozenset({
    "api.github.com", "github.com", "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
})
_VERSION = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class TrustedReleaseError(RuntimeError):
    """A safe, bounded release verification or staging failure."""


@dataclass(frozen=True)
class TrustedRelease:
    version: str
    available: bool
    release_notes: str
    installer_name: str
    installer_sha256: str
    from_configuration: int
    to_configuration: int
    migration_preview: str

    def response(self) -> dict[str, object]:
        return asdict(self)


class TrustedReleaseService:
    def __init__(self, data_directory: Path, *, database_path: Path = DATABASE_PATH,
                 public_key_der: str = PUBLIC_KEY_DER, transport=None,
                 current_version: str = CURRENT_APP_VERSION):
        self._data_directory = Path(data_directory).resolve()
        self._database_path = Path(database_path).resolve()
        self._public_key_der = public_key_der
        self._transport = transport
        self._current_version = current_version

    def check(self) -> TrustedRelease:
        try:
            with httpx.Client(transport=self._transport, timeout=httpx.Timeout(8.0), follow_redirects=False) as client:
                release_payload = self._get_json(client, RELEASES_API, MAX_METADATA_BYTES)
                if not isinstance(release_payload, dict) or not isinstance(release_payload.get("assets"), list):
                    raise TrustedReleaseError("GitHub release metadata is invalid.")
                assets = release_payload["assets"]
                manifest_bytes = self._read_asset(client, assets, "erselmetz-release.json", MAX_METADATA_BYTES)
                signature = self._read_asset(client, assets, "erselmetz-release.sig", 256).decode("ascii").strip()
                manifest = self._verify_manifest(manifest_bytes, signature)
                if release_payload.get("tag_name") != f"v{manifest.version}":
                    raise TrustedReleaseError("The signed version does not match the GitHub release tag.")
                return TrustedRelease(
                    version=manifest.version,
                    available=_compare_versions(manifest.version, self._current_version) > 0,
                    release_notes=manifest.release_notes,
                    installer_name=manifest.installer_name,
                    installer_sha256=manifest.installer_sha256,
                    from_configuration=manifest.from_configuration,
                    to_configuration=manifest.to_configuration,
                    migration_preview=manifest.migration_preview,
                )
        except TrustedReleaseError:
            raise
        except (httpx.HTTPError, OSError, UnicodeError, ValueError) as exc:
            raise TrustedReleaseError("The trusted release could not be checked.") from exc

    def prepare(self, version: str) -> dict[str, object]:
        release = self.check()
        if not release.available or release.version != version:
            raise TrustedReleaseError("The verified release changed or is not newer than this app.")
        current_configuration = self._read_configuration_version()
        if release.from_configuration != current_configuration:
            raise TrustedReleaseError("This release is incompatible with the current configuration version.")
        if release.to_configuration < release.from_configuration or release.to_configuration > CURRENT_CONFIGURATION_VERSION:
            raise TrustedReleaseError("This release requires an unsupported configuration migration.")

        update_dir = self._data_directory / "updates"
        update_dir.mkdir(parents=True, exist_ok=True)
        installer_path = update_dir / release.installer_name
        partial_path = update_dir / f"{release.installer_name}.partial"
        try:
            self._download_verified(release, partial_path)
            backup_path = self._backup_database(update_dir / "backups", release.version)
            os.replace(partial_path, installer_path)
            return {
                "version": release.version,
                "installer_name": release.installer_name,
                "installer_path": str(installer_path),
                "installer_sha256": release.installer_sha256,
                "backup_path": str(backup_path),
                "configuration_version": current_configuration,
                "message": "The signed installer and SQLite recovery backup are ready. Close ERSELMETZ AI before manually running the installer.",
            }
        except TrustedReleaseError:
            partial_path.unlink(missing_ok=True)
            raise
        except (OSError, httpx.HTTPError, sqlite3.Error) as exc:
            partial_path.unlink(missing_ok=True)
            raise TrustedReleaseError("The update could not be staged safely.") from exc

    def _read_configuration_version(self) -> int:
        if not self._database_path.exists():
            raise TrustedReleaseError("Application data is unavailable for migration preview.")
        try:
            with sqlite3.connect(self._database_path) as connection:
                value = connection.execute("PRAGMA user_version").fetchone()[0]
        except sqlite3.Error as exc:
            raise TrustedReleaseError("Application configuration version could not be read.") from exc
        if type(value) is not int or value < 0 or value > CURRENT_CONFIGURATION_VERSION:
            raise TrustedReleaseError("Application configuration is newer than this release supports.")
        return value

    def _backup_database(self, backup_directory: Path, version: str) -> Path:
        if not self._database_path.is_file():
            raise TrustedReleaseError("Application database is unavailable for recovery backup.")
        backup_directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
        backup_path = backup_directory / f"pre-update-{version}-{stamp}.sqlite3"
        source = sqlite3.connect(self._database_path, timeout=5)
        target = sqlite3.connect(backup_path)
        try:
            source.backup(target)
            if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise sqlite3.DatabaseError("backup integrity check failed")
            target.commit()
        except sqlite3.Error:
            backup_path.unlink(missing_ok=True)
            raise
        finally:
            target.close()
            source.close()
        if backup_path.stat().st_size == 0:
            backup_path.unlink(missing_ok=True)
            raise TrustedReleaseError("Recovery backup verification failed.")
        return backup_path

    def _download_verified(self, release: TrustedRelease, partial_path: Path) -> None:
        try:
            with httpx.Client(transport=self._transport, timeout=httpx.Timeout(30.0), follow_redirects=False) as client:
                payload = self._get_json(client, RELEASES_API, MAX_METADATA_BYTES)
                if not isinstance(payload, dict):
                    raise TrustedReleaseError("GitHub release metadata is invalid.")
                if payload.get("tag_name") != f"v{release.version}":
                    raise TrustedReleaseError("The GitHub release changed; check it again before staging.")
                asset = _find_asset(payload.get("assets"), release.installer_name)
                response = self._request(client, asset["url"], max_bytes=MAX_INSTALLER_BYTES, stream=True)
                digest = hashlib.sha256()
                size = 0
                try:
                    with partial_path.open("xb") as output:
                        for chunk in response.iter_bytes(1024 * 1024):
                            size += len(chunk)
                            if size > MAX_INSTALLER_BYTES:
                                raise TrustedReleaseError("Installer exceeds the allowed size.")
                            digest.update(chunk)
                            output.write(chunk)
                finally:
                    response.close()
                if size <= 0 or digest.hexdigest() != release.installer_sha256:
                    raise TrustedReleaseError("Installer integrity verification failed.")
        except TrustedReleaseError:
            raise
        except (httpx.HTTPError, OSError, ValueError) as exc:
            raise TrustedReleaseError("The signed installer could not be downloaded safely.") from exc

    def _get_json(self, client: httpx.Client, url: str, max_bytes: int) -> object:
        response = self._request(client, url, max_bytes=max_bytes)
        data = response.content
        if len(data) > max_bytes:
            raise TrustedReleaseError("Release metadata exceeds the allowed size.")
        try:
            return json.loads(data)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise TrustedReleaseError("GitHub release metadata is malformed.") from exc

    def _read_asset(self, client: httpx.Client, assets: object, name: str, max_bytes: int) -> bytes:
        asset = _find_asset(assets, name)
        response = self._request(client, asset["url"], max_bytes=max_bytes)
        if len(response.content) > max_bytes:
            raise TrustedReleaseError("Release metadata exceeds the allowed size.")
        return response.content

    def _request(self, client: httpx.Client, url: str, *, max_bytes: int, stream: bool = False):
        current = _trusted_github_url(url)
        for _ in range(5):
            response = client.send(client.build_request(
                "GET", current,
                headers={"Accept": "application/vnd.github+json" if urlsplit(current).hostname == "api.github.com" else "application/octet-stream",
                         "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "ERSELMETZ-AI-Updater"},
                extensions={"timeout": {"connect": 8.0, "read": 30.0 if stream else 8.0, "write": 8.0, "pool": 8.0}},
            ), stream=stream)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                response.close()
                if not location:
                    raise TrustedReleaseError("Release source redirect was invalid.")
                current = _trusted_github_url(urljoin(current, location))
                continue
            if response.status_code != 200:
                response.close()
                raise TrustedReleaseError("The trusted GitHub release is unavailable.")
            declared = response.headers.get("content-length")
            if declared and int(declared) > max_bytes:
                response.close()
                raise TrustedReleaseError("Release content exceeds the allowed size.")
            if not stream:
                content = bytearray()
                for chunk in response.iter_bytes(8192):
                    content.extend(chunk)
                    if len(content) > max_bytes:
                        response.close()
                        raise TrustedReleaseError("Release metadata exceeds the allowed size.")
                response.close()
                response = httpx.Response(
                    200, headers=response.headers, content=bytes(content), request=response.request,
                )
            return response
        raise TrustedReleaseError("GitHub release redirect limit exceeded.")

    def _verify_manifest(self, raw: bytes, signature: str) -> TrustedRelease:
        if len(raw) > MAX_METADATA_BYTES or len(signature) > 256:
            raise TrustedReleaseError("Signed release metadata is invalid.")
        try:
            sig = base64.b64decode(signature, validate=True)
            public_key = serialization.load_der_public_key(base64.b64decode(self._public_key_der, validate=True))
            public_key.verify(sig, raw)
            payload = json.loads(raw)
        except (ValueError, TypeError, UnicodeError, json.JSONDecodeError, InvalidSignature) as exc:
            raise TrustedReleaseError("Release signature verification failed.") from exc
        if not isinstance(payload, dict) or set(payload) != {"version", "releaseNotes", "artifact", "configuration"}:
            raise TrustedReleaseError("Signed release metadata has an unsupported format.")
        version = payload["version"]
        notes = payload["releaseNotes"]
        artifact = payload["artifact"]
        configuration = payload["configuration"]
        if (not isinstance(version, str) or not _VERSION.fullmatch(version)
                or not isinstance(notes, str) or len(notes) > 12000
                or not isinstance(artifact, dict) or set(artifact) != {"name", "sha256"}
                or artifact["name"] != f"ERSELMETZ-AI-Setup-{version}-win-x64.exe"
                or not isinstance(artifact["sha256"], str) or not _SHA256.fullmatch(artifact["sha256"])
                or not isinstance(configuration, dict)
                or set(configuration) != {"fromVersion", "toVersion", "preview"}
                or not all(type(configuration[key]) is int and configuration[key] >= 0
                           for key in ("fromVersion", "toVersion"))
                or not isinstance(configuration["preview"], str) or len(configuration["preview"]) > 1200):
            raise TrustedReleaseError("Signed release metadata has invalid fields.")
        return TrustedRelease(
            version=version, available=_compare_versions(version, self._current_version) > 0,
            release_notes=notes, installer_name=artifact["name"], installer_sha256=artifact["sha256"],
            from_configuration=configuration["fromVersion"], to_configuration=configuration["toVersion"],
            migration_preview=configuration["preview"],
        )


def _find_asset(assets: object, name: str) -> dict[str, object]:
    if not isinstance(assets, list) or len(assets) > 100:
        raise TrustedReleaseError("GitHub release asset list is invalid.")
    matches = [item for item in assets if isinstance(item, dict) and item.get("name") == name]
    if len(matches) != 1:
        raise TrustedReleaseError("A required signed release asset is missing or duplicated.")
    asset = matches[0]
    asset_url = asset.get("url")
    if not isinstance(asset_url, str):
        raise TrustedReleaseError("GitHub release asset URL is invalid.")
    parsed = urlsplit(_trusted_github_url(asset_url))
    if parsed.hostname != "api.github.com" or not re.fullmatch(r"/repos/erselmetz/ai-corporation/releases/assets/\d+", parsed.path):
        raise TrustedReleaseError("Release asset is outside the configured repository.")
    return asset


def _trusted_github_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_DOWNLOAD_HOSTS
                or parsed.username or parsed.password or parsed.port not in {None, 443}):
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise TrustedReleaseError("Update source is outside the trusted GitHub release origin.") from exc
    return value


def _compare_versions(left: str, right: str) -> int:
    def parse(value: str) -> tuple[tuple[int, ...], bool]:
        base, separator, _suffix = value.partition("-")
        return tuple(int(part) for part in base.split(".")), bool(separator)
    left_parts, left_pre = parse(left)
    right_parts, right_pre = parse(right)
    if left_parts != right_parts:
        return (left_parts > right_parts) - (left_parts < right_parts)
    return (right_pre > left_pre) - (right_pre < left_pre)
