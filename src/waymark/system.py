"""Local system profiling for respectful first-run setup."""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar


@dataclass(frozen=True)
class CapabilityRecommendation:
    mode: str
    chat_model: str | None
    embedding_model: str | None
    reason: str


@dataclass(frozen=True)
class SystemProfile:
    os_name: str
    os_version: str
    machine: str
    processor: str
    cpu_count: int | None
    total_ram_gb: float | None
    disk_free_gb: float
    recommendation: CapabilityRecommendation


def recommend_capability(
    *,
    total_ram_gb: float | None,
    disk_free_gb: float,
    cpu_count: int | None,
) -> CapabilityRecommendation:
    if disk_free_gb < 5:
        return CapabilityRecommendation(
            mode="app-only",
            chat_model=None,
            embedding_model=None,
            reason="Less than 5 GB of free disk is available.",
        )

    if total_ram_gb is None:
        return CapabilityRecommendation(
            mode="lite",
            chat_model=None,
            embedding_model="nomic-embed-text",
            reason="RAM could not be detected, so Waymark should start conservatively.",
        )

    if total_ram_gb < 8:
        return CapabilityRecommendation(
            mode="app-only",
            chat_model=None,
            embedding_model=None,
            reason="Less than 8 GB RAM is available.",
        )

    if total_ram_gb < 16:
        return CapabilityRecommendation(
            mode="lite",
            chat_model=None,
            embedding_model="nomic-embed-text",
            reason="8-16 GB RAM is best for manual capture plus light search.",
        )

    if total_ram_gb >= 32 and (cpu_count or 0) >= 8 and disk_free_gb >= 20:
        return CapabilityRecommendation(
            mode="pro",
            chat_model="qwen3:8b",
            embedding_model="mxbai-embed-large",
            reason="32 GB+ RAM and sufficient disk can support larger local models.",
        )

    return CapabilityRecommendation(
        mode="balanced",
        chat_model="qwen3:4b",
        embedding_model="nomic-embed-text",
        reason="16 GB+ RAM is a good fit for the default local AI setup.",
    )


def collect_system_profile(disk_path: Path) -> SystemProfile:
    disk_free_gb = free_disk_gb(disk_path)
    total_ram_gb = detect_total_ram_gb()
    cpu_count = os.cpu_count()
    recommendation = recommend_capability(
        total_ram_gb=total_ram_gb,
        disk_free_gb=disk_free_gb,
        cpu_count=cpu_count,
    )
    return SystemProfile(
        os_name=platform.system() or "unknown",
        os_version=platform.version() or "unknown",
        machine=platform.machine() or "unknown",
        processor=platform.processor() or "unknown",
        cpu_count=cpu_count,
        total_ram_gb=total_ram_gb,
        disk_free_gb=disk_free_gb,
        recommendation=recommendation,
    )


def free_disk_gb(path: Path) -> float:
    target = path.expanduser().resolve()
    while not target.exists() and target.parent != target:
        target = target.parent
    usage = shutil.disk_usage(target)
    return round(usage.free / (1024**3), 1)


def detect_total_ram_gb() -> float | None:
    if platform.system().lower() == "windows":
        return detect_windows_total_ram_gb()

    if hasattr(os, "sysconf"):
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
        except (OSError, ValueError):
            return None
        if isinstance(pages, int) and isinstance(page_size, int):
            return round((pages * page_size) / (1024**3), 1)

    return None


class MemoryStatusEx(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def detect_windows_total_ram_gb() -> float | None:
    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    windll: Any = getattr(ctypes, "windll", None)
    if windll is None:
        return None
    kernel32: Any = windll.kernel32
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    total_physical_bytes = int(status.ullTotalPhys)
    return round(total_physical_bytes / (1024**3), 1)
