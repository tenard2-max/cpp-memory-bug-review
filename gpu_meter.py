"""로컬 GPU 전용/공유 메모리·온도·사용률 스냅샷."""

from __future__ import annotations

import ctypes
import json
import shutil
import subprocess
import time
from ctypes import POINTER, byref, c_int, c_void_p
from dataclasses import dataclass
from pathlib import Path

import psutil

_NVIDIA_CANDIDATES = (
    r"C:\Windows\System32\nvidia-smi.exe",
    r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
)
_CACHE: list["GpuSnapshot"] | None = None
_CACHE_AT = 0.0
_CACHE_TTL = 1.8
_ADL = None
_ADL_CTX = None
_ADL_FAIL = False


@dataclass
class GpuSnapshot:
    index: int
    name: str
    temperature_c: float | None = None
    memory_used_mb: float | None = None
    memory_total_mb: float | None = None
    shared_used_mb: float | None = None
    shared_total_mb: float | None = None
    fan_rpm: float | None = None
    utilization_pct: float | None = None


def _parse_num(raw: object) -> float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.upper() in {"N/A", "[N/A]", "NA"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _nvidia_exe() -> str:
    found = shutil.which("nvidia-smi")
    if found:
        return found
    for candidate in _NVIDIA_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    return ""


def _nvidia_gpus() -> list[GpuSnapshot]:
    exe = _nvidia_exe()
    if not exe:
        return []
    try:
        completed = subprocess.run(
            [
                exe,
                "--query-gpu=index,name,temperature.gpu,memory.used,memory.total,fan.speed,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0:
        return []
    shared_total_mb = psutil.virtual_memory().total / (1024 * 1024) / 2.0
    gpus: list[GpuSnapshot] = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 7:
            continue
        index = int(_parse_num(parts[0]) or len(gpus))
        gpus.append(
            GpuSnapshot(
                index=index,
                name=parts[1] or f"GPU_{index}",
                temperature_c=_parse_num(parts[2]),
                memory_used_mb=_parse_num(parts[3]),
                memory_total_mb=_parse_num(parts[4]),
                shared_used_mb=None,
                shared_total_mb=shared_total_mb,
                fan_rpm=_parse_num(parts[5]),
                utilization_pct=_parse_num(parts[6]),
            )
        )
    return gpus


@ctypes.WINFUNCTYPE(c_void_p, c_int)
def _adl_alloc(size: int):
    return ctypes.cast((ctypes.c_byte * size)(), c_void_p).value or 0


def _amd_temperature_c() -> float | None:
    """AMD ADL OverdriveN 온도(°C). 실패하면 None."""
    global _ADL, _ADL_CTX, _ADL_FAIL
    if _ADL_FAIL:
        return None
    try:
        if _ADL is None:
            dll_path = Path(r"C:\Windows\System32\atiadlxx.dll")
            if not dll_path.is_file():
                dll_path = Path(r"C:\Windows\System32\atiadlxy.dll")
            if not dll_path.is_file():
                _ADL_FAIL = True
                return None
            _ADL = ctypes.WinDLL(str(dll_path))
            _ADL.ADL2_Main_Control_Create.argtypes = [ctypes.c_void_p, c_int, POINTER(c_void_p)]
            _ADL.ADL2_Main_Control_Create.restype = c_int
            _ADL.ADL2_OverdriveN_Temperature_Get.argtypes = [c_void_p, c_int, c_int, POINTER(c_int)]
            _ADL.ADL2_OverdriveN_Temperature_Get.restype = c_int
            ctx = c_void_p()
            if _ADL.ADL2_Main_Control_Create(_adl_alloc, 1, byref(ctx)) != 0:
                _ADL_FAIL = True
                return None
            _ADL_CTX = ctx
        assert _ADL is not None and _ADL_CTX is not None
        for adapter in range(0, 8):
            raw = c_int()
            # iThermalControllerIndex 1 = edge 온도인 경우가 많다.
            if _ADL.ADL2_OverdriveN_Temperature_Get(_ADL_CTX, adapter, 1, byref(raw)) == 0 and raw.value > 0:
                return raw.value / 1000.0
    except Exception:
        _ADL_FAIL = True
        return None
    return None


def _as_list(value: object) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _windows_gpus() -> list[GpuSnapshot]:
    """작업 관리자와 같은 Windows GPU 카운터 + AMD 온도를 읽는다."""
    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$video = @(Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM)
$mem = @(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory |
    Select-Object Name, DedicatedUsage, SharedUsage)
$eng = @(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine |
    Select-Object Name, UtilizationPercentage)
@{ video = $video; mem = $mem; eng = $eng } | ConvertTo-Json -Compress -Depth 6
"""
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []

    videos = []
    for item in _as_list(payload.get("video")):
        name = str(item.get("Name") or "").strip()
        if not name:
            continue
        lower = name.lower()
        if "microsoft" in lower and "basic" in lower:
            continue
        total = _parse_num(item.get("AdapterRAM"))
        videos.append(
            {
                "name": name,
                "total_mb": (total / (1024 * 1024)) if total and total > 0 else None,
            }
        )
    if not videos:
        return []

    mem_rows = []
    for item in _as_list(payload.get("mem")):
        dedicated = _parse_num(item.get("DedicatedUsage")) or 0.0
        shared = _parse_num(item.get("SharedUsage")) or 0.0
        mem_rows.append(
            {
                "name": str(item.get("Name") or ""),
                "dedicated_mb": dedicated / (1024 * 1024),
                "shared_mb": shared / (1024 * 1024),
                "score": dedicated + shared,
            }
        )
    mem_rows.sort(key=lambda row: row["score"], reverse=True)

    def luid_key(text: str) -> str:
        lower = text.lower()
        if "_luid_" in lower:
            after = lower.split("_luid_", 1)[1]
        elif lower.startswith("luid_"):
            after = lower[len("luid_") :]
        else:
            return lower
        parts = after.split("_")
        if len(parts) >= 2:
            return f"luid_{parts[0]}_{parts[1]}"
        return lower

    util_by_luid: dict[str, float] = {}
    for item in _as_list(payload.get("eng")):
        key = luid_key(str(item.get("Name") or ""))
        util_by_luid[key] = util_by_luid.get(key, 0.0) + (_parse_num(item.get("UtilizationPercentage")) or 0.0)

    shared_total_mb = psutil.virtual_memory().total / (1024 * 1024) / 2.0
    temperature = _amd_temperature_c()
    # 실제 사용 중인 어댑터만 고른다. 비어 있는 가상 어댑터는 건너뛴다.
    active_mem = [row for row in mem_rows if row["score"] > 1.0] or mem_rows[:1]
    primary = videos[0]
    mem = active_mem[0] if active_mem else None
    util = None
    if mem:
        util_raw = util_by_luid.get(luid_key(mem["name"]))
        util = None if util_raw is None else min(100.0, util_raw)
    return [
        GpuSnapshot(
            index=0,
            name=primary["name"],
            temperature_c=temperature,
            memory_used_mb=mem["dedicated_mb"] if mem else None,
            memory_total_mb=primary["total_mb"],
            shared_used_mb=mem["shared_mb"] if mem else None,
            shared_total_mb=shared_total_mb,
            fan_rpm=None,
            utilization_pct=util,
        )
    ]


def sample_gpus() -> list[GpuSnapshot]:
    """짧은 TTL 캐시로 GPU 스냅샷을 돌려준다."""
    global _CACHE, _CACHE_AT
    now = time.monotonic()
    if _CACHE is not None and now - _CACHE_AT < _CACHE_TTL:
        return list(_CACHE)
    gpus = _nvidia_gpus() or _windows_gpus()
    _CACHE = gpus
    _CACHE_AT = now
    return list(gpus)
