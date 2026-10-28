"""Local, read-only restart and performance evidence for release review."""
from __future__ import annotations

from datetime import datetime, timezone
import os
import platform
import sys
from typing import Any


def process_memory() -> dict[str, Any]:
    """Return current process working-set bytes where the standard library can measure it."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class ProcessMemoryCounters(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t),
                ]

            counters = ProcessMemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            process = kernel32.GetCurrentProcess()
            reader = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
            reader.argtypes = (wintypes.HANDLE, ctypes.POINTER(ProcessMemoryCounters), wintypes.DWORD)
            reader.restype = wintypes.BOOL
            if reader(process, ctypes.byref(counters), counters.cb):
                return {"state": "measured", "bytes": int(counters.WorkingSetSize),
                        "source": "Windows process working set"}
        elif sys.platform.startswith("linux"):
            with open("/proc/self/statm", "r", encoding="ascii") as stream:
                pages = int(stream.read().split()[1])
            return {"state": "measured", "bytes": pages * os.sysconf("SC_PAGE_SIZE"),
                    "source": "Linux resident set size"}
    except (OSError, ValueError, IndexError, AttributeError, ImportError):
        pass
    return {"state": "unknown", "bytes": None,
            "reason": "Current process memory is not measurable on this platform."}


def readiness_snapshot(*, application_service, app_started_at: datetime,
                       startup_setup_ms: float, observed_at: datetime | None = None,
                       memory_reader=process_memory) -> dict[str, Any]:
    observed_at = observed_at or datetime.now(timezone.utc)
    try:
        registered_assignments = application_service.list_models()
        assignments = [
            {"agent_id": item.agent_id, "provider_id": item.provider_id, "model_id": item.model_id}
            for item in registered_assignments[:100]
        ]
        omitted_assignments = max(0, len(registered_assignments) - len(assignments))
        assignment_state = "available"
    except Exception:
        assignments = []
        omitted_assignments = 0
        assignment_state = "unknown"

    try:
        entries = application_service.execution_queue().list_active(limit=100)
        previous_claims = [
            {"entry_id": entry.id, "task_id": entry.task_id, "state": "outcome_unknown",
             "claimed_at": entry.updated_at.isoformat(), "resolution_required": True}
            for entry in entries
            if entry.state.value == "claimed" and entry.updated_at <= app_started_at
        ]
        recovery_state = "available"
    except Exception:
        previous_claims = []
        recovery_state = "unknown"

    return {
        "observed_at": observed_at.isoformat(),
        "retention": "response snapshot only; not persisted",
        "conditions": {
            "platform": platform.system() or "unknown",
            "platform_release": platform.release() or "unknown",
            "machine": platform.machine() or "unknown",
            "python": platform.python_version(),
            "workloads": {
                "startup": "local Python app-factory setup",
                "memory": "current local backend process working set/RSS",
                "rendering": "separate same-device Three.js visualization measurement",
                "model": "recorded assignments only; no inference request",
            },
            "model_assignments_state": assignment_state,
            "model_assignments": assignments,
            "model_assignment_limit": 100,
            "omitted_model_assignment_count": omitted_assignments,
        },
        "recovery": {
            "state": recovery_state,
            "preexisting_claims": previous_claims,
            "automatic_replay": False,
            "guidance": "A claim present before this app run may have an uncertain outcome. Inspect and explicitly resolve it; this report never replays work.",
        },
        "measurements": {
            "startup_setup": {
                "state": "measured", "milliseconds": round(max(0.0, startup_setup_ms), 3),
                "scope": "local app factory setup only; excludes Python imports, process launch, ASGI startup and Electron startup",
            },
            "process_memory": _memory_snapshot(memory_reader),
            "rendering": {
                "state": "unknown",
                "evidence_page": "native:Brain",
                "reason": "Rendering measurements are collected on the local browser device and are not sent to this backend report.",
            },
            "model_workload": {
                "state": "unknown",
                "reason": "No explicit model workload benchmark has been run. Assignments describe conditions only and are not performance evidence.",
                "provider_calls": 0,
            },
            "hardware_fit": {
                "state": "unknown",
                "reason": "No hardware recommendation thresholds are set; software slots and model labels do not prove fit.",
            },
        },
    }


def _memory_snapshot(memory_reader):
    try:
        return memory_reader()
    except Exception:
        return {"state": "unknown", "bytes": None,
                "reason": "Current process memory is not measurable on this platform."}
