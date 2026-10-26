"""헤더 심볼을 SQLite에 넣고, 함수에서 쓰는 이름만 정확히 찾아 온다."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("config") / "index.yaml"
DB_PATH = Path(__file__).with_name("data") / "symbol_index.sqlite"
HEADER_SUFFIXES = {".h", ".hpp", ".hh", ".hxx"}
SKIP_DIRS = {".git", "node_modules", "ipch", "debug", "release", "x64", "x86"}
IDENT = re.compile(r"\b[A-Za-z_]\w*\b")
DEFINE_LINE = re.compile(r"^\s*#\s*define\s+(\w+)\b(.*)$")
STRUCT_START = re.compile(r"\b(?:typedef\s+)?(?:struct|class|union|enum)(?:\s+(\w+))?\s*\{")
TYPEDEF_ALIAS = re.compile(r"\btypedef\s+(?!struct\b|class\b|union\b|enum\b)[^;{]*?\s+(\w+)\s*;")
FUNC_DECL = re.compile(r"^[\w:\s\*&<>,~]+?\s+(\w+)\s*\([^;{}]*\)\s*;")
EXTERN_DECL = re.compile(r"^\s*extern\s+.+?\s+(\w+)\s*;")
PRIMITIVE = {
    "void", "char", "int", "short", "long", "float", "double", "signed", "unsigned",
    "bool", "size_t", "const", "static", "inline", "typedef", "struct", "class",
    "union", "enum", "return", "if", "else", "for", "while", "BYTE", "WORD",
    "DWORD", "BOOL", "UINT", "INT", "LONG", "CHAR",
}
MAX_FILE_BYTES = 2_000_000
MAX_SYMBOL_LINES = 80


def load_config(path: Path = CONFIG_PATH) -> dict:
    """index.yaml에서 헤더 루트와 토큰 예산만 읽는다."""
    config = {"header_roots": [], "include_inline_bodies": False, "context_token_budget": 1500}
    if not path.exists():
        return config
    section = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith("header_roots:"):
            section = "roots"
            continue
        if section == "roots" and line.strip().startswith("-"):
            value = line.strip()[1:].strip().strip('"').strip("'")
            if value:
                config["header_roots"].append(value)
            continue
        section = ""
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        lowered = value.lower()
        if key == "include_inline_bodies":
            config[key] = lowered in {"true", "yes", "1"}
        elif key == "context_token_budget" and value.isdigit():
            config[key] = int(value)
    return config


def save_header_roots(roots: list[str], path: Path = CONFIG_PATH, budget: int | None = None) -> None:
    """화면에서 확인한 헤더 루트와 컨텍스트 토큰 예산을 설정 파일에 다시 적는다."""
    config = load_config(path)
    if budget is not None:
        config["context_token_budget"] = min(4096, max(1500, int(budget)))
    lines = [
        "# 레거시 헤더 루트. 프로그램은 이 목록만 인덱싱한다.",
        "header_roots:",
    ]
    for root in roots:
        cleaned = root.strip()
        if cleaned:
            lines.append(f"  - {cleaned}")
    lines.append(f"include_inline_bodies: {'true' if config['include_inline_bodies'] else 'false'}")
    lines.append(f"context_token_budget: {config['context_token_budget']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            sha256 TEXT NOT NULL,
            skipped TEXT
        );
        CREATE TABLE IF NOT EXISTS symbols (
            symbol_name TEXT NOT NULL,
            kind TEXT NOT NULL,
            file_path TEXT NOT NULL,
            line_start INTEGER NOT NULL,
            line_end INTEGER NOT NULL,
            text TEXT NOT NULL,
            dependencies TEXT NOT NULL,
            PRIMARY KEY (symbol_name, file_path, line_start)
        );
        CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(symbol_name);
        """
    )
    return connection


def index_status() -> dict:
    """저장된 심볼 수와 마지막 경고를 돌려준다. DB가 없으면 빈 상태다."""
    if not DB_PATH.exists():
        return {"files": 0, "symbols": 0, "skipped": [], "roots": load_config()["header_roots"]}
    with _connect() as connection:
        files = connection.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        symbols = connection.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        skipped = [
            {"path": row["path"], "message": row["skipped"]}
            for row in connection.execute("SELECT path, skipped FROM files WHERE skipped != '' ORDER BY path")
        ]
    return {"files": files, "symbols": symbols, "skipped": skipped, "roots": load_config()["header_roots"]}


