"""memset(포인터, sizeof(포인터)), 매개변수 배열 sizeof, 스택 sprintf 넘침을 함수 안에서 찾는다."""

from __future__ import annotations

import re

MEMSET_POINTER = re.compile(
    r"\bmemset\s*\(\s*([A-Za-z_]\w*)\s*,[\s\S]{0,120}?sizeof\s*\(\s*\1\s*\)",
)
ZERO_POINTER = re.compile(
    r"\b(?:ZeroMemory|SecureZeroMemory)\s*\(\s*([A-Za-z_]\w*)\s*,\s*sizeof\s*\(\s*\1\s*\)",
)
PARAM_ARRAY = re.compile(
    r"(?:const\s+)?(?:unsigned\s+)?(?:struct\s+|class\s+)?(?:[\w:]+)\s+(\w+)\s*\[\s*[^\]]*\]",
)
ARRAY_DECL = re.compile(r"\b(\w+)\s*\[\s*[^\]]*\]")
SIZEOF_NAME = re.compile(r"\bsizeof\s*\(\s*(\w+)\s*\)")


def scan_suspects(lines: list[str], ranges: list[tuple[int, int]]) -> list[tuple[int, str]]:
    """줄 인덱스와 강력 의심 문구를 반환한다. 같은 줄의 같은 문구는 한 번만 남긴다."""
    found: list[tuple[int, str]] = []
    seen: set[tuple[int, str]] = set()

    def add(index: int, message: str) -> None:
        if index < 0 or (index, message) in seen:
            return
        seen.add((index, message))
        found.append((index, message))

    for index, line in enumerate(lines):
        if _covered(ranges, index):
            continue
        _add_memset(line, index, set(), add)

    for start, end in ranges:
        signature, body_start = _signature(lines, start, end)
        param_arrays = set(PARAM_ARRAY.findall(signature))
        body = "\n".join(lines[body_start : end + 1])
        local_arrays = set(ARRAY_DECL.findall(body)) - param_arrays
        for index in range(start, end + 1):
            _add_memset(lines[index], index, local_arrays, add)
        for index in range(body_start, end + 1):
            for match in SIZEOF_NAME.finditer(lines[index]):
                name = match.group(1)
                if name in param_arrays:
                    add(index, f"강력 의심: 매개변수 배열 {name}의 sizeof는 4바이트 포인터 크기다")
        _add_stack_sprintf(lines, body_start, end, add)
    return found


def _add_memset(line: str, index: int, local_arrays: set[str], add) -> None:
    """지역 배열의 sizeof는 배열 전체이므로 의심에서 뺀다."""
    for pattern in (MEMSET_POINTER, ZERO_POINTER):
        match = pattern.search(line)
        if not match:
            continue
        name = match.group(1)
        if name in local_arrays:
            continue
        add(index, f"강력 의심: {name}에 sizeof({name})만큼만 초기화하면 포인터 크기만 지워진다")


CHAR_ARRAY = re.compile(r"\b(?:unsigned\s+)?char\s+(\w+)\s*\[\s*(\d+)\s*\]")
UNBOUNDED_WRITE = re.compile(r"\b(?:sprintf|vsprintf)\s*\(")


def _add_stack_sprintf(lines: list[str], start: int, end: int, add) -> None:
    """길이를 알 수 있는 sprintf가 스택 char 배열을 넘으면 확정한다."""
    body = _mask_comments("\n".join(lines[start : end + 1]))
    arrays = {name: int(size) for name, size in CHAR_ARRAY.findall(body)}
    if not arrays:
        return
    for match in UNBOUNDED_WRITE.finditer(body):
        parsed = _split_args(body, match.end() - 1)
        if parsed is None or len(parsed[0]) < 2:
            continue
        args, _close = parsed
        name = args[0].strip()
        if name not in arrays:
            continue
        needed = _min_sprintf_bytes(args[1], args[2:])
        if needed is None or needed <= arrays[name]:
            continue
        line_index = start + body.count("\n", 0, match.start())
        add(
            line_index,
            f"강력 의심: sprintf({name})가 char[{arrays[name]}] 스택 배열에 "
            f"널 포함 최소 {needed}바이트를 써 스택을 침범한다",
        )


