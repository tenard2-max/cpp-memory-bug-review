"""구형 VS 2008 소스의 인코딩을 읽고, 함수 단위로 자른 뒤 줄 번호를 붙인다."""

from __future__ import annotations

import re
from pathlib import Path

from suspects import scan_suspects

MEMORY_CALL = re.compile(
    r"\b(?:_snprintf|sprintf|malloc|calloc|realloc|free|memcpy|memset|strcpy|strncpy)\b"
    r"|\b(?:new|delete)\b"
    r"|SAFE_DELETE|SAFE_FREE|SAFE_RELEASE",
    re.IGNORECASE,
)
MAX_CHUNK_LINES = 500
SLIDE_MIN_LINES = 500
WINDOW_LINES = 500
OVERLAP_LINES = 50
STRUCT_WORD = re.compile(r"\bstruct\b")
POINTER_MARK = re.compile(r"->|(?<![&])&(?!&)\s*[A-Za-z_]")
_TYPE_PREFIX = {
    "char", "void", "int", "short", "long", "float", "double", "bool", "signed", "unsigned",
    "const", "volatile", "struct", "class", "BOOL", "BYTE", "WORD", "DWORD", "UINT", "ULONG",
    "LPCTSTR", "LPCSTR", "LPSTR", "LPTSTR", "TCHAR", "WCHAR", "HANDLE", "LPVOID", "PVOID",
}
NAME_PATTERN = re.compile(r"\b([A-Za-z_~][\w:]*)\s*\(")


def read_text(path: Path) -> str:
    """utf-8, cp949, euc-kr 순서로 읽고, 마지막에는 깨진 글자를 대체해서라도 반환한다."""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("euc-kr", errors="replace")


def read_lines(path: Path) -> list[str]:
    return read_text(path).splitlines()


def function_ranges(lines: list[str]) -> list[tuple[int, int]]:
    """중괄호 깊이 1인 블록을 함수 범위로 본다. 인덱스는 0부터다."""
    depth = 0
    stack: list[int] = []
    ranges: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        for char in line:
            if char == "{":
                if depth == 0:
                    stack.append(index)
                depth += 1
            elif char == "}" and depth:
                depth -= 1
                if depth == 0 and stack:
                    start = stack.pop()
                    signature = start
                    while signature > 0 and lines[signature - 1].strip():
                        previous = lines[signature - 1].strip()
                        if previous.endswith(";") or previous.endswith("}"):
                            break
                        signature -= 1
                        if start - signature > 8:
                            break
                    ranges.append((signature, index))
    return ranges


def function_name(lines: list[str], start: int, end: int) -> str:
    header = " ".join(lines[start : min(end + 1, start + 8)])
    match = NAME_PATTERN.search(header)
    return match.group(1) if match else ""


def function_name_at(lines: list[str], line: int) -> str:
    """보고된 줄이 들어 있는 함수 이름을 원본에서 다시 찾는다."""
    if line <= 0:
        return ""
    block = _contains(function_ranges(lines), line - 1)
    if block is None:
        return ""
    return function_name(lines, block[0], block[1])


def inject_line_numbers(lines: list[str], start: int, end: int) -> str:
    """LLM에 넘기기 전에 원본 줄 번호를 [L0001] 형태로 붙인다."""
    return "\n".join(f"[L{line_no:04d}] {lines[line_no - 1]}" for line_no in range(start + 1, end + 2))


def source_snippet(lines: list[str], line: int, radius: int = 3) -> str:
    """문제 줄과 앞뒤 줄을 원본 그대로 잘라 리포트에 넣는다."""
    if line <= 0 or not lines:
        return ""
    start = max(1, line - radius)
    end = min(len(lines), line + radius)
    return "\n".join(f"{number}: {lines[number - 1]}" for number in range(start, end + 1))


def _without_comments(lines: list[str]) -> list[str]:
    """주석 안의 단어는 분석 대상 판정에 쓰지 않는다."""
    cleaned: list[str] = []
    in_block = False
    for line in lines:
        code = line
        if in_block:
            if "*/" in code:
                code = code.split("*/", 1)[1]
                in_block = False
            else:
                cleaned.append("")
                continue
        while "/*" in code:
            before, _, rest = code.partition("/*")
            if "*/" in rest:
                code = before + " " + rest.split("*/", 1)[1]
            else:
                code = before
                in_block = True
                break
        cleaned.append(code.split("//", 1)[0])
    return cleaned


