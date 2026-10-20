"""Version and source identity for the running backend."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def _source_commit() -> str:
    configured = os.environ.get("ERSELMETZ_BUILD_COMMIT", "").strip()
    if configured and len(configured) <= 64 and all(ch in "0123456789abcdefABCDEF-" for ch in configured):
        return configured.lower()
    if getattr(sys, "frozen", False):
        return "unknown"
    root = Path(__file__).resolve().parents[1]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"], cwd=root,
            check=True, capture_output=True, text=True, timeout=1.0,
        )
    except (OSError, subprocess.SubprocessError):
        return "development"
    value = result.stdout.strip()
    return value if value and all(ch in "0123456789abcdefABCDEF" for ch in value) else "unknown"


BUILD_STAMP = {
    "version": os.environ.get("ERSELMETZ_APP_VERSION", "0.1.0")[:32],
    "commit": _source_commit(),
}
