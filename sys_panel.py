"""코드 검토 안내 칸용 로컬 하드웨어·런타임 스냅샷."""

from __future__ import annotations

import csv
import html
import shutil
import subprocess
import time
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Sequence

import psutil

from cpu_meter import sample_cpu

_NVIDIA_CANDIDATES = (
    r"C:\Windows\System32\nvidia-smi.exe",
    r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe",
)


@dataclass
class GpuSnapshot:
    index: int
    name: str
    temperature_c: float | None = None
    memory_used_mb: float | None = None
    memory_total_mb: float | None = None
    fan_rpm: float | None = None
    utilization_pct: float | None = None


_WMI_GPU_CACHE: list[GpuSnapshot] | None = None
_WMI_GPU_CACHE_AT = 0.0


@dataclass
class HostSnapshot:
    system_cpu: float
    ollama_cpu: float | None
    ram_percent: float
    ram_used_mb: float
    ram_total_mb: float
    gpus: list[GpuSnapshot]
    warnings: list[str]


def _parse_num(raw: str) -> float | None:
    text = (raw or "").strip()
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
                fan_rpm=_parse_num(parts[5]),
                utilization_pct=_parse_num(parts[6]),
            )
        )
    return gpus


def _wmi_gpus() -> list[GpuSnapshot]:
    global _WMI_GPU_CACHE, _WMI_GPU_CACHE_AT
    now = time.monotonic()
    if _WMI_GPU_CACHE is not None and now - _WMI_GPU_CACHE_AT < 30:
        return list(_WMI_GPU_CACHE)
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_VideoController | "
                "Select-Object Name, AdapterRAM | ConvertTo-Csv -NoTypeInformation",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return list(_WMI_GPU_CACHE or [])
    if completed.returncode != 0:
        return list(_WMI_GPU_CACHE or [])
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        return list(_WMI_GPU_CACHE or [])
    gpus: list[GpuSnapshot] = []
    for line in lines[1:]:
        parts = next(csv.reader(StringIO(line)), None)
        if not parts:
            continue
        name = (parts[0] or "").strip()
        if not name:
            continue
        lower = name.lower()
        if "microsoft" in lower and "basic" in lower:
            continue
        total_mb = None
        if len(parts) > 1:
            raw_ram = _parse_num(parts[1])
            if raw_ram and raw_ram > 0:
                total_mb = raw_ram / (1024 * 1024)
        gpus.append(GpuSnapshot(index=len(gpus), name=name, memory_total_mb=total_mb))
    _WMI_GPU_CACHE = gpus
    _WMI_GPU_CACHE_AT = now
    return list(gpus)


def sample_host(extra_warnings: Sequence[str] | None = None) -> HostSnapshot:
    """CPU·RAM·GPU 상태를 한 번에 읽는다."""
    system_cpu, ollama_cpu = sample_cpu()
    memory = psutil.virtual_memory()
    gpus = _nvidia_gpus() or _wmi_gpus()
    warnings = list(extra_warnings or [])
    if not gpus:
        warnings.append("GPU_ENUM: 표시할 그래픽 장치를 찾지 못했습니다.")
    if memory.percent >= 90:
        warnings.append(f"RAM_PRESSURE: 시스템 메모리 {memory.percent:.0f}%")
    return HostSnapshot(
        system_cpu=system_cpu,
        ollama_cpu=ollama_cpu,
        ram_percent=float(memory.percent),
        ram_used_mb=memory.used / (1024 * 1024),
        ram_total_mb=memory.total / (1024 * 1024),
        gpus=gpus,
        warnings=warnings,
    )


def _bar(label: str, value_text: str, ratio: float | None, color: str) -> str:
    width = 0 if ratio is None else max(0, min(100, ratio * 100))
    return (
        f'<div class="cmd-metric">'
        f'<div class="cmd-metric-row"><span>{html.escape(label)}</span>'
        f"<span>{html.escape(value_text)}</span></div>"
        f'<div class="cmd-track"><div class="cmd-fill" style="width:{width:.1f}%;background:{color};"></div></div>'
        f"</div>"
    )


def _sparkline(values: Sequence[float], stroke: str, fill: str) -> str:
    points = list(values[-40:] if values else [0.0])
    width, height = 220, 54
    lo = min(points)
    hi = max(points)
    span = hi - lo if hi > lo else 1.0
    coords: list[str] = []
    for index, value in enumerate(points):
        x = 0 if len(points) == 1 else index * (width / (len(points) - 1))
        y = height - ((value - lo) / span) * (height - 4) - 2
        coords.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(coords)
    area = f"0,{height} " + polyline + f" {width},{height}"
    return (
        f'<svg class="cmd-spark" viewBox="0 0 {width} {height}" preserveAspectRatio="none">'
        f'<polygon points="{area}" fill="{fill}"></polygon>'
        f'<polyline points="{polyline}" fill="none" stroke="{stroke}" stroke-width="1.6"></polyline>'
        f"</svg>"
    )


def _device_card(title: str, body_html: str) -> str:
    return (
        f'<div class="cmd-card">'
        f'<div class="cmd-card-title">{html.escape(title)}</div>'
        f"{body_html}"
        f"</div>"
    )