def _has_pointer(line: str) -> bool:
    """역참조, 주소, 포인터 선언만 본다. 곱셈 a * b 와 && 는 제외한다."""
    if POINTER_MARK.search(line):
        return True
    for match in re.finditer(r"\*", line):
        left = line[: match.start()].rstrip()
        right = line[match.end() :].lstrip()
        left_token = ""
        found = re.search(r"[A-Za-z_]\w*$", left)
        if found:
            left_token = found.group(0)
        if right.startswith("*") or right[:1] in "*;,)":
            if left_token:
                return True
            continue
        if right[:1].isalpha() or right[:1] == "_":
            if not left or left[-1] in "([=,{;!&:+-/%<>" or left.endswith("return"):
                return True
            if left_token[:1].isupper() or left_token in _TYPE_PREFIX:
                return True
    return False


def _is_type_definition(lines: list[str], start: int, end: int) -> bool:
    """구조체·열거·공용체·클래스 선언은 함수도 아니고 소거 대상도 아니다."""
    header = " ".join(lines[start : min(end + 1, start + 4)])
    if not re.search(r"\b(?:typedef\s+)?(?:struct|enum|union|class)\b", header):
        return False
    body = "\n".join(lines[start : end + 1])
    return MEMORY_CALL.search(body) is None and "->" not in body


def _local_type_context(source_text: str, chunk_text: str) -> str:
    """같은 파일에 있는 구조체 정의를, 그 이름을 쓰는 함수 창에 붙인다."""
    blocks: list[str] = []
    pattern = re.compile(r"typedef\s+struct\b[^{;]*\{.*?\}\s*(\w+)\s*;", re.S)
    for match in pattern.finditer(source_text):
        name = match.group(1)
        if re.search(rf"\b{re.escape(name)}\b", chunk_text):
            blocks.append(match.group(0).strip())
    return "\n\n".join(blocks)


def _contains(ranges: list[tuple[int, int]], line_index: int) -> tuple[int, int] | None:
    matches = [item for item in ranges if item[0] <= line_index <= item[1]]
    if not matches:
        return None
    return min(matches, key=lambda item: item[1] - item[0])


def _windows(start: int, end: int, anchors: list[int]) -> tuple[list[tuple[int, int]], int]:
    """500줄 이하는 통째로 두고, 더 긴 함수는 키워드가 있는 500줄 창만 남긴다."""
    if end - start + 1 <= SLIDE_MIN_LINES:
        return [(start, end)], 0
    windows = _overlap_windows(start, end, WINDOW_LINES, OVERLAP_LINES)
    kept = [window for window in windows if any(window[0] <= anchor <= window[1] for anchor in anchors)]
    return kept, len(windows) - len(kept)


def _overlap_windows(start: int, end: int, size: int, overlap: int) -> list[tuple[int, int]]:
    """긴 함수를 겹치는 구간으로 나눈다. 경계에 걸친 할당과 해제가 빠지지 않게 한다."""
    step = max(1, size - overlap)
    windows: list[tuple[int, int]] = []
    cursor = start
    while cursor <= end:
        window_end = min(end, cursor + size - 1)
        windows.append((cursor, window_end))
        if window_end >= end:
            break
        cursor += step
    return windows


