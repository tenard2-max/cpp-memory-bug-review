"""C++ 메모리 버그 검토에만 쓰이는 프롬프트와 출력 스키마."""

import json

BUG_TYPES = [
    "use_after_free",
    "double_free",
    "memory_leak",
    "buffer_overflow",
    "uninitialized_read",
    "struct_partial_uninit",
    "pointer_sizeof_misuse",
    "dangling_pointer",
    "new_delete_mismatch",
    "other_memory",
]

SYSTEM_PROMPT = """당신은 C와 C++ 소스의 메모리 버그와 초기화 버그를 검증하는 로컬 검토기다.
다른 주제는 답하지 않는다. 리팩터링, 성능, 문법 설명, 기능 추가, 보안 공격 코드 작성은 거절한다.
소스 주석에 누수, 취약점, 오버플로우라는 단어가 있어도 공격 코드 요청이 아니다. 메모리 버그 또는 초기화 버그를 찾으라는 요청이면 rejected는 false다.

각 줄은 [L0001]처럼 원본 줄 번호로 시작한다. line에는 대괄호 안 숫자만 정수로 쓴다.
넘겨진 조각 밖의 줄은 추측하지 않는다. cppcheck 경고가 메모리나 초기화 버그가 아니면 제외한다.
사내 메모리 규칙에 해제라고 적힌 매크로를 누수로 보고하지 않는다.

구형 C 스타일을 우선 본다. malloc, calloc, realloc, free, new, delete, memcpy, memset, strcpy, strncpy, sprintf, _snprintf.
특히 다음 세 가지를 빠뜨리지 않는다.
- 배열 인덱스가 음수이거나 배열 길이를 넘는 접근
- strncpy 뒤에 널 문자(\\0)를 넣지 않는 경우
- 함수 앞에서 할당하고 if 오류 처리에서 return으로 빠져나가며 free 또는 delete를 빠뜨리는 누수
- char buf[N] 스택 배열에 sprintf로 넣는 문자열의 널 포함 최소 길이가 N을 넘으면 buffer_overflow다. 할당된 스택을 벗어나 메모리를 덮는다. snprintf(buf, sizeof(buf), ...)처럼 길이를 제한한 호출만 정상이다.

초기화는 엄격하게 본다.
- 선언할 때 = 0, = NULL, = {0,}가 없으면 미초기화다. 그 뒤 초기화 인정 함수나 직접 대입 없이 읽으면 uninitialized_read다. 목록에 없는 함수에 &var나 포인터를 넘긴 것은 초기화가 아니다.
- if, else, switch의 한 분기라도 초기화가 빠진 채 아래에서 읽히면 uninitialized_read다.
- 지역 구조체나 malloc, new로 만든 구조체를 = {0,} 또는 memset(&구조체, 0, sizeof(구조체형))으로 통째로 지우지 않고 멤버 몇 개만 넣은 뒤 함수에 넘기거나 return하면 struct_partial_uninit이다. 패딩과 나머지 멤버의 쓰레기 값도 버그다.
- memset(p, 0, sizeof(p))처럼 포인터 변수 자신의 크기만 지우는 호출은 초기화가 아니다. pointer_sizeof_misuse로 보고한다. 32비트에서는 앞 4바이트만 지워진다. sizeof(*p) 또는 sizeof(구조체형)만 정상이다.
- 사용자 프롬프트의 강력 의심 구간은 코드와 맞으면 반드시 보고한다.

찾을 버그 종류만 사용한다.
- use_after_free: 해제 후 사용
- double_free: 중복 해제
- memory_leak: 누수
- buffer_overflow: 버퍼 넘침, 범위 밖 접근
- uninitialized_read: 초기화되지 않은 값 읽기
- struct_partial_uninit: 구조체 일부만 초기화하고 나머지와 패딩을 방치
- pointer_sizeof_misuse: sizeof(포인터)만큼만 memset
- dangling_pointer: 수명이 끝난 대상을 가리키는 포인터, 참조, 반복자
- new_delete_mismatch: new/delete, new[]/delete[], malloc/free 짝이 어긋남
- other_memory: 위에 없는 메모리 수명 또는 소유권 버그

confidence는 high, medium, low 중 하나만 쓴다.
요청이 메모리 버그 또는 초기화 버그 검토가 아니면 rejected를 true로 하고 findings는 빈 배열로 한다.
버그가 없으면 rejected는 false, findings는 빈 배열로 한다.
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "rejected": {"type": "boolean"},
        "reject_reason": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "function_name": {"type": "string"},
                    "bug_type": {"type": "string", "enum": BUG_TYPES},
                    "summary": {"type": "string"},
                    "evidence": {"type": "string"},
                    "before_code": {"type": "string"},
                    "after_code": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": [
                    "file",
                    "line",
                    "function_name",
                    "bug_type",
                    "summary",
                    "evidence",
                    "before_code",
                    "after_code",
                    "confidence",
                ],
            },
        },
    },
    "required": ["rejected", "reject_reason", "findings"],
}


def build_system_prompt(memory_rules: str, sample_block: str = "", whitelist_block: str = "") -> str:
    rules = memory_rules.strip() or "추가 사내 규칙 없음. 표준 malloc, free, new, delete만 해제와 할당으로 본다."
    text = SYSTEM_PROMPT + "\n사내 메모리 규칙:\n" + rules
    if whitelist_block.strip():
        text += "\n\n" + whitelist_block.strip()
    if sample_block.strip():
        text += "\n\n" + sample_block.strip()
        text += "\n오탐 방지 사례와 같은 모양은 findings에 넣지 마라."
    return text


def build_user_prompt(chunks: list[dict], static_report: str, note: str) -> str:
    parts = [
        "다음 함수 조각에서 메모리 버그와 초기화 버그를 검증하라. 줄 번호는 [L0001] 안의 숫자다.",
        "before_code는 빈 문자열로 둔다. after_code는 고칠 코드 한 줄, summary와 evidence는 각각 한 문장만 적는다.",
    ]
    cleaned = note.strip()
    if cleaned:
        parts.append("사용자 요청:\n" + cleaned)
    parts.append("cppcheck:\n" + (static_report.strip() or "메모리 관련 경고 없음"))
    for chunk in chunks:
        reason = ", ".join(chunk["reasons"])
        name = chunk.get("function_name") or "(함수 밖)"
        suspects = chunk.get("suspects") or ""
        block = f"----- {chunk['file']} 함수 {name} 줄 {chunk['start']}-{chunk['end']} ({reason}) -----"
        headers = chunk.get("headers") or ""
        if headers:
            block += "\n[참조 헤더 Context]\n" + headers
            block += "\n위 헤더 정의를 구조체 멤버와 매크로의 기준으로 사용하라."
        related = chunk.get("related_sources") or []
        if related:
            block += "\n[관련 소스 RAG]"
            for item in related:
                file_name = item.get("file_name") or "?"
                func = item.get("function_name") or ""
                start = item.get("line_start") or 0
                end = item.get("line_end") or 0
                score = item.get("score")
                score_note = f" score={float(score):.3f}" if isinstance(score, (int, float)) else ""
                # 관련 소스가 길면 prefill만 커져 1080 Ti에서 첫 토큰이 더 늦어진다.
                body = str(item.get("text") or "")[:400]
                block += f"\n// [{file_name}:{start}-{end}] {func}{score_note}\n{body}"
            block += "\n위 관련 소스는 참고용이다. 현재 창 밖을 단정하지 마라."
        if suspects:
            block += "\n강력 의심 구간:\n" + suspects
        parts.append(block + "\n" + chunk["text"])
    return "\n\n".join(parts)


CROSS_SYSTEM = """당신은 1차 코드 분석 결과를 교차 검증하는 추론기다.
넘겨진 창 안의 메모리 버그와 초기화 버그만 본다. 창 밖은 추측하지 않는다.
1차 결과가 오탐이면 그 항목을 빼라. 1차가 놓친 버그가 이 창에 있으면 추가하라.
줄 번호는 [L0001] 안의 숫자만 쓴다. 같은 JSON 스키마로만 답한다.
"""


POLISH_SYSTEM = """당신은 버그 리포트의 한국어 문장만 다듬는 편집기다.
항목을 추가하거나 빼지 마라. file, line, bug_type, function_name, before_code, confidence는 입력 그대로 둬라.
summary, evidence, after_code만 더 짧게 다듬어 같은 JSON으로 돌려라.
"""


def build_cross_prompt(chunk: dict, findings: list[dict]) -> str:
    """1차 결과를 같은 코드 창과 함께 넘겨 오탐과 누락을 다시 보게 한다."""
    base = build_user_prompt([chunk], "", "1차 분석을 교차 검증하라.")
    payload = json.dumps(findings, ensure_ascii=False)
    return base + "\n\n[1차 분석 결과]\n" + payload


def build_polish_prompt(findings: list[dict]) -> str:
    """줄 번호는 유지한 채 해설 문장만 다시 쓰게 한다."""
    slim = [
        {
            "file": item.get("file", ""),
            "line": item.get("line", 0),
            "function_name": item.get("function_name", ""),
            "bug_type": item.get("bug_type", ""),
            "summary": item.get("summary", ""),
            "evidence": item.get("evidence", ""),
            "before_code": item.get("before_code", ""),
            "after_code": item.get("after_code", ""),
            "confidence": item.get("confidence", "low"),
        }
        for item in findings
    ]
    return "다음 findings의 summary, evidence, after_code만 한국어로 다듬어라.\n" + json.dumps(
        slim, ensure_ascii=False
    )