def build_index(full: bool = False) -> dict:
    """설정에 적힌 헤더 루트를 인덱싱한다. full이 아니면 해시가 같은 파일은 건너뛴다."""
    config = load_config()
    roots = [Path(item) for item in config["header_roots"]]
    seen_paths: set[str] = set()
    missing_roots: list[str] = []
    updated = 0
    unchanged = 0
    with _connect() as connection:
        for root in roots:
            if not root.is_dir():
                missing_roots.append(str(root))
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in HEADER_SUFFIXES:
                    continue
                if any(part.lower() in SKIP_DIRS for part in path.parts):
                    continue
                resolved = str(path.resolve())
                seen_paths.add(resolved)
                try:
                    if path.stat().st_size > MAX_FILE_BYTES:
                        _store_skip(connection, resolved, "파일이 2MB를 넘어 건너뜁니다.")
                        continue
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    current = connection.execute("SELECT sha256 FROM files WHERE path = ?", (resolved,)).fetchone()
                    if not full and current is not None and current["sha256"] == digest:
                        unchanged += 1
                        continue
                    from chunks import read_text

                    symbols = extract_symbols(read_text(path), config["include_inline_bodies"])
                except Exception as error:
                    _store_skip(connection, resolved, f"파싱 불가로 건너뜁니다: {error}")
                    continue
                connection.execute("DELETE FROM symbols WHERE file_path = ?", (resolved,))
                connection.executemany(
                    """
                    INSERT INTO symbols
                    (symbol_name, kind, file_path, line_start, line_end, text, dependencies)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            item["symbol_name"],
                            item["kind"],
                            resolved,
                            item["line_start"],
                            item["line_end"],
                            item["text"],
                            " ".join(item["dependencies"]),
                        )
                        for item in symbols
                    ],
                )
                connection.execute(
                    "INSERT INTO files(path, sha256, skipped) VALUES (?, ?, '') "
                    "ON CONFLICT(path) DO UPDATE SET sha256 = excluded.sha256, skipped = ''",
                    (resolved, digest),
                )
                updated += 1
        if seen_paths:
            placeholders = ",".join("?" for _ in seen_paths)
            connection.execute(f"DELETE FROM symbols WHERE file_path NOT IN ({placeholders})", tuple(seen_paths))
            connection.execute(f"DELETE FROM files WHERE path NOT IN ({placeholders})", tuple(seen_paths))
        connection.commit()
    status = index_status()
    status["updated"] = updated
    status["unchanged"] = unchanged
    status["missing_roots"] = missing_roots
    return status


def _store_skip(connection: sqlite3.Connection, path: str, message: str) -> None:
    connection.execute("DELETE FROM symbols WHERE file_path = ?", (path,))
    connection.execute(
        "INSERT INTO files(path, sha256, skipped) VALUES (?, '', ?) "
        "ON CONFLICT(path) DO UPDATE SET skipped = excluded.skipped",
        (path, message),
    )


def extract_symbols(text: str, include_inline_bodies: bool) -> list[dict]:
    """한 헤더에서 매크로, 타입, 선언을 심볼 단위로 꺼낸다."""
    masked = _mask_comments(text)
    found: list[dict] = []
    seen: set[tuple[str, int]] = set()

    def add(name: str, kind: str, start: int, end: int, body: str) -> None:
        key = (name, start)
        if not name or name in PRIMITIVE or key in seen:
            return
        seen.add(key)
        clipped = _clip_lines(body)
        deps = sorted(
            {
                token
                for token in IDENT.findall(clipped)
                if token not in PRIMITIVE and token != name
            }
        )
        found.append(
            {
                "symbol_name": name,
                "kind": kind,
                "line_start": text.count("\n", 0, start) + 1,
                "line_end": text.count("\n", 0, end) + 1,
                "text": clipped,
                "dependencies": deps[:40],
            }
        )

    logical_start = 0
    pending_start = None
    pending = ""
    for match in re.finditer(r".*(?:\n|$)", text):
        line = match.group(0)
        stripped = line.rstrip("\n")
        if pending_start is None:
            pending_start = match.start()
        if stripped.endswith("\\"):
            pending += stripped[:-1] + " "
            continue
        whole = pending + stripped
        define = DEFINE_LINE.match(whole)
        if define:
            add(define.group(1), "macro", pending_start, match.end(), whole.strip())
        pending = ""
        pending_start = None
        logical_start = match.end()
    del logical_start

    for match in STRUCT_START.finditer(masked):
        open_at = match.end() - 1
        close_at = _close_brace(masked, open_at)
        tail = masked[close_at : close_at + 80]
        alias_match = re.match(r"\s*(\w+)\s*;", tail)
        end = close_at + (alias_match.end() if alias_match else 0)
        body = text[match.start() : end]
        tag = match.group(1) or ""
        if tag:
            add(tag, "struct", match.start(), end, body)
        if alias_match:
            add(alias_match.group(1), "struct", match.start(), end, body)

    for match in TYPEDEF_ALIAS.finditer(masked):
        add(match.group(1), "typedef", match.start(), match.end(), text[match.start() : match.end()].strip())

    for line_match in re.finditer(r".*(?:\n|$)", masked):
        line = line_match.group(0).strip()
        if not line or line.startswith("#"):
            continue
        extern = EXTERN_DECL.match(line)
        if extern:
            add(extern.group(1), "global_decl", line_match.start(), line_match.end(), line)
            continue
        declaration = FUNC_DECL.match(line)
        if declaration:
            add(declaration.group(1), "function_decl", line_match.start(), line_match.end(), line)
            continue
        if include_inline_bodies:
            continue
    return found


def select_context(chunk_text: str, extra_blocks: list[dict] | None = None) -> dict:
    """인덱스에서 쓰는 심볼을 고르고, 예산이 남으면 정규식 결과를 뒤에 붙인다."""
    budget = load_config()["context_token_budget"]
    names = [token for token in IDENT.findall(chunk_text) if token not in PRIMITIVE]
    frequency: dict[str, int] = {}
    for name in names:
        frequency[name] = frequency.get(name, 0) + 1
    chosen: list[dict] = []
    seen: set[tuple[str, str, int]] = set()
    used_index = DB_PATH.exists()
    if used_index and frequency:
        with _connect() as connection:
            _collect_exact(connection, frequency, chosen, seen, depth=0)
    ranked = sorted(chosen, key=lambda item: (item["depth"], -item["hits"], item["symbol_name"]))
    kept: list[dict] = []
    omitted: list[str] = []
    used_tokens = 0
    covered: set[str] = set()
    for item in ranked:
        tokens = estimate_tokens(item["text"])
        label = f"{item['symbol_name']} ({item['kind']}, exact)"
        if used_tokens + tokens > budget:
            omitted.append(label)
            continue
        used_tokens += tokens
        kept.append(item)
        covered.add(item["symbol_name"])
    fallback_blocks = []
    for block in extra_blocks or []:
        if block["name"] in covered:
            continue
        tokens = estimate_tokens(block["text"])
        label = f"{block['name']} (regex)"
        if used_tokens + tokens > budget:
            omitted.append(label)
            continue
        used_tokens += tokens
        covered.add(block["name"])
        fallback_blocks.append(block)
    parts = []
    included = []
    for item in kept:
        file_name = Path(item["file_path"]).name
        parts.append(f"// [{file_name}:{item['line_start']}] {item['symbol_name']}\n{item['text']}")
        included.append(f"{item['symbol_name']} {file_name}:{item['line_start']} exact")
    for block in fallback_blocks:
        parts.append(block["text"])
        included.append(f"{block['name']} regex")
    return {
        "text": "\n\n".join(parts),
        "included": included,
        "omitted": omitted,
        "used_index": used_index,
    }


def _collect_exact(connection, frequency, chosen, seen, depth: int) -> None:
    if depth > 2 or not frequency:
        return
    names = list(frequency)
    placeholders = ",".join("?" for _ in names)
    rows = connection.execute(
        f"SELECT symbol_name, kind, file_path, line_start, line_end, text, dependencies "
        f"FROM symbols WHERE symbol_name IN ({placeholders})",
        names,
    ).fetchall()
    next_names: dict[str, int] = {}
    for row in rows:
        key = (row["symbol_name"], row["file_path"], row["line_start"])
        if key in seen:
            continue
        seen.add(key)
        chosen.append(
            {
                "symbol_name": row["symbol_name"],
                "kind": row["kind"],
                "file_path": row["file_path"],
                "line_start": row["line_start"],
                "text": row["text"],
                "depth": depth,
                "hits": frequency.get(row["symbol_name"], 1),
            }
        )
        for dependency in row["dependencies"].split():
            if dependency not in PRIMITIVE:
                next_names[dependency] = next_names.get(dependency, 0) + 1
    if next_names:
        _collect_exact(connection, next_names, chosen, seen, depth + 1)


def _mask_comments(text: str) -> str:
    def block(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    masked = re.sub(r"/\*.*?\*/", block, text, flags=re.DOTALL)
    return re.sub(r"//.*?$", lambda match: " " * len(match.group(0)), masked, flags=re.MULTILINE)


def _close_brace(text: str, open_at: int) -> int:
    depth = 0
    for index in range(open_at, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    return len(text)


def _clip_lines(text: str) -> str:
    lines = text.strip().splitlines()
    if len(lines) <= MAX_SYMBOL_LINES:
        return "\n".join(lines)
    return "\n".join(lines[:MAX_SYMBOL_LINES]) + "\n..."
