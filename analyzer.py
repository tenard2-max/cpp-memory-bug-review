"""cppcheck만 1차 필터로 사용한다. VS 2008 소스에는 빌드 DB가 없어도 파일 단위로 동작한다."""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ElementTree
from pathlib import Path

MEMORY_IDS = {
    "memleak",
    "memleakOnRealloc",
    "mismatchAllocDealloc",
    "deallocuse",
    "doubleFree",
    "deallocDealloc",
    "autovarInvalidDeallocation",
    "bufferAccessOutOfBounds",
    "arrayIndexOutOfBounds",
    "negativeIndex",
    "uninitvar",
    "uninitdata",
    "uninitMemberVar",
    "uninitStructMember",
    "nullPointer",
    "nullPointerRedundantCheck",
    "ctunullpointer",
    "invalidLifetime",
    "danglingLifetime",
    "danglingReference",
    "eraseDereference",
}
MEMORY_WORDS = ("memory", "leak", "free", "alloc", "buffer", "null", "uninit", "dangling", "sizeof")


def cppcheck_path() -> str | None:
    return shutil.which("cppcheck")


def _is_memory_issue(issue_id: str, message: str) -> bool:
    if issue_id in MEMORY_IDS:
        return True
    lowered = f"{issue_id} {message}".lower()
    return any(word in lowered for word in MEMORY_WORDS)


def run_cppcheck(files: list[Path], standard: str = "c++03", timeout: int = 90) -> tuple[list[dict], str]:
    """메모리 관련 cppcheck 경고를 구조와 원문으로 반환한다."""
    executable = cppcheck_path()
    if not executable:
        return [], "cppcheck가 설치되어 있지 않다. 메모리 호출이 있는 함수만 모델에 넘긴다."
    if not files:
        return [], "검사할 소스가 없다."

    command = [
        executable,
        "--enable=warning,performance,portability",
        f"--std={standard}",
        "--inline-suppr",
        "--suppress=missingIncludeSystem",
        "--xml",
        "--xml-version=2",
        *[str(path) for path in files],
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return [], "cppcheck 시간 초과"
    except OSError as error:
        return [], f"cppcheck 실행 실패: {error}"

    raw = (completed.stderr or completed.stdout or "").strip()
    issues = _parse_xml(raw)
    if not issues and "<results" not in raw:
        return [], raw or "cppcheck 결과 없음"
    lines = [
        f"{item['file']}:{item['line']}: {item['severity']}: {item['id']}: {item['message']}"
        for item in issues
    ]
    report = "\n".join(lines) if lines else "메모리 관련 cppcheck 경고 없음"
    return issues, report


def _parse_xml(raw: str) -> list[dict]:
    start = raw.find("<results")
    if start < 0:
        return []
    try:
        root = ElementTree.fromstring(raw[start:])
    except ElementTree.ParseError:
        return []
    issues: list[dict] = []
    for error in root.findall(".//error"):
        location = error.find("location")
        if location is None:
            continue
        issue_id = error.get("id", "")
        message = error.get("msg", "")
        if not _is_memory_issue(issue_id, message):
            continue
        try:
            line = int(location.get("line", "0"))
        except ValueError:
            line = 0
        issues.append(
            {
                "file": location.get("file", ""),
                "line": line,
                "id": issue_id,
                "severity": error.get("severity", ""),
                "message": message,
            }
        )
    return issues
