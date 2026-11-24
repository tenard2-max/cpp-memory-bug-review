"""사내 버그 샘플을 저장하고, 지금 보는 함수와 맞는 예제만 고른다."""

from __future__ import annotations

import json
import re
from pathlib import Path

from chunks import MEMORY_CALL

SAMPLES_PATH = Path(__file__).with_name("bug_samples.json")
MAX_INJECTED = 12
MAX_PROMPT_LINES = 16
MACRO_PATTERN = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")
_VECTOR_ENABLED = True


def set_vector_search_enabled(enabled: bool) -> None:
    """검토 파이프라인이 벡터 선별을 켤지 끈다."""
    global _VECTOR_ENABLED
    _VECTOR_ENABLED = bool(enabled)


def vector_search_enabled() -> bool:
    return bool(_VECTOR_ENABLED)

DEFAULT_SAMPLES = [
    {
        "id": 1,
        "category": "포인터 sizeof 오용",
        "keywords": ["memset", "sizeof", "pPacket"],
        "bad_code": """void ClearPacket(TRAN_PACKET* pPacket) {
    memset(pPacket, 0x00, sizeof(pPacket));
    SendPacket(pPacket);
}""",
        "good_code": """memset(pPacket, 0x00, sizeof(TRAN_PACKET));
SendPacket(pPacket);""",
        "explanation": "sizeof(pPacket)은 포인터 크기라 32비트에서 4바이트만 지운다. 56바이트 구조체의 나머지와 패딩은 쓰레기 값이다. sizeof(TRAN_PACKET) 또는 sizeof(*pPacket)을 써야 한다.",
        "is_false_positive": False,
    },
    {
        "id": 2,
        "category": "구조체 부분 미초기화",
        "keywords": ["SendPacket", "packet", "memset"],
        "bad_code": """void MakePacket() {
    TRAN_PACKET packet;
    packet.nType = 1;
    SendPacket(&packet);
}""",
        "good_code": """TRAN_PACKET packet;
memset(&packet, 0, sizeof(packet));
packet.nType = 1;
SendPacket(&packet);""",
        "explanation": "일부 멤버만 넣으면 나머지 멤버와 패딩에 쓰레기 값이 남는다. 보내기 전에 = {0,} 또는 memset(&packet, 0, sizeof(packet))으로 구조체 전체를 먼저 지워야 한다.",
        "is_false_positive": False,
    },
    {
        "id": 3,
        "category": "조기 리턴 시 미해제",
        "keywords": ["malloc", "new", "return"],
        "bad_code": """BOOL LoadAccount(int err) {
    char* buffer = (char*)malloc(128);
    if (buffer == NULL) {
        return FALSE;
    }
    if (err) {
        return FALSE;
    }
    free(buffer);
    return TRUE;
}""",
        "good_code": """if (err) {
    free(buffer);
    return FALSE;
}
free(buffer);
return TRUE;""",
        "explanation": "할당에 성공한 뒤 if (err) return으로 빠지면 free 또는 delete가 실행되지 않는다. NULL이라 할당이 실패해서 바로 return하는 경우는 누수가 아니다.",
        "is_false_positive": False,
    },
    {
        "id": 4,
        "category": "strncpy 널 누락",
        "keywords": ["strncpy"],
        "bad_code": """void CopyCard(const char* src) {
    char dest[16];
    strncpy(dest, src, sizeof(dest));
    UseCard(dest);
}""",
        "good_code": """strncpy(dest, src, sizeof(dest));
dest[sizeof(dest) - 1] = '\\0';
UseCard(dest);""",
        "explanation": "strncpy는 길이가 꽉 차면 널 문자를 넣지 않는다. 마지막 바이트에 dest[sizeof(dest)-1] = '\\0'을 넣어야 버퍼 너머를 읽지 않는다.",
        "is_false_positive": False,
    },
    {
        "id": 5,
        "category": "스택 버퍼 오버플로우",
        "keywords": ["sprintf", "logBuffer"],
        "bad_code": """void WriteLog() {
    char logBuffer[16];
    sprintf(logBuffer, "Packet Processed: %s", "dfjsdlfklfdkl");
}""",
        "good_code": """char logBuffer[64];
snprintf(logBuffer, sizeof(logBuffer), "Packet Processed: %s", "dfjsdlfklfdkl");""",
        "explanation": "char logBuffer[16]은 16바이트다. \"Packet Processed: \"와 \"dfjsdlfklfdkl\"과 널만 합쳐도 32바이트라 스택을 침범한다. 배열을 키우거나 snprintf로 길이를 제한해야 한다.",
        "is_false_positive": False,
    },
]