def _mask_comments(text: str) -> str:
    """주석만 공백으로 바꾼다. 문자열 안의 내용은 길이를 재기 위해 남긴다."""
    output: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        if text.startswith("//", index):
            while index < length and text[index] != "\n":
                output.append(" ")
                index += 1
            continue
        if text.startswith("/*", index):
            output.extend("  ")
            index += 2
            while index < length and not text.startswith("*/", index):
                output.append("\n" if text[index] == "\n" else " ")
                index += 1
            if text.startswith("*/", index):
                output.extend("  ")
                index += 2
            continue
        if text[index] == '"':
            output.append('"')
            index += 1
            while index < length:
                output.append(text[index])
                if text[index] == "\\":
                    index += 1
                    if index < length:
                        output.append(text[index])
                    index += 1
                    continue
                if text[index] == '"':
                    index += 1
                    break
                index += 1
            continue
        output.append(text[index])
        index += 1
    return "".join(output)


def _split_args(text: str, open_index: int) -> tuple[list[str], int] | None:
    """여는 괄호 위치에서 최상위 인자를 나눈다. 문자열이 닫히지 않으면 None이다."""
    depth = 0
    current: list[str] = []
    args: list[str] = []
    in_string = False
    escaped = False
    index = open_index
    while index < len(text):
        char = text[index]
        if in_string:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            current.append(char)
        elif char == "(":
            depth += 1
            if depth > 1:
                current.append(char)
        elif char == ")":
            depth -= 1
            if depth == 0:
                args.append("".join(current).strip())
                return args, index
            current.append(char)
        elif char == "," and depth == 1:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    return None


def _min_sprintf_bytes(format_arg: str, value_args: list[str]) -> int | None:
    """포맷과 리터럴 인자로 알 수 있는 최소 기록 길이. 널을 포함한다."""
    decoded = _string_literal(format_arg)
    if decoded is None:
        return None
    total = 0
    value_index = 0
    index = 0
    while index < len(decoded):
        if decoded[index] != "%":
            total += 1
            index += 1
            continue
        index += 1
        if index >= len(decoded):
            return None
        if decoded[index] == "%":
            total += 1
            index += 1
            continue
        while index < len(decoded) and decoded[index] in "-+ #0":
            index += 1
        width = 0
        if index < len(decoded) and decoded[index] == "*":
            value_index += 1
            index += 1
        else:
            width_start = index
            while index < len(decoded) and decoded[index].isdigit():
                index += 1
            if index > width_start:
                width = int(decoded[width_start:index])
        if index < len(decoded) and decoded[index] == ".":
            index += 1
            if index < len(decoded) and decoded[index] == "*":
                value_index += 1
                index += 1
            else:
                while index < len(decoded) and decoded[index].isdigit():
                    index += 1
        while index < len(decoded) and decoded[index] in "hljztL":
            index += 1
        if index >= len(decoded):
            return None
        specifier = decoded[index]
        index += 1
        if specifier == "s":
            literal = _string_literal(value_args[value_index]) if value_index < len(value_args) else None
            piece = len(literal) if literal is not None else 0
            total += max(width, piece)
            value_index += 1
        elif specifier in "diuoxXfFeEgGaAcp":
            total += max(width, 1)
            value_index += 1
        elif specifier == "n":
            value_index += 1
        else:
            return None
    return total + 1


def _string_literal(argument: str) -> str | None:
    """인자가 문자열 리터럴 하나일 때만 내용을 돌려준다."""
    text = argument.strip()
    if not text.startswith('"'):
        return None
    decoded, end = _read_string(text, 0)
    if decoded is None or text[end:].strip():
        return None
    return decoded


def _read_string(text: str, start: int) -> tuple[str | None, int]:
    if start >= len(text) or text[start] != '"':
        return None, start
    chars: list[str] = []
    index = start + 1
    simple = {"n": "\n", "r": "\r", "t": "\t", "0": "\0", "\\": "\\", '"': '"', "'": "'", "a": "\a", "b": "\b", "f": "\f", "v": "\v"}
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 1
            if index >= len(text):
                return None, index
            chars.append(simple.get(text[index], text[index]))
            index += 1
            continue
        if char == '"':
            return "".join(chars), index + 1
        chars.append(char)
        index += 1
    return None, index


def _covered(ranges: list[tuple[int, int]], index: int) -> bool:
    return any(start <= index <= end for start, end in ranges)


def _signature(lines: list[str], start: int, end: int) -> tuple[str, int]:
    """여는 중괄호 앞의 매개변수 구문과, 본문이 시작되는 줄 인덱스를 돌려준다."""
    body_start = start
    while body_start < end and "{" not in lines[body_start]:
        body_start += 1
    header = " ".join(lines[start : body_start + 1])
    open_paren = header.find("(")
    brace = header.find("{")
    if open_paren < 0:
        return "", body_start
    stop = brace if brace > open_paren else len(header)
    return header[open_paren:stop], body_start
