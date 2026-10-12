"""Bounded read-only inventory of the current application and configured services."""

from __future__ import annotations

from datetime import datetime, timezone
import platform
import re
import os
import subprocess
from pathlib import Path

MAX_INVENTORY_RECORDS = 128
_REVISION = re.compile(r"\A[0-9a-f]{7,64}\Z")
_REF = re.compile(r"\A[\w./-]{1,128}\Z")


def _git_environment() -> dict[str, str]:
    """Keep caller Git overrides and user/system config out of the fixed probe."""
    inherited = {key.upper(): value for key, value in os.environ.items()}
    environment = {
        key: inherited[key]
        for key in ("PATH", "SYSTEMROOT", "WINDIR")
        if key in inherited
    }
    environment.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
    })
    return environment


def _checkout_record(root: Path, observed_at: str) -> dict:
    """Read only the fixed current checkout metadata, with a short process bound."""
    record = {
        "id": "repository:current",
        "kind": "repository_checkout",
        "name": "ERSELMETZ AI source checkout",
        "source": "fixed application checkout",
        "version": None,
        "revision": None,
        "status": "unknown",
        "management": "system_owned",
        "dependent_workflows": ["maintenance:review", "maintenance:activation"],
        "observed_at": observed_at,
    }
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel", "--verify", "HEAD"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
            shell=False,
            env=_git_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return record
    lines = result.stdout.splitlines()
    if result.returncode != 0 or len(lines) != 2:
        return record
    top_level, revision = lines
    try:
        matches_root = Path(top_level).resolve() == root.resolve()
    except (OSError, RuntimeError, ValueError):
        return record
    if not matches_root or not _REVISION.fullmatch(revision):
        return record
    try:
        branch_result = subprocess.run(
            ["git", "-C", str(root), "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
            shell=False,
            env=_git_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return record
    branch = branch_result.stdout.strip()
    if branch_result.returncode != 0 or (branch and not _REF.fullmatch(branch)):
        return record
    record.update(status="detected", revision=revision, version=branch or "detached HEAD")
    return record


def build_software_inventory(
    *,
    checkout_root: Path,
    provider_connections: tuple[dict, ...] | list[dict] = (),
    assignments: tuple[object, ...] | list[object] = (),
    application_version: str = "unknown",
    now: datetime | None = None,
) -> dict:
    """Build a capped inventory snapshot without probing networks or package managers."""
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    observed_at = observed.astimezone(timezone.utc).isoformat()
    records: list[dict] = [
        {
            "id": "application:erselmetz-ai",
            "kind": "application",
            "name": "ERSELMETZ AI",
            "source": "running application metadata",
            "version": application_version[:128] if isinstance(application_version, str) else "unknown",
            "revision": None,
            "status": "running",
            "management": "system_owned",
            "dependent_workflows": ["coordinator_chat", "task_dispatch", "maintenance"],
            "observed_at": observed_at,
        },
        {
            "id": "runtime:python",
            "kind": "runtime",
            "name": "Python runtime",
            "source": "current process",
            "version": platform.python_version(),
            "revision": None,
            "status": "running",
            "management": "externally_managed",
            "dependent_workflows": ["python_backend"],
            "observed_at": observed_at,
        },
        _checkout_record(checkout_root, observed_at),
    ]
    assignment_agents: dict[str, list[str]] = {}
    for assignment in assignments[:MAX_INVENTORY_RECORDS]:
        provider_id = getattr(assignment, "provider_id", None)
        agent_id = getattr(assignment, "agent_id", None)
        if isinstance(provider_id, str) and isinstance(agent_id, str):
            assignment_agents.setdefault(provider_id, []).append(agent_id[:128])
    for item in provider_connections[:MAX_INVENTORY_RECORDS]:
        provider_id = item.get("provider_id")
        if not isinstance(provider_id, str):
            continue
        provider_type = item.get("provider_type")
        source = item.get("source")
        models = item.get("models", [])
        if not isinstance(models, list):
            models = []
        models = [value[:128] for value in models[:64] if isinstance(value, str)]
        state = item.get("state")
        if state not in {"available", "unavailable", "unknown", "stale", "expired", "empty"}:
            state = "unknown"
        checked_at = item.get("checked_at")
        if not isinstance(checked_at, str) or len(checked_at) > 64:
            checked_at = None
        records.append({
            "id": provider_id[:128],
            "kind": "integration",
            "name": str(item.get("name", provider_id))[:256],
            "source": source[:256] if isinstance(source, str) else "configured provider connection",
            "version": None,
            "revision": None,
            "status": state,
            "management": "system_owned_configuration",
            "models": models,
            "dependent_workflows": [f"agent:{agent_id}" for agent_id in assignment_agents.get(provider_id, [])[:64]],
            "observed_at": checked_at or observed_at,
        })
        if len(records) >= MAX_INVENTORY_RECORDS:
            break
    if len(records) == 3:
        records.append({
            "id": "integrations:configured",
            "kind": "integration_summary",
            "name": "Configured provider integrations",
            "source": "in-process provider connection registry",
            "version": None,
            "revision": None,
            "status": "not_configured",
            "management": "system_owned_configuration",
            "dependent_workflows": [],
            "observed_at": observed_at,
        })
    return {
        "generated_at": observed_at,
        "items": records[:MAX_INVENTORY_RECORDS],
        "limitations": [
            "Only the running application, its Python runtime, its fixed source checkout, and configured provider connections are inspected.",
            "Windows installed applications, arbitrary directories, package managers, credentials, and remote services are not scanned.",
            "Externally managed software is informational; this panel does not install, update, or remove software.",
            "Repository revision and integration assignment records are sequential observations, not an atomic snapshot.",
        ],
    }