def load_samples() -> list[dict]:
    """파일이 없으면 기본 샘플 3개를 만들어 읽고, 있으면 그 내용을 반환한다."""
    if not SAMPLES_PATH.exists():
        save_samples(DEFAULT_SAMPLES)
        return [dict(item) for item in DEFAULT_SAMPLES]
    try:
        raw = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"bug_samples.json을 읽지 못했습니다: {error}") from error
    if not isinstance(raw, list):
        raise ValueError("bug_samples.json은 배열이어야 합니다.")
    return [_normalize(item, index + 1) for index, item in enumerate(raw)]


def save_samples(samples: list[dict], *, sync_vector: bool = True) -> None:
    """같은 내용으로 바꾸다가 파일이 깨지지 않도록 임시 파일에 쓴 뒤 교체한다."""
    normalized = [_normalize(item, index + 1) for index, item in enumerate(samples)]
    payload = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"
    temporary = SAMPLES_PATH.with_suffix(".json.tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(SAMPLES_PATH)
    # 벡터 인덱스는 필요할 때만 맞춘다. 실패해도 JSON 저장은 유지한다.
    if not sync_vector:
        return
    try:
        from vector_store import ensure_sample_index, is_available

        if is_available():
            ensure_sample_index(normalized, force=False)
    except Exception:
        pass


def add_sample(fields: dict, *, sync_vector: bool = True) -> tuple[dict, bool]:
    """새 샘플을 추가한다. 같은 정상 코드가 이미 있으면 새로 만들지 않는다."""
    samples = load_samples()
    sample = _normalize(fields, _next_id(samples))
    if not sample["bad_code"]:
        raise ValueError("문제 코드가 비어 있습니다.")
    if not sample["keywords"]:
        raise ValueError("키워드가 하나 이상 필요합니다.")
    if sample["is_false_positive"]:
        for current in samples:
            if current["is_false_positive"] and current["bad_code"] == sample["bad_code"]:
                return current, False
    if sample["id"] in {item["id"] for item in samples}:
        sample["id"] = _next_id(samples)
    samples.append(sample)
    save_samples(samples, sync_vector=sync_vector)
    return sample, True


def delete_sample(sample_id: int) -> None:
    samples = [item for item in load_samples() if item["id"] != sample_id]
    save_samples(samples)


def clear_samples() -> int:
    """등록 샘플을 모두 지우고 벡터 인덱스를 비운다. 반환은 삭제 전 건수."""
    before = len(load_samples())
    save_samples([], sync_vector=False)
    try:
        from vector_store import is_available, rebuild_sample_index

        if is_available():
            rebuild_sample_index([])
    except Exception:
        pass
    return before


def reset_samples_to_default() -> int:
    """호환용. 더 이상 내장 5건으로 되돌리지 않고 clear_samples()와 같다."""
    return clear_samples()


def import_samples(raw: list, replace: bool) -> int:
    """JSON 배열을 추가하거나 전체 목록을 그 내용으로 바꾼다."""
    if not isinstance(raw, list):
        raise ValueError("불러올 JSON은 샘플 배열이어야 합니다.")
    incoming = [_normalize(item, index + 1) for index, item in enumerate(raw)]
    if replace:
        save_samples(incoming)
        return len(incoming)
    current = load_samples()
    by_id = {item["id"]: item for item in current}
    for item in incoming:
        if item["id"] in by_id or item["id"] <= 0:
            if item["id"] in by_id:
                by_id[item["id"]] = item
                continue
            item["id"] = _next_id(list(by_id.values()))
        by_id[item["id"]] = item
    save_samples(list(by_id.values()))
    return len(incoming)


SAMPLE_MD_TEMPLATE = """## 버그 종류
조기 리턴 시 미해제

## 키워드
malloc, return

## 문제 코드
```c
BOOL LoadAccount(int err) {
    char* buffer = (char*)malloc(128);
    if (err) {
        return FALSE;
    }
    free(buffer);
    return TRUE;
}
```

## 수정 코드
```c
if (err) {
    free(buffer);
    return FALSE;
}
free(buffer);
return TRUE;
```

## 해설
할당 성공 뒤 조기 return 하면 free가 빠진다.

## 오탐 방지
아니오

---

## 버그 종류
오탐 예외 예시

## 키워드
SAFE_FREE

## 문제 코드
```c
SAFE_FREE(p);
```

## 수정 코드
```c
SAFE_FREE(p);
```

## 해설
SAFE_FREE는 사내 정상 해제 매크로다. 같은 패턴은 누수로 보지 마라.

## 오탐 방지
예
"""

_SECTION_ALIASES = {
    "버그 종류": "category",
    "category": "category",
    "종류": "category",
    "키워드": "keywords",
    "keywords": "keywords",
    "문제 코드": "bad_code",
    "bad_code": "bad_code",
    "문제코드": "bad_code",
    "수정 코드": "good_code",
    "good_code": "good_code",
    "수정코드": "good_code",
    "해설": "explanation",
    "explanation": "explanation",
    "설명": "explanation",
    "오탐 방지": "is_false_positive",
    "오탐방지": "is_false_positive",
    "false_positive": "is_false_positive",
    "is_false_positive": "is_false_positive",
}
_HEADING = re.compile(r"^#{1,3}\s+(.+?)\s*$")
_FENCE = re.compile(r"^```(?:\w+)?\s*$")


def _truthy(text: str) -> bool:
    value = text.strip().lower()
    return value in {"예", "y", "yes", "true", "1", "온", "on", "오탐", "정상"}


def _strip_code_fence(body: str) -> str:
    lines = body.strip().splitlines()
    if len(lines) >= 2 and _FENCE.match(lines[0]) and _FENCE.match(lines[-1]):
        return "\n".join(lines[1:-1]).strip()
    return body.strip()


def parse_sample_markdown(text: str) -> list[dict]:
    """MD에서 샘플 목록을 읽는다. `---` 구분선으로 여러 건을 나눈다."""
    raw = (text or "").replace("\r\n", "\n").strip()
    if not raw:
        raise ValueError("MD 내용이 비어 있습니다.")
    chunks = re.split(r"\n\s*---\s*\n", raw)
    samples: list[dict] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        fields: dict[str, str] = {}
        current_key = ""
        buffer: list[str] = []

        def flush() -> None:
            nonlocal current_key, buffer
            if not current_key:
                buffer = []
                return
            fields[current_key] = "\n".join(buffer).strip()
            current_key = ""
            buffer = []

        for line in chunk.splitlines():
            heading = _HEADING.match(line)
            if heading:
                title = heading.group(1).strip()
                mapped = _SECTION_ALIASES.get(title) or _SECTION_ALIASES.get(title.lower())
                if mapped:
                    flush()
                    current_key = mapped
                    continue
            buffer.append(line)
        flush()
        if not fields:
            continue
        sample = {
            "category": fields.get("category") or "미분류",
            "keywords": fields.get("keywords") or "",
            "bad_code": _strip_code_fence(fields.get("bad_code") or ""),
            "good_code": _strip_code_fence(fields.get("good_code") or ""),
            "explanation": fields.get("explanation") or "",
            "is_false_positive": _truthy(fields.get("is_false_positive") or ""),
        }
        if not sample["bad_code"]:
            raise ValueError(f"MD 샘플 '{sample['category']}'에 문제 코드가 없습니다.")
        if not str(sample["keywords"]).strip():
            raise ValueError(f"MD 샘플 '{sample['category']}'에 키워드가 없습니다.")
        samples.append(sample)
    if not samples:
        raise ValueError(
            "MD에서 샘플을 찾지 못했습니다. "
            "## 버그 종류 / ## 키워드 / ## 문제 코드 / ## 수정 코드 / ## 해설 형식을 쓰세요."
        )
    return samples


def import_samples_from_markdown(text: str, replace: bool = False) -> int:
    """MD 텍스트를 파싱해 샘플을 추가하거나 교체한다. 벡터 동기화는 마지막에 한 번만 한다."""
    incoming = parse_sample_markdown(text)
    if replace:
        save_samples(incoming, sync_vector=True)
        return len(incoming)
    samples = load_samples()
    added = 0
    for fields in incoming:
        sample = _normalize(fields, _next_id(samples))
        if not sample["bad_code"]:
            raise ValueError(f"MD 샘플 '{sample['category']}'에 문제 코드가 없습니다.")
        if not sample["keywords"]:
            raise ValueError(f"MD 샘플 '{sample['category']}'에 키워드가 없습니다.")
        if sample["is_false_positive"]:
            exists = any(
                current["is_false_positive"] and current["bad_code"] == sample["bad_code"]
                for current in samples
            )
            if exists:
                continue
        if sample["id"] in {item["id"] for item in samples}:
            sample["id"] = _next_id(samples)
        samples.append(sample)
        added += 1
    save_samples(samples, sync_vector=True)
    return added


def register_false_positive(code: str, function_name: str, summary: str) -> tuple[dict, bool]:
    """리포트가 정상 코드를 버그로 부른 조각을 네거티브 샘플로 남긴다."""
    snippet = code.strip()
    keywords = keywords_from_code(snippet, function_name)
    reason = summary.strip() or "리포트에서 정상으로 표시한 패턴"
    return add_sample(
        {
            "category": "오탐 예외",
            "keywords": keywords,
            "bad_code": snippet,
            "good_code": snippet,
            "explanation": f"이 코드는 사내 정상 처리다. 같은 패턴은 버그로 보고하지 마라. {reason}",
            "is_false_positive": True,
        }
    )


def keywords_from_code(code: str, function_name: str = "") -> list[str]:
    """예외 학습 때 다음에 다시 맞출 수 있도록 함수명, 메모리 호출, 매크로를 뽑는다."""
    found: list[str] = []
    if function_name.strip():
        found.append(function_name.strip())
    found.extend(match.group(0) for match in MEMORY_CALL.finditer(code))
    found.extend(match.group(0) for match in MACRO_PATTERN.finditer(code))
    unique: list[str] = []
    for item in found:
        if item not in unique:
            unique.append(item)
    return unique[:8] or ["정상패턴"]


def select_samples(
    code: str,
    function_name: str = "",
    limit: int = MAX_INJECTED,
    *,
    use_vector: bool | None = None,
) -> list[dict]:
    """함수와 맞는 샘플을 고른다. 벡터 검색이 켜져 있으면 BGE-M3+Chroma를 우선하고 키워드로 보강한다."""
    enabled = _VECTOR_ENABLED if use_vector is None else bool(use_vector)
    samples = load_samples()
    by_id = {item["id"]: item for item in samples}
    haystack = f"{function_name}\n{code}"
    keyword_scores: dict[int, float] = {}
    for sample in samples:
        keywords = sample["keywords"]
        if not keywords:
            continue
        hits = [keyword for keyword in keywords if _keyword_in(keyword, haystack)]
        if not hits:
            continue
        keyword_scores[sample["id"]] = len(hits) / max(1, len(keywords)) + (0.25 if len(hits) == len(keywords) else 0.0)

    vector_scores: dict[int, float] = {}
    if enabled:
        try:
            from vector_store import ensure_sample_index, is_available, query_similar_samples

            if is_available():
                ensure_sample_index(samples, force=False)
                for row in query_similar_samples(haystack, limit=max(limit * 3, 6)):
                    sample_id = int(row["id"])
                    if sample_id in by_id:
                        vector_scores[sample_id] = float(row.get("score") or 0.0)
        except Exception:
            vector_scores = {}

    if not keyword_scores and not vector_scores:
        return []

    # 벡터 0.7 + 키워드 0.3. 키워드만 있으면 키워드 점수만 사용.
    combined: list[tuple[float, int, dict]] = []
    candidate_ids = set(keyword_scores) | set(vector_scores)
    for sample_id in candidate_ids:
        sample = by_id.get(sample_id)
        if sample is None:
            continue
        vector_score = vector_scores.get(sample_id, 0.0)
        keyword_score = keyword_scores.get(sample_id, 0.0)
        if vector_scores and keyword_scores:
            score = 0.7 * vector_score + 0.3 * keyword_score
            if vector_score > 0 and keyword_score > 0:
                reason = "hybrid"
            elif vector_score > 0:
                reason = "vector"
            else:
                reason = "keyword"
        elif vector_scores:
            score = vector_score
            reason = "vector"
        else:
            score = keyword_score
            reason = "keyword"
        if score <= 0:
            continue
        picked = dict(sample)
        picked["_select_score"] = round(float(score), 4)
        picked["_select_reason"] = reason
        picked["_vector_score"] = round(float(vector_score), 4)
        picked["_keyword_score"] = round(float(keyword_score), 4)
        combined.append((score, -sample_id, picked))
    combined.sort(reverse=True)
    # 같은 점수면 버그 종류를 고르게 넣어, 한 함수의 여러 버그가 앞번호 3개에 가려지지 않게 한다.
    return _diversify_by_category([item[2] for item in combined], limit)


def _diversify_by_category(ranked: list[dict], limit: int) -> list[dict]:
    """점수 순을 유지하되, 먼저 종류별로 하나씩 채운 뒤 나머지를 채운다."""
    if limit <= 0 or not ranked:
        return []
    selected: list[dict] = []
    used_ids: set[int] = set()
    used_categories: set[str] = set()
    for sample in ranked:
        category = str(sample.get("category") or "")
        sample_id = int(sample.get("id") or 0)
        if sample_id in used_ids or category in used_categories:
            continue
        selected.append(sample)
        used_ids.add(sample_id)
        used_categories.add(category)
        if len(selected) >= limit:
            return selected
    for sample in ranked:
        sample_id = int(sample.get("id") or 0)
        if sample_id in used_ids:
            continue
        selected.append(sample)
        used_ids.add(sample_id)
        if len(selected) >= limit:
            break
    return selected


def format_samples(samples: list[dict]) -> str:
    """시스템 프롬프트의 참고 사례 섹션. 긴 코드는 앞부분만 남긴다."""
    if not samples:
        return ""
    # 많이 넣을수록 코드 길이를 줄여 컨텍스트를 지킨다.
    code_lines = 12 if len(samples) <= 4 else 8 if len(samples) <= 8 else 5
    bug_n = sum(1 for sample in samples if not sample.get("is_false_positive"))
    blocks = [
        "[참고할 사내 버그 및 예외 사례]",
        f"버그 사례는 {bug_n}개다. 창에 같은 패턴이 있으면 findings에 모두 넣고, "
        "앞부분만 쓰고 중간에 멈추지 마라. 줄마다 따로 보고하고 한두 건만 고르지 마라.",
    ]
    for index, sample in enumerate(samples, start=1):
        if sample["is_false_positive"]:
            kind = "오탐 방지. 이 패턴은 사내 정상 코드이니 버그로 보고하지 마라."
        else:
            kind = "버그 사례. 같은 유형이면 반드시 찾아 보고하라."
        bug_hint = _bug_type_hint(sample)
        header = f"{index}. {sample['category']} ({kind})"
        if bug_hint:
            header += f" bug_type={bug_hint}"
        blocks.append(
            "\n".join(
                [
                    header,
                    "문제 코드:",
                    _clip(sample["bad_code"], max_lines=code_lines),
                    "올바른 코드:",
                    _clip(sample["good_code"], max_lines=code_lines),
                    f"해설: {_clip(sample['explanation'], max_lines=3)}",
                ]
            )
        )
    return "\n\n".join(blocks)


def _bug_type_hint(sample: dict) -> str:
    """프롬프트용 enum 힌트. 샘플에 bug_type이 없으면 카테고리·키워드로 추정한다."""
    explicit = str(sample.get("bug_type") or "").strip()
    if explicit:
        return explicit
    text = f"{sample.get('category') or ''} {' '.join(sample.get('keywords') or [])}".lower()
    if "double" in text or "이중" in text:
        return "double_free"
    if "leak" in text or "누수" in text:
        return "memory_leak"
    if "sizeof" in text:
        return "pointer_sizeof_misuse"
    if any(word in text for word in ("overflow", "오버플", "sprintf", "memcpy", "strcat", "버퍼")):
        return "buffer_overflow"
    if any(word in text for word in ("uninit", "미초기", "초기화", "wild")):
        return "uninitialized_read"
    if "dangling" in text or "댕글" in text:
        return "dangling_pointer"
    return ""


def _normalize(raw: dict, fallback_id: int) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("샘플 항목은 객체여야 합니다.")
    keywords = raw.get("keywords") or []
    if isinstance(keywords, str):
        keywords = keywords.split(",")
    cleaned = []
    for item in keywords:
        text = str(item).strip()
        if text and text not in cleaned:
            cleaned.append(text)
    try:
        sample_id = int(raw.get("id") or fallback_id)
    except (TypeError, ValueError):
        sample_id = fallback_id
    bug_type = str(raw.get("bug_type") or "").strip()
    return {
        "id": sample_id,
        "category": str(raw.get("category") or "").strip() or "미분류",
        "keywords": cleaned,
        "bad_code": str(raw.get("bad_code") or "").strip(),
        "good_code": str(raw.get("good_code") or "").strip(),
        "explanation": str(raw.get("explanation") or "").strip(),
        "is_false_positive": bool(raw.get("is_false_positive")),
        "bug_type": bug_type,
    }


def _next_id(samples: list[dict]) -> int:
    return max((item["id"] for item in samples), default=0) + 1


def _keyword_in(keyword: str, text: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(keyword) + r"(?!\w)"
    flags = 0 if _is_mixed_case(keyword) else re.IGNORECASE
    return re.search(pattern, text, flags) is not None


def _is_mixed_case(keyword: str) -> bool:
    letters = [char for char in keyword if char.isalpha()]
    return any(char.islower() for char in letters) and any(char.isupper() for char in letters)


def _clip(text: str, max_lines: int = MAX_PROMPT_LINES) -> str:
    lines = text.splitlines() or [""]
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[:max_lines]) + "\n..."