def build_chunks(
    files: list[Path], issues: list[dict], project_root: Path | None = None
) -> tuple[list[dict], dict]:
    """메모리·포인터·구조체가 없는 함수는 버리고, 500줄 초과 함수는 겹치는 창으로 나눈다."""
    from headers import HeaderIndex

    roots = []
    if project_root is not None and project_root.is_dir():
        roots.append(project_root.resolve())
    for path in files:
        parent = path.resolve().parent
        if parent not in roots:
            roots.append(parent)
    header_index = HeaderIndex(roots)
    file_text = {path.resolve(): read_text(path) for path in files}
    issues_by_file: dict[str, list[dict]] = {}
    for issue in issues:
        issues_by_file.setdefault(str(Path(issue["file"]).resolve()), []).append(issue)

    chunks: list[dict] = []
    function_total = 0
    pruned = 0
    dropped_windows = 0
    for path in files:
        resolved = str(path.resolve())
        lines = read_lines(path)
        source_text = file_text.get(path.resolve(), "\n".join(lines))
        struct_names = header_index.struct_names(source_text)
        struct_pattern = None
        if struct_names:
            struct_pattern = re.compile(r"\b(?:%s)\b" % "|".join(re.escape(name) for name in sorted(struct_names)))
        ranges = function_ranges(lines)
        code_lines = _without_comments(lines)
        anchors: dict[int, list[str]] = {}
        for issue in issues_by_file.get(resolved, []):
            if issue["line"] <= 0:
                continue
            anchors.setdefault(issue["line"] - 1, []).append(f"cppcheck {issue['id']}: {issue['message']}")
        for index, line in enumerate(code_lines):
            if MEMORY_CALL.search(line) or _has_pointer(line) or STRUCT_WORD.search(line):
                anchors.setdefault(index, []).append("메모리·포인터 또는 구조체")
            if struct_pattern is not None:
                struct_match = struct_pattern.search(line)
                if struct_match:
                    anchors.setdefault(index, []).append(f"헤더 구조체 {struct_match.group(0)}")
        for index, message in scan_suspects(lines, ranges):
            anchors.setdefault(index, []).append(message)
        seen_spans: set[tuple[int, int]] = set()
        covered: set[int] = set()
        for block_start, block_end in ranges:
            if _is_type_definition(lines, block_start, block_end):
                covered.update(range(block_start, block_end + 1))
                continue
            function_total += 1
            block_anchors = [index for index in anchors if block_start <= index <= block_end]
            covered.update(range(block_start, block_end + 1))
            if not block_anchors:
                pruned += 1
                continue
            name = function_name(lines, block_start, block_end)
            windows, dropped = _windows(block_start, block_end, block_anchors)
            dropped_windows += dropped
            if not windows:
                pruned += 1
                continue
            sliding = block_end - block_start + 1 > SLIDE_MIN_LINES
            for window_index, (start, end) in enumerate(windows, start=1):
                _append_chunk(
                    chunks,
                    seen_spans,
                    path,
                    lines,
                    source_text,
                    header_index,
                    anchors,
                    start,
                    end,
                    name,
                    sliding,
                    window_index,
                    len(windows),
                )
        for anchor in anchors:
            if anchor in covered:
                continue
            start = max(0, anchor - 20)
            end = min(len(lines) - 1, start + MAX_CHUNK_LINES - 1)
            _append_chunk(
                chunks,
                seen_spans,
                path,
                lines,
                source_text,
                header_index,
                anchors,
                start,
                end,
                "",
                False,
                1,
                1,
            )
    return chunks, {
        "functions": function_total,
        "pruned": pruned,
        "dropped_windows": dropped_windows,
        "windows": len(chunks),
    }


def _append_chunk(
    chunks: list[dict],
    seen_spans: set[tuple[int, int]],
    path: Path,
    lines: list[str],
    source_text: str,
    header_index,
    anchors: dict[int, list[str]],
    start: int,
    end: int,
    name: str,
    sliding: bool,
    window_index: int,
    window_count: int,
) -> None:
    if (start, end) in seen_spans:
        return
    seen_spans.add((start, end))
    reasons: list[str] = []
    for index in range(start, end + 1):
        reasons.extend(anchors.get(index, []))
    unique_reasons = sorted(set(reasons))
    suspect_lines = []
    seen_suspects: set[tuple[int, str]] = set()
    for index in range(start, end + 1):
        for message in anchors.get(index, []):
            if not message.startswith("강력 의심"):
                continue
            key = (index + 1, message)
            if key in seen_suspects:
                continue
            seen_suspects.add(key)
            suspect_lines.append({"line": index + 1, "message": message})
    numbered = inject_line_numbers(lines, start, end)
    from symbol_index import select_context

    selected = select_context(numbered, header_index.context_blocks(source_text, numbered))
    headers = selected["text"]
    local_types = _local_type_context(source_text, numbered)
    if local_types:
        headers = (local_types + "\n" + headers).strip()
    related_sources: list[dict] = []
    try:
        from samples_db import vector_search_enabled
        from vector_store import is_available, query_similar_sources

        if vector_search_enabled() and is_available():
            related_sources = query_similar_sources(
                numbered,
                limit=2,
                exclude_path=str(path.resolve()),
            )
    except Exception:
        related_sources = []
    chunks.append(
        {
            "file": path.name,
            "path": str(path),
            "function_name": name,
            "start": start + 1,
            "end": end + 1,
            "sliding": sliding,
            "window_index": window_index,
            "window_count": window_count,
            "reasons": unique_reasons,
            "suspects": "\n".join(item["message"] for item in suspect_lines),
            "suspect_lines": suspect_lines,
            "headers": headers,
            "context_included": selected["included"],
            "context_omitted": selected["omitted"],
            "related_sources": related_sources,
            "text": numbered,
        }
    )


def load_memory_rules(path: Path) -> str:
    if not path.exists():
        return ""
    return read_text(path).strip()
