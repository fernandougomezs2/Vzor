"""Structured host metadata and native peak-working-set measurement."""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def utc_timestamp() -> str:
    """Return an ISO-8601 timestamp for benchmark artifacts only."""

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _windows_memory() -> tuple[int | None, int | None]:
    class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    counters = PROCESS_MEMORY_COUNTERS_EX()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_current_process = kernel32.GetCurrentProcess
    get_current_process.argtypes = []
    get_current_process.restype = ctypes.c_void_p
    get_process_memory_info = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
    get_process_memory_info.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX),
        ctypes.c_ulong,
    ]
    get_process_memory_info.restype = ctypes.c_int
    success = get_process_memory_info(get_current_process(), ctypes.byref(counters), counters.cb)
    if not success:
        return None, None
    return int(counters.PeakWorkingSetSize), int(counters.WorkingSetSize)


def process_memory() -> dict[str, int | str | None]:
    """Return the process peak memory metric without an extra dependency.

    Windows reports the OS-maintained process *Peak Working Set* in bytes.
    POSIX reports ``ru_maxrss`` (Linux: KiB, macOS: bytes).  It is a cumulative
    process metric, so an isolated child is required for comparable runs.
    """

    if os.name == "nt":
        peak, current = _windows_memory()
        return {
            "memory_metric": "peak_working_set_bytes",
            "peak_memory_bytes": peak,
            "current_working_set_bytes": current,
        }
    try:
        import resource

        maximum = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_bytes = int(maximum if sys.platform == "darwin" else maximum * 1024)
    except (ImportError, OSError):
        peak_bytes = None
    return {
        "memory_metric": "peak_rss_bytes",
        "peak_memory_bytes": peak_bytes,
        "current_working_set_bytes": None,
    }


def memory_status() -> tuple[int | None, int | None]:
    """Return total and currently available physical memory for benchmark policy."""
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
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

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.WinDLL("kernel32").GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.ullTotalPhys), int(status.ullAvailPhys)
        return None, None
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        page_count = os.sysconf("SC_PHYS_PAGES")
        return int(page_size * page_count), None
    except (AttributeError, OSError, ValueError):
        return None, None


def _cpu_model() -> str | None:
    if platform.system() == "Windows":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            return None
    return platform.processor() or None


def system_metadata(
    *,
    dataset_path: Path,
    rows: int,
    columns: int,
    operation: str,
    profile: str | None,
    seed: int | None,
) -> dict[str, Any]:
    """Collect stable machine context plus run-specific benchmark fields."""

    import vzor

    dataset_size = dataset_path.stat().st_size
    total_ram, available_ram = memory_status()
    resolved_dataset = Path(dataset_path).resolve()
    dataset_drive = resolved_dataset.drive or None
    try:
        disk_usage = shutil.disk_usage(resolved_dataset.anchor or resolved_dataset.parent)
    except OSError:
        disk_usage = None
    return {
        "timestamp": utc_timestamp(),
        "vzor_version": vzor.__version__,
        "backend": "pandas",
        "python_version": platform.python_version(),
        "pandas_version": pd.__version__,
        "os": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "cpu": _cpu_model(),
        "logical_cpu_count": os.cpu_count(),
        "total_ram_bytes": total_ram,
        "total_ram_gb": round(total_ram / 1024**3, 3) if total_ram is not None else None,
        "available_ram_bytes": available_ram,
        "available_ram_gb": round(available_ram / 1024**3, 3) if available_ram is not None else None,
        "operation": operation,
        "profile": profile,
        "seed": seed,
        "rows": rows,
        "columns": columns,
        "dataset_path": str(dataset_path),
        "dataset_name": dataset_path.name,
        "dataset_file_size_bytes": dataset_size,
        "dataset_file_size_mb": round(dataset_size / 1024**2, 3),
        "dataset_drive": dataset_drive,
        "dataset_disk_total_bytes": disk_usage.total if disk_usage else None,
        "dataset_disk_free_bytes": disk_usage.free if disk_usage else None,
    }
