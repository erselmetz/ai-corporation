"""Non-secret, local-only first-run configuration persisted in SQLite."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
from urllib.parse import urlsplit

import httpx

from app.providers import OllamaProvider

from app.database import get_connection


_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_OLLAMA_URL = "http://127.0.0.1:11434"


@dataclass(frozen=True, slots=True)
class FirstRunConfiguration:
    completed: bool
    skipped: bool
    provider_type: str
    provider_id: str | None
    model_id: str | None
    ollama_base_url: str | None
    gemini_models: tuple[str, ...]
    gemini_key_persisted: bool
    global_slots: int
    provider_slots: int
    model_slots: int


class FirstRunSetupStore:
    """Store allowlisted setup metadata; credential bytes never enter SQLite."""

    def initialize_for_new_owner(self, *, first_owner_run: bool) -> None:
        if first_owner_run is not True:
            return
        connection = get_connection()
        try:
            connection.execute(
                """INSERT OR IGNORE INTO local_first_run(singleton, updated_at)
                   VALUES (1, CURRENT_TIMESTAMP)"""
            )
            connection.commit()
        finally:
            connection.close()

    def get(self) -> FirstRunConfiguration | None:
        connection = get_connection()
        try:
            row = connection.execute(
                "SELECT * FROM local_first_run WHERE singleton = 1"
            ).fetchone()
            if row is None:
                return None
            try:
                models = json.loads(row["gemini_models"] or "[]")
            except (TypeError, ValueError):
                models = []
            if (not isinstance(models, list) or len(models) > 100
                    or any(not isinstance(item, str) or not _MODEL_ID.fullmatch(item)
                           for item in models)):
                models = []
            return FirstRunConfiguration(
                completed=bool(row["completed"]),
                skipped=bool(row["skipped"]),
                provider_type=row["provider_type"],
                provider_id=row["provider_id"],
                model_id=row["model_id"],
                ollama_base_url=row["ollama_base_url"],
                gemini_models=tuple(models),
                gemini_key_persisted=bool(row["gemini_key_persisted"]),
                global_slots=row["global_slots"],
                provider_slots=row["provider_slots"],
                model_slots=row["model_slots"],
            )
        finally:
            connection.close()

    def skip(self) -> None:
        self._update(
            "UPDATE local_first_run SET skipped = 1, updated_at = CURRENT_TIMESTAMP WHERE singleton = 1",
            (),
        )

    def complete_ollama(self, model_id: str) -> FirstRunConfiguration:
        if not isinstance(model_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}", model_id):
            raise ValueError("Ollama model identifier is invalid")
        self._update(
            """UPDATE local_first_run SET completed = 1, skipped = 0,
               provider_type = 'ollama', provider_id = 'ollama', model_id = ?,
               ollama_base_url = ?, gemini_models = NULL, gemini_key_persisted = 0,
               global_slots = 1, provider_slots = 1, model_slots = 1,
               updated_at = CURRENT_TIMESTAMP WHERE singleton = 1""",
            (model_id, _OLLAMA_URL),
        )
        result = self.get()
        if result is None:
            raise RuntimeError("First-run setup state is unavailable")
        return result

    def complete_gemini(self, model_id: str, models: tuple[str, ...], *, key_persisted: bool) -> FirstRunConfiguration:
        if not isinstance(key_persisted, bool):
            raise ValueError("Gemini credential persistence choice must be explicit")
        if not isinstance(model_id, str) or not _MODEL_ID.fullmatch(model_id):
            raise ValueError("Gemini model identifier is invalid")
        if (not isinstance(models, tuple) or not 1 <= len(models) <= 100
                or any(not isinstance(item, str) or not _MODEL_ID.fullmatch(item) for item in models)
                or model_id not in models):
            raise ValueError("Gemini model catalog is invalid")
        self._update(
            """UPDATE local_first_run SET completed = 1, skipped = 0,
               provider_type = 'gemini', provider_id = 'gemini', model_id = ?,
               ollama_base_url = NULL, gemini_models = ?, gemini_key_persisted = ?,
               global_slots = 1, provider_slots = 1, model_slots = 1,
               updated_at = CURRENT_TIMESTAMP WHERE singleton = 1""",
            (model_id, json.dumps(list(models), separators=(",", ":")), int(key_persisted)),
        )
        result = self.get()
        if result is None:
            raise RuntimeError("First-run setup state is unavailable")
        return result

    @staticmethod
    def _update(statement: str, values: tuple) -> None:
        connection = get_connection()
        try:
            cursor = connection.execute(statement, values)
            if cursor.rowcount != 1:
                raise RuntimeError("First-run setup has not been initialized for this owner")
            connection.commit()
        finally:
            connection.close()


class OllamaFirstRunService:
    """Owner-triggered fixed-model preview and bounded local Ollama pull."""

    MODEL_ID = "llama3.2:3b"
    BASE_URL = _OLLAMA_URL
    REGISTRY_MANIFEST = "https://registry.ollama.ai/v2/library/llama3.2/manifests/3b"
    MAX_MANIFEST_BYTES = 1024 * 1024
    MAX_MANIFEST_LAYERS = 256
    MAX_MODEL_BYTES = 100 * 1024 * 1024 * 1024
    MAX_PULL_LINE_BYTES = 64 * 1024
    _DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")

    def __init__(self, *, provider=None, client_factory=httpx.Client,
                 model_id: str | None = None, registry_manifest: str | None = None):
        self._provider = provider or OllamaProvider(self.BASE_URL)
        self._client_factory = client_factory
        self.model_id = model_id or self.MODEL_ID
        self.registry_manifest = registry_manifest or self.REGISTRY_MANIFEST
        manifest = urlsplit(self.registry_manifest) if isinstance(self.registry_manifest, str) else None
        if (not isinstance(self.model_id, str) or not _MODEL_ID.fullmatch(self.model_id)
                or manifest is None or manifest.scheme != "https" or manifest.hostname != "registry.ollama.ai"
                or manifest.username or manifest.password or manifest.query or manifest.fragment
                or not re.fullmatch(r"/v2/library/[A-Za-z0-9._-]+/manifests/[A-Za-z0-9._-]+", manifest.path)):
            raise ValueError("A fixed approved Ollama model and registry manifest are required")

    def status(self) -> dict:
        return self.status_for_model(self.model_id)

    def status_for_model(self, model_id: str | None) -> dict:
        inventory = self._provider.local_model_inventory()
        selected_model = model_id if isinstance(model_id, str) and _MODEL_ID.fullmatch(model_id) else self.model_id
        return {
            "state": inventory.state,
            "service_running": inventory.state == "available",
            "model_id": selected_model,
            "model_installed": selected_model in inventory.models if inventory.state == "available" else None,
            "source": inventory.source,
            "reason": inventory.reason,
        }

    def default_installed_chat_model(self, preferred: str = MODEL_ID) -> tuple[str, ...]:
        """Return bounded installed model IDs ordered by the reviewed default rule."""
        endpoint = self._provider
        inventory = endpoint.local_model_inventory()
        if inventory.state != "available" or not inventory.models:
            return ()
        if preferred in inventory.models:
            return (preferred,)
        candidates = []
        try:
            raw = endpoint._bounded_request("GET", "/api/tags", timeout=2.0)
            payload = json.loads(raw)
            entries = payload.get("models") if isinstance(payload, dict) else None
            if not isinstance(entries, list) or len(entries) > 100:
                return ()
            by_name = {entry.get("name"): entry.get("size") for entry in entries if isinstance(entry, dict)}
            candidates = sorted(inventory.models, key=lambda model: (by_name.get(model, 2**63), model))[:100]
        except Exception:
            return ()
        deadline = time.monotonic() + 5.0
        for model in candidates:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                raw = endpoint._bounded_request("POST", "/api/show", {"model": model}, timeout=min(1.0, remaining))
                details = json.loads(raw)
                capabilities = details.get("capabilities") if isinstance(details, dict) else None
                if isinstance(capabilities, list) and "completion" in capabilities:
                    return (model,)
            except Exception:
                continue
        return ()

    def preview_model(self) -> dict:
        headers = {"Accept": "application/vnd.ollama.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"}
        try:
            with self._client_factory(timeout=10.0, follow_redirects=False,
                                      trust_env=False) as client:
                with client.stream("GET", self.registry_manifest, headers=headers) as response:
                    response.raise_for_status()
                    digest = response.headers.get("docker-content-digest", "")
                    payload = bytearray()
                    for chunk in response.iter_bytes():
                        if len(payload) + len(chunk) > self.MAX_MANIFEST_BYTES:
                            raise ValueError("manifest too large")
                        payload.extend(chunk)
            if not digest and payload:
                digest = "sha256:" + hashlib.sha256(payload).hexdigest()
            data = json.loads(payload)
            if not isinstance(data, dict):
                raise ValueError("manifest invalid")
            layers = data.get("layers") if isinstance(data, dict) else None
            if (data.get("schemaVersion") not in {2, None} or not isinstance(layers, list)
                    or not 1 <= len(layers) <= self.MAX_MANIFEST_LAYERS
                    or not self._DIGEST.fullmatch(digest)):
                raise ValueError("manifest invalid")
            total = 0
            for layer in layers:
                size = layer.get("size") if isinstance(layer, dict) else None
                if type(size) is not int or not 0 <= size <= self.MAX_MODEL_BYTES:
                    raise ValueError("layer size invalid")
                total += size
                if total > self.MAX_MODEL_BYTES:
                    raise ValueError("model size invalid")
            if total <= 0:
                raise ValueError("model size missing")
            return {
                "model_id": self.model_id,
                "manifest_digest": digest,
                "manifest_bytes": total,
                "size_evidence": "official Ollama registry manifest; full layer total, before cache reuse",
                "available_space_bytes": self._available_default_space(),
                "destination": "Ollama's default per-user model directory; a custom OLLAMA_MODELS location cannot be inspected here",
                "registry_url": self.registry_manifest,
            }
        except (httpx.HTTPError, OSError, ValueError, TypeError, KeyError):
            raise ValueError("The official Ollama model-size estimate is unavailable. No model download was started.") from None

    def pull(self, *, expected_digest: str, expected_bytes: int):
        if (not isinstance(expected_digest, str) or not self._DIGEST.fullmatch(expected_digest)
                or type(expected_bytes) is not int or not 1 <= expected_bytes <= self.MAX_MODEL_BYTES):
            raise ValueError("Refresh the model-size estimate before downloading")
        preview = self.preview_model()
        if preview["manifest_digest"] != expected_digest or preview["manifest_bytes"] != expected_bytes:
            raise ValueError("The model registry manifest changed; review its size again before downloading")
        available = preview["available_space_bytes"]
        if isinstance(available, int) and available < expected_bytes:
            raise ValueError("Available space in Ollama's default model folder is below the full model estimate")
        started = time.monotonic()
        try:
            with self._client_factory(timeout=httpx.Timeout(connect=5, read=120, write=10, pool=5),
                                      follow_redirects=False, trust_env=False) as client:
                with client.stream(
                    "POST", f"{self.BASE_URL}/api/pull",
                    json={"model": self.model_id, "stream": True},
                ) as response:
                    response.raise_for_status()
                    line = bytearray()
                    for chunk in response.iter_bytes():
                        if time.monotonic() - started > 6 * 60 * 60:
                            raise ValueError("Ollama model pull exceeded the supported time limit")
                        line.extend(chunk)
                        if len(line) > self.MAX_PULL_LINE_BYTES:
                            raise ValueError("Ollama progress line exceeded the limit")
                        while b"\n" in line:
                            raw, _, remaining = line.partition(b"\n")
                            line = bytearray(remaining)
                            event = self._progress(raw)
                            yield json.dumps(event, separators=(",", ":")) + "\n"
                            if event.get("event") == "error":
                                return
                    if line.strip():
                        event = self._progress(bytes(line))
                        yield json.dumps(event, separators=(",", ":")) + "\n"
                        if event.get("event") == "error":
                            return
            result = self.status()
            if result["state"] != "available" or result["model_installed"] is not True:
                yield json.dumps({"event": "error", "message": "Ollama did not confirm the model in its installed-model inventory."}) + "\n"
                return
            yield json.dumps({"event": "complete", "message": "Ollama confirmed the recommended model is installed."}) + "\n"
        except GeneratorExit:
            # Closing the owner stream closes the Ollama request. Ollama may keep
            # reusable partial blobs; cancellation is not a claim of erasure.
            raise
        except (httpx.HTTPError, OSError, ValueError):
            yield json.dumps({"event": "error", "message": "Ollama download failed or was interrupted. Retry after checking the service and disk space; partial model data may remain."}) + "\n"

    @classmethod
    def _progress(cls, raw: bytes) -> dict:
        try:
            event = json.loads(raw)
            status = event.get("status") if isinstance(event, dict) else None
            if not isinstance(status, str):
                raise ValueError
            if "error" in event:
                return {"event": "error", "message": "Ollama could not download the recommended model. Check the local service and available disk space."}
            total, completed = event.get("total"), event.get("completed", 0)
            if total is not None and (type(total) is not int or not 0 <= total <= cls.MAX_MODEL_BYTES):
                raise ValueError
            if type(completed) is not int or not 0 <= completed <= cls.MAX_MODEL_BYTES:
                raise ValueError
            if total is not None and completed > total:
                raise ValueError
            return {"event": "progress", "status": status[:120],
                    "total": total, "completed": completed}
        except (ValueError, TypeError, json.JSONDecodeError):
            return {"event": "error", "message": "Ollama returned invalid download progress. No provider assignment was changed."}

    @staticmethod
    def _available_default_space() -> int | None:
        if os.environ.get("OLLAMA_MODELS"):
            return None
        root = Path(os.environ.get("USERPROFILE") or Path.home()) / ".ollama" / "models"
        candidate = root
        while not candidate.exists() and candidate != candidate.parent:
            candidate = candidate.parent
        try:
            return shutil.disk_usage(candidate).free
        except OSError:
            return None
