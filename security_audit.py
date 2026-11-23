"""로컬 LLM+RAG 외부 유출 여부 보안 점검. 증빙용 리포트 생성."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
STREAMLIT_CONFIG = ROOT / ".streamlit" / "config.toml"
REPORT_DIR = ROOT / "data" / "security"
SCAN_GLOBS = ("*.py",)
SKIP_PARTS = {".git", ".venv", "venv", "__pycache__", "node_modules", "data", "docs", "DOC", "reports", "inbox"}

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
SUSPECT_TOKENS = (
    "openai",
    "anthropic",
    "googleapis",
    "api.deepseek",
    "huggingface.co",
    "hf.co",
    "openrouter",
    "groq.com",
)
URL_RE = re.compile(r"https?://[^\s'\"\)\]}>]+", re.IGNORECASE)
ENV_KEYS = (
    "ANONYMIZED_TELEMETRY",
    "HF_HUB_OFFLINE",
    "TRANSFORMERS_OFFLINE",
    "HF_DATASETS_OFFLINE",
    "OLLAMA_HOST",
)


def apply_local_security_env() -> dict[str, str]:
    """프로세스에 오프라인·텔레메트리 차단 환경변수를 강제한다."""
    defaults = {
        "ANONYMIZED_TELEMETRY": "False",
        "CHROMA_TELEMETRY": "False",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "OLLAMA_HOST": os.environ.get("OLLAMA_HOST") or "127.0.0.1:11434",
    }
    applied: dict[str, str] = {}
    for key, value in defaults.items():
        # 이미 사용자가 끈 경우를 덮어쓰지 않되, 기본은 차단 ON
        current = os.environ.get(key)
        if current is None or current == "":
            os.environ[key] = value
            applied[key] = value
        else:
            applied[key] = current
    return applied


def ensure_streamlit_config() -> dict[str, Any]:
    """Streamlit 사용 통계 수집을 끈다."""
    STREAMLIT_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    text = STREAMLIT_CONFIG.read_text(encoding="utf-8") if STREAMLIT_CONFIG.is_file() else ""
    lines = text.splitlines()
    changed = False

    def ensure_section(section: str, key: str, value: str) -> None:
        nonlocal lines, changed
        header = f"[{section}]"
        if header not in lines:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(header)
            lines.append(f"{key} = {value}")
            changed = True
            return
        idx = lines.index(header)
        end = idx + 1
        while end < len(lines) and not lines[end].startswith("["):
            end += 1
        block = lines[idx + 1 : end]
        found = False
        for offset, row in enumerate(block):
            if row.strip().startswith(f"{key}"):
                if row.strip() != f"{key} = {value}":
                    lines[idx + 1 + offset] = f"{key} = {value}"
                    changed = True
                found = True
                break
        if not found:
            lines.insert(end, f"{key} = {value}")
            changed = True

    ensure_section("server", "address", '"127.0.0.1"')
    ensure_section("server", "port", "8501")
    ensure_section("server", "headless", "true")
    ensure_section("browser", "gatherUsageStats", "false")
    if changed or not STREAMLIT_CONFIG.is_file():
        STREAMLIT_CONFIG.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {
        "path": str(STREAMLIT_CONFIG),
        "gatherUsageStats": False,
        "updated": changed,
    }


def _is_local_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    host = (parsed.hostname or "").lower()
    if host in LOCAL_HOSTS:
        return True
    # 사설망
    if host.startswith("10.") or host.startswith("192.168.") or host.startswith("172."):
        return True
    return False


def scan_python_sources() -> dict[str, Any]:
    """프로젝트 .py 에서 외부 URL·의심 토큰을 찾는다."""
    findings: list[dict[str, Any]] = []
    scanned = 0
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        for match in URL_RE.finditer(text):
            url = match.group(0).rstrip(".,);\"'")
            if _is_local_url(url):
                continue
            line = text.count("\n", 0, match.start()) + 1
            findings.append(
                {
                    "file": rel,
                    "line": line,
                    "kind": "external_url",
                    "value": url,
                    "severity": "medium" if "github.com" in url or "ollama.com" in url else "high",
                    "note": "하드코딩 외부 URL. 런타임 호출인지 주석/문서성인지 확인.",
                }
            )
        # 점검 모듈 자신의 키워드 목록은 오탐이므로 토큰 스캔에서 제외
        if path.name == "security_audit.py":
            continue
        lower = text.lower()
        for token in SUSPECT_TOKENS:
            start = 0
            while True:
                idx = lower.find(token, start)
                if idx < 0:
                    break
                line_no = text.count("\n", 0, idx) + 1
                line_text = text.splitlines()[line_no - 1] if text.splitlines() else ""
                # UI 안내 문장(검색 키워드 나열)은 info로 낮춤
                severity = "high" if token in {"openai", "anthropic", "googleapis"} else "medium"
                note = "외부 API/허브 관련 문자열."
                if "보안" in line_text or "스캔" in line_text or "gatherUsageStats" in line_text:
                    severity = "info"
                    note = "보안점검 안내 문구(실행 호출 아님)."
                findings.append(
                    {
                        "file": rel,
                        "line": line_no,
                        "kind": "suspect_token",
                        "value": token,
                        "severity": severity,
                        "note": note,
                    }
                )
                start = idx + len(token)
    # 중복 (file,line,value) 축소
    uniq = []
    seen = set()
    for item in findings:
        key = (item["file"], item["line"], item["kind"], item["value"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    return {"scanned_files": scanned, "findings": uniq}


def check_env() -> dict[str, Any]:
    rows = []
    ok = True
    expect = {
        "ANONYMIZED_TELEMETRY": {"False", "0", "false"},
        "HF_HUB_OFFLINE": {"1", "true", "True"},
        "TRANSFORMERS_OFFLINE": {"1", "true", "True"},
        "HF_DATASETS_OFFLINE": {"1", "true", "True"},
    }
    for key, good in expect.items():
        value = os.environ.get(key, "")
        passed = value in good
        if not passed:
            ok = False
        rows.append({"name": key, "value": value or "(미설정)", "ok": passed})
    host = os.environ.get("OLLAMA_HOST", "")
    host_ok = (not host) or host.startswith("127.0.0.1") or host.startswith("localhost")
    if not host_ok:
        ok = False
    rows.append({"name": "OLLAMA_HOST", "value": host or "(미설정=기본)", "ok": host_ok})
    return {"ok": ok, "rows": rows}


def check_streamlit_config() -> dict[str, Any]:
    ensure = ensure_streamlit_config()
    text = STREAMLIT_CONFIG.read_text(encoding="utf-8") if STREAMLIT_CONFIG.is_file() else ""
    stats_off = "gatherUsageStats" in text and "false" in text.lower()
    bind_local = 'address = "127.0.0.1"' in text or "address = '127.0.0.1'" in text
    return {
        "ok": stats_off and bind_local,
        "path": str(STREAMLIT_CONFIG),
        "gatherUsageStats_false": stats_off,
        "bind_127": bind_local,
        "updated": ensure.get("updated"),
    }


def check_ollama_endpoint(ollama_url: str) -> dict[str, Any]:
    url = (ollama_url or "").strip() or "http://127.0.0.1:11434"
    local = _is_local_url(url)
    reachable = False
    detail = ""
    try:
        from reviewer import ollama_reachable

        reachable = bool(ollama_reachable(url, timeout=2))
        detail = "응답 있음" if reachable else "응답 없음(실행 중이면 모델 로드 전일 수 있음)"
    except Exception as error:  # noqa: BLE001
        detail = str(error)
    return {"ok": local, "url": url, "local": local, "reachable": reachable, "detail": detail}


def _private_or_loopback(ip: str) -> bool:
    ip = ip.strip("[]")
    if ip in LOCAL_HOSTS:
        return True
    if ip.startswith("10.") or ip.startswith("192.168."):
        return True
    if ip.startswith("172."):
        try:
            second = int(ip.split(".")[1])
            if 16 <= second <= 31:
                return True
        except (IndexError, ValueError):
            pass
    return False


def check_outbound_netstat() -> dict[str, Any]:
    """python/ollama ESTABLISHED 연결 중 공인 IP가 있는지 본다."""
    try:
        completed = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        raw = completed.stdout or ""
    except OSError as error:
        return {"ok": False, "error": str(error), "rows": [], "suspects": []}

    # PID → 이미지
    pid_names: dict[str, str] = {}
    try:
        task = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="cp949",
            errors="replace",
            check=False,
        )
        for line in (task.stdout or "").splitlines():
            parts = [p.strip().strip('"') for p in line.split(",")]
            if len(parts) >= 2:
                pid_names[parts[1]] = parts[0].lower()
    except OSError:
        pass

    watch = {"python.exe", "pythonw.exe", "ollama.exe", "streamlit.exe"}
    rows = []
    suspects = []
    for line in raw.splitlines():
        if "ESTABLISHED" not in line.upper():
            continue
        cols = line.split()
        if len(cols) < 5:
            continue
        local, remote, state, pid = cols[1], cols[2], cols[3], cols[-1]
        name = pid_names.get(pid, "")
        if name and name not in watch:
            # PID 이름을 모를 때는 python/ollama 문자열 라인만
            if "python" not in line.lower() and "ollama" not in line.lower():
                continue
        elif not name:
            continue
        remote_ip = remote.rsplit(":", 1)[0].strip("[]")
        local_ok = _private_or_loopback(remote_ip)
        item = {
            "process": name or "?",
            "pid": pid,
            "local": local,
            "remote": remote,
            "state": state,
            "local_only": local_ok,
        }
        rows.append(item)
        if not local_ok:
            suspects.append(item)
    return {
        "ok": len(suspects) == 0,
        "rows": rows[:80],
        "suspects": suspects,
        "note": "인터넷 연결 상태에서 실행 중일 때의 스냅샷입니다. 오프라인 테스트와 함께 보세요.",
    }


def internet_reachable(timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection(("1.1.1.1", 53), timeout=timeout):
            return True
    except OSError:
        return False


def manual_checklist() -> list[dict[str, str]]:
    return [
        {
            "id": "offline",
            "title": "1. 네트워크 격리(비행기 모드/랜선 제거)",
            "detail": "모델·임베딩 캐시 준비 후 오프라인에서 Streamlit+RAG+LLM 분석이 에러 없이 끝나는지 확인.",
        },
        {
            "id": "netstat",
            "title": "2. netstat 아웃바운드 감시",
            "detail": "분석 중 `netstat -ano` 에서 python/ollama 가 127.0.0.1·사설망 외 공인 IP와 ESTABLISHED 인지 확인.",
        },
        {
            "id": "firewall",
            "title": "3. 방화벽 아웃바운드 차단(선택·원천 봉쇄)",
            "detail": "Windows 방화벽에서 python.exe·ollama.exe 아웃바운드 차단 후에도 분석이 되면 외부 경로는 막힌 것.",
        },
        {
            "id": "telemetry",
            "title": "4. 텔레메트리·HF 오프라인 플래그",
            "detail": "ANONYMIZED_TELEMETRY=False, HF_HUB_OFFLINE=1, Streamlit gatherUsageStats=false 적용.",
        },
        {
            "id": "ollama_bind",
            "title": "5. Ollama 바인딩",
            "detail": "OLLAMA_HOST=127.0.0.1:11434 (0.0.0.0 외부 개방 지양).",
        },
    ]


def run_security_audit(*, ollama_url: str = "http://127.0.0.1:11434") -> dict[str, Any]:
    """자동 점검 실행 후 JSON/텍스트 증빙을 저장한다."""
    applied = apply_local_security_env()
    streamlit_cfg = check_streamlit_config()
    env = check_env()
    source = scan_python_sources()
    ollama = check_ollama_endpoint(ollama_url)
    net = check_outbound_netstat()
    online = internet_reachable()

    high = [f for f in source["findings"] if f.get("severity") == "high"]
    auto_ok = (
        env["ok"]
        and streamlit_cfg["ok"]
        and ollama["local"]
        and net["ok"]
        and len(high) == 0
    )
    # info 등급은 자동 실패에 넣지 않는다.
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "auto_ok": auto_ok,
        "internet_now": online,
        "applied_env": applied,
        "env": env,
        "streamlit": streamlit_cfg,
        "ollama": ollama,
        "source_scan": source,
        "netstat": net,
        "manual_checklist": manual_checklist(),
        "summary": (
            "자동 항목 통과. 오프라인 실기동 체크리스트를 함께 증빙하세요."
            if auto_ok
            else "자동 항목 중 실패/주의가 있습니다. findings·suspects를 확인하세요."
        ),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = REPORT_DIR / f"security_audit_{stamp}.json"
    md_path = REPORT_DIR / f"security_audit_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_to_markdown(report), encoding="utf-8")
    report["json_path"] = str(json_path)
    report["md_path"] = str(md_path)
    return report


def _to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 로컬 LLM+RAG 보안 점검 리포트",
        "",
        f"- 시각: {report.get('generated_at')}",
        f"- 자동 판정: {'통과' if report.get('auto_ok') else '주의/실패'}",
        f"- 현재 인터넷: {'연결됨' if report.get('internet_now') else '오프라인/차단'}",
        f"- 요약: {report.get('summary')}",
        "",
        "## 환경 변수",
    ]
    for row in report.get("env", {}).get("rows") or []:
        mark = "OK" if row.get("ok") else "FAIL"
        lines.append(f"- [{mark}] `{row['name']}` = `{row['value']}`")
    stcfg = report.get("streamlit") or {}
    lines += [
        "",
        "## Streamlit",
        f"- 설정 파일: `{stcfg.get('path')}`",
        f"- gatherUsageStats=false: {stcfg.get('gatherUsageStats_false')}",
        f"- bind 127.0.0.1: {stcfg.get('bind_127')}",
        "",
        "## Ollama",
    ]
    ol = report.get("ollama") or {}
    lines.append(f"- URL: `{ol.get('url')}` local={ol.get('local')} reachable={ol.get('reachable')} ({ol.get('detail')})")
    lines += ["", "## 소스 정적 감사 (외부 URL/토큰)"]
    findings = (report.get("source_scan") or {}).get("findings") or []
    if not findings:
        lines.append("- 외부 URL/의심 토큰 없음 (스캔 범위: 프로젝트 .py)")
    else:
        for item in findings[:80]:
            lines.append(
                f"- [{item.get('severity')}] {item.get('file')}:{item.get('line')} "
                f"`{item.get('value')}` — {item.get('note')}"
            )
    lines += ["", "## netstat ESTABLISHED (python/ollama)"]
    net = report.get("netstat") or {}
    if net.get("error"):
        lines.append(f"- 오류: {net['error']}")
    elif not net.get("rows"):
        lines.append("- 감시 대상 ESTABLISHED 연결 없음(또는 프로세스 미기동)")
    else:
        for row in net.get("suspects") or []:
            lines.append(
                f"- [SUSPECT] {row.get('process')} pid={row.get('pid')} {row.get('local')} → {row.get('remote')}"
            )
        if not net.get("suspects"):
            lines.append("- 공인 IP ESTABLISHED 없음 (스냅샷 기준 OK)")
    lines += ["", "## 수동 체크리스트"]
    for item in report.get("manual_checklist") or []:
        lines.append(f"- [ ] {item['title']}: {item['detail']}")
    lines.append("")
    return "\n".join(lines)
