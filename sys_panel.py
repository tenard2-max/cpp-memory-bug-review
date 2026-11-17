"""코드 검토 안내 칸용 로컬 하드웨어·런타임 스냅샷."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Sequence

import psutil

from cpu_meter import sample_cpu
from gpu_meter import GpuSnapshot, sample_gpus


@dataclass
class HostSnapshot:
    system_cpu: float
    ollama_cpu: float | None
    ram_percent: float
    ram_used_mb: float
    ram_total_mb: float
    gpus: list[GpuSnapshot]
    warnings: list[str]


def sample_host(extra_warnings: Sequence[str] | None = None) -> HostSnapshot:
    """CPU·RAM·GPU 상태를 한 번에 읽는다."""
    system_cpu, ollama_cpu = sample_cpu()
    memory = psutil.virtual_memory()
    gpus = sample_gpus()
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


def _bar(
    label: str,
    value_text: str,
    ratio: float | None,
    color: str,
    *,
    emphasize: bool = False,
    shared: bool = False,
) -> str:
    width = 0 if ratio is None else max(0, min(100, ratio * 100))
    if shared:
        css_class = "cmd-metric cmd-metric-shared"
    elif emphasize:
        css_class = "cmd-metric cmd-metric-emphasis"
    else:
        css_class = "cmd-metric"
    return (
        f'<div class="{css_class}">'
        f'<div class="cmd-metric-row"><span class="cmd-metric-label">{html.escape(label)}</span>'
        f'<span class="cmd-metric-value">{html.escape(value_text)}</span></div>'
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


def _shared_memory_bar(gpu: GpuSnapshot | None, host: HostSnapshot) -> str:
    """옵션에서 공유 메모리를 켰을 때 VRAM 아래에 붙는 행(GPU 공유 메모리)."""
    if gpu and gpu.shared_used_mb is not None and gpu.shared_total_mb:
        used_gb = gpu.shared_used_mb / 1024.0
        total_gb = gpu.shared_total_mb / 1024.0
        ratio = gpu.shared_used_mb / gpu.shared_total_mb if gpu.shared_total_mb else None
        text = f"{used_gb:.1f}/{total_gb:.1f} GB ({(ratio or 0) * 100:.0f}%)"
        return _bar("공유 메모리", text, ratio, "#7ec8e3", shared=True)
    # GPU 공유값을 못 읽으면 시스템 RAM 대비로라도 표시
    return _bar(
        "공유 메모리",
        f"{host.ram_used_mb / 1024:.1f}/{host.ram_total_mb / 1024:.1f} GB ({host.ram_percent:.0f}%) · host fallback",
        host.ram_percent / 100.0,
        "#7ec8e3",
        shared=True,
    )


def _gpu_body(gpu: GpuSnapshot, *, vram_label: str, shared_memory: bool, host: HostSnapshot) -> str:
    temp_ratio = None if gpu.temperature_c is None else min(gpu.temperature_c / 95.0, 1.0)
    temp_text = "N/A" if gpu.temperature_c is None else f"{gpu.temperature_c:.0f} °C"

    if gpu.memory_used_mb is not None and gpu.memory_total_mb:
        mem_ratio = gpu.memory_used_mb / gpu.memory_total_mb
        mem_text = f"{gpu.memory_used_mb:.0f}/{gpu.memory_total_mb:.0f} MB"
    elif gpu.memory_used_mb is not None:
        mem_ratio = None
        mem_text = f"{gpu.memory_used_mb:.0f} MB used"
    elif gpu.memory_total_mb:
        mem_ratio = None
        mem_text = f"total {gpu.memory_total_mb:.0f} MB"
    else:
        mem_ratio = None
        mem_text = f"profile {vram_label}"

    if gpu.fan_rpm is not None:
        third_ratio = min(gpu.fan_rpm / 5000.0, 1.0)
        third_text = f"{gpu.fan_rpm:.0f} RPM"
        third_label = "팬"
    elif gpu.utilization_pct is not None:
        third_ratio = gpu.utilization_pct / 100.0
        third_text = f"{gpu.utilization_pct:.0f}%"
        third_label = "사용률"
    else:
        third_ratio = None
        third_text = "N/A"
        third_label = "사용률"

    shared_row = _shared_memory_bar(gpu, host) if shared_memory else ""
    return (
        _bar("온도", temp_text, temp_ratio, "#b83b3b")
        + _bar("VRAM / 전용", mem_text, mem_ratio, "#e0872f", emphasize=True)
        + shared_row
        + _bar(third_label, third_text, third_ratio, "#6f9b5a")
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
    shared_memory: bool = False,
    extra_warnings: Sequence[str] | None = None,
) -> tuple[str, HostSnapshot]:
    """안내 칸 HTML과 방금 읽은 스냅샷을 반환한다."""
    host = host or sample_host(extra_warnings)
    model = (model_name or "unknown").strip() or "unknown"
    pipeline = "LOCAL_OLLAMA_ONLINE" if online else "LOCAL_OLLAMA_OFFLINE"
    deploy = "LOCAL_ONLY · NO_UPLOAD"
    shared_meta = "ON" if shared_memory else "OFF"

    gpu_cards: list[str] = []
    for gpu in host.gpus[:2]:
        body = _gpu_body(gpu, vram_label=vram_label, shared_memory=shared_memory, host=host)
        gpu_cards.append(_device_card(f"GPU_{gpu.index}  {gpu.name}", body))

    if not gpu_cards:
        shared_row = _shared_memory_bar(None, host) if shared_memory else ""
        body = (
            _bar("온도", "N/A", None, "#b83b3b")
            + _bar("VRAM / 전용", vram_label, None, "#e0872f", emphasize=True)
            + shared_row
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
    primary = host.gpus[0] if host.gpus else None
    temp_note = (
        f"{primary.temperature_c:.0f}°C"
        if primary and primary.temperature_c is not None
        else "temp N/A"
    )

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
        f'<div class="cmd-chart-foot">{latest_cpu:.0f}% · model {html.escape(model)} · GPU {temp_note}</div>'
        "</div>"
    )

    markup = f"""
<div class="cmd-panel">
  <div class="cmd-head">
    <div class="cmd-title">[SYS_INIT] :: CPP_MEMORY_BUG_REVIEW</div>
    <div class="cmd-sub">TARGET: {html.escape(pipeline)}</div>
    <div class="cmd-meta">MODEL: {html.escape(model)} &nbsp;|&nbsp; DEPLOYMENT: {html.escape(deploy)} &nbsp;|&nbsp; VRAM_PROFILE: {html.escape(vram_label)} &nbsp;|&nbsp; SHARED_MEM: {shared_meta}</div>
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
