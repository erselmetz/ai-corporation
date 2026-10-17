"""Read-only, on-demand host inventory for cautious local model guidance."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import shutil
from typing import Any


@dataclass(frozen=True, slots=True)
class Observation:
    state: str
    value: Any
    unit: str | None
    source: str | None
    observed_at: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    observed_at: str
    cpu: Observation
    gpu: Observation
    memory: Observation
    disk: Observation
    recommendation: dict[str, str]


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def collect_hardware_profile(*, now: datetime | None = None) -> HardwareProfile:
    """Observe supported host facts once; never persist or transmit the result."""
    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    cpu = _observe_cpu(observed_at)
    gpu = _observe_gpu(observed_at)
    memory = _observe_memory(observed_at)
    disk = _observe_disk(observed_at)
    recommendation = _recommend(memory, gpu, disk)
    return HardwareProfile(observed_at, cpu, gpu, memory, disk, recommendation)


def profile_to_dict(profile: HardwareProfile) -> dict[str, Any]:
    def observation(value: Observation) -> dict[str, Any]:
        return {
            "state": value.state,
            "value": value.value,
            "unit": value.unit,
            "source": value.source,
            "observed_at": value.observed_at,
            "reason": value.reason,
        }

    return {
        "observed_at": profile.observed_at,
        "cpu": observation(profile.cpu),
        "gpu": observation(profile.gpu),
        "memory": observation(profile.memory),
        "disk": observation(profile.disk),
        "recommendation": profile.recommendation,
        "privacy": "Read-only local observation; not stored or uploaded.",
    }


def _unknown(timestamp: str, reason: str) -> Observation:
    return Observation("unknown", None, None, None, timestamp, reason)


def _wmi_service():
    if os.name != "nt":
        return None
    try:
        import win32com.client

        return win32com.client.GetObject(r"winmgmts:\\.\root\cimv2")
    except Exception:
        return None


def _observe_cpu(timestamp: str) -> Observation:
    service = _wmi_service()
    if service is not None:
        try:
            processors = tuple(service.ExecQuery(
                "SELECT Name, NumberOfCores, NumberOfLogicalProcessors FROM Win32_Processor"
            ))
            names = tuple(str(item.Name).strip()[:160] for item in processors if item.Name)
            if names:
                cores = sum(int(item.NumberOfCores or 0) for item in processors)
                logical = sum(int(item.NumberOfLogicalProcessors or 0) for item in processors)
                return Observation(
                    "observed",
                    {"name": "; ".join(names), "physical_cores": cores or None,
                     "logical_processors": logical or os.cpu_count()},
                    None,
                    "Windows WMI Win32_Processor",
                    timestamp,
                )
        except Exception:
            pass
    processor = platform.processor().strip()[:160]
    if processor:
        return Observation(
            "observed", {"name": processor, "logical_processors": os.cpu_count()},
            None, "Python platform.processor and os.cpu_count", timestamp,
        )
    return _unknown(timestamp, "CPU model details are unavailable on this platform.")


def _observe_gpu(timestamp: str) -> Observation:
    service = _wmi_service()
    if service is None:
        return _unknown(timestamp, "GPU inventory is unsupported or unavailable on this platform.")
    try:
        adapters = []
        for item in service.ExecQuery("SELECT Name, AdapterRAM FROM Win32_VideoController"):
            name = str(item.Name or "").strip()[:160]
            if not name or name.casefold().startswith(("microsoft basic", "microsoft remote")):
                continue
            # Win32_VideoController.AdapterRAM is an unsigned 32-bit value and
            # can be truncated or sign-wrapped, so it is deliberately not used.
            adapters.append({"name": name, "dedicated_memory_bytes": None})
        return Observation(
            "observed", adapters, None, "Windows WMI Win32_VideoController", timestamp,
        )
    except Exception:
        return _unknown(timestamp, "Windows GPU inventory could not be read.")


def _observe_memory(timestamp: str) -> Observation:
    if os.name == "nt":
        try:
            status = _MemoryStatusEx()
            status.dwLength = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                if status.ullTotalPhys > 0:
                    return Observation(
                        "observed",
                        {"total_bytes": int(status.ullTotalPhys),
                         "available_bytes": int(status.ullAvailPhys)},
                        "bytes", "Windows GlobalMemoryStatusEx", timestamp,
                    )
        except (AttributeError, OSError, TypeError):
            pass
        return _unknown(timestamp, "Windows memory totals could not be read.")
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        total_pages = os.sysconf("SC_PHYS_PAGES")
        available_pages = os.sysconf("SC_AVPHYS_PAGES")
        if page_size > 0 and total_pages > 0:
            return Observation(
                "observed",
                {"total_bytes": page_size * total_pages,
                 "available_bytes": page_size * available_pages},
                "bytes", "POSIX sysconf memory counters", timestamp,
            )
    except (AttributeError, OSError, ValueError):
        pass
    return _unknown(timestamp, "Physical memory totals are unsupported on this platform.")


def _observe_disk(timestamp: str) -> Observation:
    custom = os.environ.get("OLLAMA_MODELS")
    if custom:
        root = Path(custom).expanduser()
        source = "Available disk space at configured Ollama model destination"
    else:
        root = Path(os.environ.get("USERPROFILE") or Path.home()) / ".ollama" / "models"
        source = "Available disk space at the default per-user Ollama model destination"
    candidate = root
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    try:
        usage = shutil.disk_usage(candidate)
        return Observation(
            "observed",
            {"free_bytes": int(usage.free), "total_bytes": int(usage.total),
             "destination": "custom" if custom else "default"},
            "bytes", source, timestamp,
        )
    except (OSError, RuntimeError, ValueError):
        return _unknown(timestamp, "Disk capacity at the Ollama model destination is unavailable.")


def _recommend(memory: Observation, gpu: Observation, disk: Observation) -> dict[str, str]:
    warning = ""
    if gpu.state != "observed":
        warning = "GPU status is unknown; Ollama may use CPU, which can make replies slower."
    elif not gpu.value:
        warning = "No hardware GPU adapter was reported; expect Ollama to use CPU, which can make replies slower."
    else:
        warning = "A GPU adapter is detected, but Ollama accelerator use and usable VRAM are not verified."

    available = None
    if memory.state == "observed" and isinstance(memory.value, dict):
        available = memory.value.get("available_bytes")
    free_disk = None
    if disk.state == "observed" and isinstance(disk.value, dict):
        free_disk = disk.value.get("free_bytes")

    if not isinstance(available, int) or available <= 0:
        model_class = "UNKNOWN"
        basis = "Available system memory was not measured; no model-size suggestion can be made."
    elif available < 4 * 1024**3:
        model_class = "small (up to about 3B parameters, Q4)"
        basis = "Current available system memory is below 4 GiB; the suggestion is intentionally conservative."
    elif available < 12 * 1024**3:
        model_class = "small-to-medium (about 3B parameters, Q4)"
        basis = "Current available system memory is 4-12 GiB; the suggestion assumes a quantized text model."
    else:
        model_class = "medium (about 7B-8B parameters, Q4)"
        basis = "Current available system memory is at least 12 GiB; larger models require verified usable VRAM and model-specific evidence."

    if isinstance(free_disk, int) and free_disk < 8 * 1024**3:
        basis += " Disk space at the Ollama destination is below 8 GiB; check the exact model estimate before any separate download."
    return {
        "ollama_model_class": model_class,
        "cpu_warning": warning,
        "basis": basis,
        "fit_claim": "This heuristic does not guarantee model fit, speed, compatibility, or successful inference.",
    }
