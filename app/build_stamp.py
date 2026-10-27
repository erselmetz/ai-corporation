"""Version and source identity for the running backend."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import json


def _packaged_stamp():
    """Frozen apps require matching inner and distribution build identities."""
    if not getattr(sys,'frozen',False):return None
    inner=Path(__file__).with_name('build_metadata.json')
    outer=Path(sys.executable).with_name('build-stamp.json')
    try:
        if inner.stat().st_size>4096 or outer.stat().st_size>4096:raise ValueError('oversized stamp')
        stamp=json.loads(inner.read_text(encoding='utf-8'))
        if stamp!=json.loads(outer.read_text(encoding='utf-8')):raise ValueError('stamp mismatch')
        if set(stamp)!={'version','commit','source_sha256','review_build'}:raise ValueError('invalid stamp')
        if not isinstance(stamp['version'],str) or not 1<=len(stamp['version'])<=32:raise ValueError('invalid version')
        for key,size in [('commit',40),('source_sha256',64)]:
            if not isinstance(stamp[key],str) or len(stamp[key])!=size or any(c not in '0123456789abcdef' for c in stamp[key]):raise ValueError('invalid source identity')
        if type(stamp['review_build']) is not bool:raise ValueError('invalid review flag')
        return stamp
    except (OSError,ValueError,TypeError) as error:
        raise RuntimeError('The application build stamp is missing or inconsistent. Reinstall the verified application.') from error


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


BUILD_STAMP = _packaged_stamp() or {
    "version": os.environ.get("ERSELMETZ_APP_VERSION", "0.1.0")[:32],
    "commit": _source_commit(),
}
