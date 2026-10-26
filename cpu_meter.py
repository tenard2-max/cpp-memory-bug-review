"""이 PC와 Ollama 프로세스의 CPU 사용률."""

from __future__ import annotations

import psutil

_OLLAMA: dict[int, psutil.Process] = {}
_PRIMED = False


def sample_cpu() -> tuple[float, float | None]:
    """시스템 사용률과 Ollama가 코어 전체에서 차지하는 비율. 둘 다 0에서 100이다."""
    global _PRIMED
    if not _PRIMED:
        psutil.cpu_percent(interval=None)
        _PRIMED = True
        system = 0.0
    else:
        system = float(psutil.cpu_percent(interval=None))
    return system, _ollama_cpu()


def _ollama_cpu() -> float | None:
    found = False
    total = 0.0
    seen: set[int] = set()
    for proc in psutil.process_iter(["name"]):
        name = (proc.info.get("name") or "").lower()
        if "ollama" not in name:
            continue
        seen.add(proc.pid)
        cached = _OLLAMA.get(proc.pid)
        if cached is None:
            try:
                proc.cpu_percent(interval=None)
            except psutil.Error:
                continue
            _OLLAMA[proc.pid] = proc
            found = True
            continue
        try:
            total += cached.cpu_percent(interval=None)
            found = True
        except psutil.Error:
            _OLLAMA.pop(proc.pid, None)
    for pid in list(_OLLAMA):
        if pid not in seen:
            _OLLAMA.pop(pid, None)
    if not found:
        return None
    cores = psutil.cpu_count() or 1
    return max(0.0, min(100.0, total / cores))


def cpu_label() -> str:
    system, ollama = sample_cpu()
    if ollama is None:
        return f"시스템 CPU {system:.0f}% · Ollama CPU 없음"
    return f"시스템 CPU {system:.0f}% · Ollama CPU {ollama:.0f}%"
