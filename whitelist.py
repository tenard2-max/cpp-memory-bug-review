"""초기화로 인정할 함수와 모듈 초기화 진입 함수를 저장한다."""

from __future__ import annotations

import json
from pathlib import Path

WHITELIST_PATH = Path(__file__).with_name("init_whitelist.json")
DEFAULT_INIT_FUNCTIONS = [
    "memset",
    "ZeroMemory",
    "SecureZeroMemory",
    "calloc",
    "strcpy",
    "strncpy",
    "sprintf",
    "_snprintf",
    "memcpy",
    "GetPrivateProfileStringAutoA",
]
DEFAULT_ENTRY_FUNCTIONS = ["Init", "OnInitDialog", "ResetData"]


def load_whitelist() -> dict:
    """파일이 없으면 기본 목록을 만들어 반환한다."""
    if not WHITELIST_PATH.exists():
        data = {
            "init_functions": list(DEFAULT_INIT_FUNCTIONS),
            "entry_functions": list(DEFAULT_ENTRY_FUNCTIONS),
        }
        save_whitelist(data)
        return data
    try:
        raw = json.loads(WHITELIST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"init_whitelist.json을 읽지 못했습니다: {error}") from error
    if not isinstance(raw, dict):
        raise ValueError("init_whitelist.json은 객체여야 합니다.")
    return {
        "init_functions": _names(raw.get("init_functions"), DEFAULT_INIT_FUNCTIONS),
        "entry_functions": _names(raw.get("entry_functions"), DEFAULT_ENTRY_FUNCTIONS),
    }


def save_whitelist(data: dict) -> None:
    payload = {
        "init_functions": _names(data.get("init_functions"), []),
        "entry_functions": _names(data.get("entry_functions"), []),
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    temporary = WHITELIST_PATH.with_suffix(".json.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(WHITELIST_PATH)


def add_name(kind: str, name: str) -> bool:
    """kind는 init_functions 또는 entry_functions다. 이미 있으면 False."""
    cleaned = _clean(name)
    if not cleaned:
        raise ValueError("함수 이름이 비어 있습니다.")
    data = load_whitelist()
    if cleaned in data[kind]:
        return False
    data[kind].append(cleaned)
    save_whitelist(data)
    return True


def remove_name(kind: str, name: str) -> None:
    data = load_whitelist()
    data[kind] = [item for item in data[kind] if item != name]
    save_whitelist(data)


def format_whitelist(data: dict) -> str:
    """시스템 프롬프트에 붙일 초기화 인정 목록이다."""
    init_names = ", ".join(data["init_functions"]) or "없음"
    entry_names = ", ".join(data["entry_functions"]) or "없음"
    return "\n".join(
        [
            "초기화로 인정하는 함수와 매크로: " + init_names,
            "클래스/모듈 초기화 진입 함수: " + entry_names,
            "선언하면서 = 0, = NULL, = {0,}를 하지 않은 변수는 미초기화다.",
            "읽기 전에 위 초기화 함수를 거치거나 직접 대입하지 않았다면, 다른 함수에 주소나 포인터로 넘겼어도 미초기화 사용이다.",
            "memset(p, 0, sizeof(p))처럼 포인터 자신의 크기만 지운 호출은 초기화로 인정하지 마라.",
            "진입 함수 안에서도 멤버와 지역 버퍼는 같은 규칙으로 초기화되어야 한다.",
        ]
    )


def _names(values, fallback: list[str]) -> list[str]:
    if not isinstance(values, list):
        values = fallback
    cleaned: list[str] = []
    for item in values:
        name = _clean(str(item))
        if name and name not in cleaned:
            cleaned.append(name)
    return cleaned


def _clean(name: str) -> str:
    return name.strip().removesuffix("()").strip()
