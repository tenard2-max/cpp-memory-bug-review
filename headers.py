"""프로젝트 폴더에서 로컬 헤더의 구조체, typedef, 매크로를 찾아 온다."""

from __future__ import annotations

import re
from pathlib import Path

INCLUDE_LOCAL = re.compile(r'^\s*#\s*include\s*"([^"]+)"', re.MULTILINE)
DEFINE_LINE = re.compile(r"^\s*#\s*define\s+(\w+)(.*)$")
STRUCT_START = re.compile(r"\b(?:typedef\s+)?struct(?:\s+(\w+))?\s*\{")
TYPEDEF_ALIAS = re.compile(r"\btypedef\s+(?!struct\b)[^;{]*?\s+(\w+)\s*;")
IDENT = re.compile(r"\b[A-Za-z_]\w*\b")
HEADER_SUFFIXES = {".h", ".hpp", ".hh", ".hxx"}
MAX_CONTEXT_CHARS = 3500
MAX_DEFINITION_LINES = 40
PRIMITIVE_ALIAS = {
    "void",
    "char",
    "int",
    "short",
    "long",
    "float",
    "double",
    "signed",
    "unsigned",
    "bool",
    "size_t",
    "BYTE",
    "WORD",
    "DWORD",
    "BOOL",
    "UINT",
    "INT",
    "LONG",
    "CHAR",
    "TCHAR",
    "WCHAR",
}


class HeaderIndex:
    """파일 이름으로 헤더를 찾고, 한 번 파싱한 정의는 다시 읽지 않는다."""

    def __init__(self, roots: list[Path]) -> None:
        self.by_name: dict[str, Path] = {}
        self.by_relative: dict[str, Path] = {}
        self._parsed: dict[Path, dict] = {}
        for root in roots:
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in HEADER_SUFFIXES:
                    continue
                if ".git" in path.parts:
                    continue
                self.by_name.setdefault(path.name.lower(), path)
                try:
                    relative = path.relative_to(root).as_posix().lower()
                except ValueError:
                    continue
                self.by_relative.setdefault(relative, path)

    def resolve(self, include: str) -> Path | None:
        relative = include.replace("\\", "/").lstrip("./").lower()
        if relative in self.by_relative:
            return self.by_relative[relative]
        return self.by_name.get(Path(include).name.lower())

    def related_headers(self, source_text: str) -> list[Path]:
        """소스의 따옴표 include와, 그 헤더가 다시 포함하는 로컬 헤더를 두 단계까지 찾는다."""
        found: list[Path] = []
        seen: set[Path] = set()
        queue = [(name, 0) for name in INCLUDE_LOCAL.findall(source_text)]
        while queue and len(found) < 40:
            include, depth = queue.pop(0)
            path = self.resolve(include)
            if path is None or path in seen:
                continue
            seen.add(path)
            found.append(path)
            if depth >= 2:
                continue
            try:
                from chunks import read_text

                nested = read_text(path)
            except OSError:
                continue
            for child in INCLUDE_LOCAL.findall(nested):
                queue.append((child, depth + 1))
        return found

    def struct_names(self, source_text: str) -> set[str]:
        names: set[str] = set()
        for path in self.related_headers(source_text):
            parsed = self.parse(path)
            names.update(parsed["struct_names"])
        return names

    def context_blocks(self, source_text: str, chunk_text: str) -> list[dict]:
        """함수 본문에 이름이 나오는 구조체와 매크로를 블록으로 돌려준다."""
        used = set(IDENT.findall(chunk_text))
        blocks: list[dict] = []
        seen: set[str] = set()
        for path in self.related_headers(source_text):
            parsed = self.parse(path)
            for item in parsed["definitions"]:
                if item["name"] not in used or item["name"] in seen:
                    continue
                seen.add(item["name"])
                blocks.append({"name": item["name"], "text": f"// {path.name}\n{item['text']}"})
        return blocks

    def context_for(self, source_text: str, chunk_text: str) -> str:
        """함수 본문에 이름이 나오는 구조체와 매크로만 짧게 붙인다."""
        blocks = [item["text"] for item in self.context_blocks(source_text, chunk_text)]
        if not blocks:
            return ""
        text = "\n\n".join(blocks)
        if len(text) <= MAX_CONTEXT_CHARS:
            return text
        return text[:MAX_CONTEXT_CHARS] + "\n..."

    def parse(self, path: Path) -> dict:
        cached = self._parsed.get(path)
        if cached is not None:
            return cached
        try:
            from chunks import read_text

            raw = read_text(path)
        except OSError:
            raw = ""
        cleaned = _strip_comments(raw)
        definitions = _definitions(cleaned)
        parsed = {
            "struct_names": {item["name"] for item in definitions if item["kind"] == "struct"},
            "definitions": definitions,
        }
        self._parsed[path] = parsed
        return parsed


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*?$", "", text, flags=re.MULTILINE)


def _clip(text: str) -> str:
    lines = text.strip().splitlines()
    if len(lines) <= MAX_DEFINITION_LINES:
        return "\n".join(lines)
    return "\n".join(lines[:MAX_DEFINITION_LINES]) + "\n..."


def _definitions(text: str) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()

    def add(name: str, kind: str, body: str) -> None:
        if not name or name in seen:
            return
        seen.add(name)
        found.append({"name": name, "kind": kind, "text": _clip(body)})

    logical: list[str] = []
    pending = ""
    for line in text.splitlines():
        if line.rstrip().endswith("\\"):
            pending += line.rstrip()[:-1] + " "
            continue
        logical.append(pending + line)
        pending = ""
    if pending:
        logical.append(pending)

    for line in logical:
        match = DEFINE_LINE.match(line)
        if not match:
            continue
        name = match.group(1)
        add(name, "macro", line.strip())

    for match in STRUCT_START.finditer(text):
        tag = match.group(1) or ""
        open_at = match.end() - 1
        block, close_at = _brace_block(text, open_at)
        tail = text[close_at : close_at + 80]
        alias_match = re.match(r"\s*(\w+)\s*;", tail)
        alias = alias_match.group(1) if alias_match else ""
        body = text[match.start() : close_at]
        if alias:
            body += tail[: alias_match.end()]
        if tag:
            add(tag, "struct", body)
        if alias:
            add(alias, "struct", body)

    for match in TYPEDEF_ALIAS.finditer(text):
        name = match.group(1)
        if name in PRIMITIVE_ALIAS:
            continue
        statement = match.group(0)
        base_words = set(IDENT.findall(statement))
        if base_words <= (PRIMITIVE_ALIAS | {name, "typedef"}):
            continue
        add(name, "typedef", statement.strip())
    return found


def _brace_block(text: str, open_at: int) -> tuple[str, int]:
    depth = 0
    for index in range(open_at, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[open_at : index + 1], index + 1
    return text[open_at:], len(text)