def render_command_panel(
    *,
    model_name: str,
    online: bool,
    cppcheck_ok: bool,
    vram_label: str,
    ram_label: str,
    mem_history: Sequence[float],
    cpu_history: Sequence[float],
    host: HostSnapshot | None = None,
    extra_warnings: Sequence[str] | None = None,
) -> tuple[str, HostSnapshot]:
    """안내 칸 HTML과 방금 읽은 스냅샷을 반환한다."""
    host = host or sample_host(extra_warnings)
    model = (model_name or "unknown").strip() or "unknown"
    pipeline = "LOCAL_OLLAMA_ONLINE" if online else "LOCAL_OLLAMA_OFFLINE"
    deploy = "LOCAL_ONLY · NO_UPLOAD"

    gpu_cards: list[str] = []
    for gpu in host.gpus[:2]:
        temp_ratio = None if gpu.temperature_c is None else min(gpu.temperature_c / 95.0, 1.0)
        temp_text = "N/A" if gpu.temperature_c is None else f"{gpu.temperature_c:.0f} °C"
        if gpu.memory_used_mb is not None and gpu.memory_total_mb:
            mem_ratio = gpu.memory_used_mb / gpu.memory_total_mb
            mem_text = f"{gpu.memory_used_mb:.0f}/{gpu.memory_total_mb:.0f} MB"
        elif gpu.memory_total_mb:
            mem_ratio = None
            mem_text = f"reported {gpu.memory_total_mb:.0f} MB"
        else:
            mem_ratio = None
            mem_text = f"profile {vram_label}"
        if gpu.fan_rpm is not None:
            fan_ratio = min(gpu.fan_rpm / 5000.0, 1.0)
            fan_text = f"{gpu.fan_rpm:.0f} RPM"
        elif gpu.utilization_pct is not None:
            fan_ratio = gpu.utilization_pct / 100.0
            fan_text = f"util {gpu.utilization_pct:.0f}%"
        else:
            fan_ratio = None
            fan_text = "N/A"
        body = (
            _bar("온도", temp_text, temp_ratio, "#b83b3b")
            + _bar("VRAM/표시", mem_text, mem_ratio, "#e0872f")
            + _bar("팬/사용률", fan_text, fan_ratio, "#6f9b5a")
        )
        gpu_cards.append(_device_card(f"GPU_{gpu.index}  {gpu.name}", body))

    if not gpu_cards:
        body = (
            _bar("온도", "N/A", None, "#b83b3b")
            + _bar("VRAM 프로필", vram_label, None, "#e0872f")
            + _bar("사용률", "N/A", None, "#6f9b5a")
        )
        gpu_cards.append(_device_card("GPU_0  (미검출)", body))

    ollama_text = "없음" if host.ollama_cpu is None else f"{host.ollama_cpu:.0f}%"
    host_body = (
        _bar("시스템 CPU", f"{host.system_cpu:.0f}%", host.system_cpu / 100.0, "#b83b3b")
        + _bar(
            "시스템 RAM",
            f"{host.ram_used_mb / 1024:.1f}/{host.ram_total_mb / 1024:.1f} GB ({host.ram_percent:.0f}%)",
            host.ram_percent / 100.0,
            "#e0872f",
        )
        + _bar(
            "Ollama CPU",
            ollama_text,
            None if host.ollama_cpu is None else host.ollama_cpu / 100.0,
            "#6f9b5a",
        )
    )
    if len(gpu_cards) == 1:
        gpu_cards.append(_device_card(f"HOST_SYS  RAM {ram_label}", host_body))

    warn_lines = list(host.warnings)
    if not online:
        warn_lines.append("WARNING: Ollama 미연결 · START.bat 확인")
    if not cppcheck_ok:
        warn_lines.append("WARNING: cppcheck 없음 · 메모리 호출 함수만 검토")
    if not warn_lines:
        warn_lines.append("LOG: sensors nominal")

    status_color = "#6f9b5a" if online else "#d64545"
    status_text = "STABLE" if online else "DEGRADED"
    latest_cpu = cpu_history[-1] if cpu_history else host.system_cpu

    left = "".join(gpu_cards[:2])
    mem_spark = _sparkline(mem_history or [host.ram_percent], "#7ec8e3", "rgba(126,200,227,0.22)")
    cpu_spark = _sparkline(cpu_history or [host.system_cpu], "#d64545", "rgba(214,69,69,0.18)")
    right = (
        '<div class="cmd-chart">'
        '<div class="cmd-chart-title">CPU와 시스템 공유 메모리 (SHARED_RAM)</div>'
        f"{mem_spark}"
        f'<div class="cmd-chart-foot">{host.ram_percent:.0f}% · {host.ram_used_mb / 1024:.1f} GB</div>'
        "</div>"
        '<div class="cmd-chart">'
        '<div class="cmd-chart-title">런타임 부하 시계열 (CPU%)</div>'
        f"{cpu_spark}"
        f'<div class="cmd-chart-foot">{latest_cpu:.0f}% · model {html.escape(model)}</div>'
        "</div>"
    )

    markup = f"""
<div class="cmd-panel">
  <div class="cmd-head">
    <div class="cmd-title">[SYS_INIT] :: CPP_MEMORY_BUG_REVIEW</div>
    <div class="cmd-sub">TARGET: {html.escape(pipeline)}</div>
    <div class="cmd-meta">MODEL: {html.escape(model)} &nbsp;|&nbsp; DEPLOYMENT: {html.escape(deploy)} &nbsp;|&nbsp; VRAM_PROFILE: {html.escape(vram_label)}</div>
  </div>
  <div class="cmd-grid">
    <div class="cmd-left">{left}</div>
    <div class="cmd-right">{right}</div>
  </div>
  <div class="cmd-foot">
    <div class="cmd-task">TASK: CPP_MEMORY_INIT_REVIEW [LOCAL] <span style="color:{status_color}">{status_text}</span></div>
    <div class="cmd-log">{"<br/>".join(html.escape(line) for line in warn_lines[:3])}</div>
    <div class="cmd-alert">[{html.escape(warn_lines[0])}]</div>
  </div>
</div>
"""
    return markup, host
