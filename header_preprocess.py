"""CPP가 쓰는 struct/typedef만 헤더에서 골라 슬림 .h 로 저장한다. DB 크기 최소화용 전처리."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from chunks import read_text
from symbol_index import (
    IDENT,
    PRIMITIVE,
    STRUCT_START,
    TYPEDEF_ALIAS,
    _close_brace,
    _mask_comments,
)

MAX_SELECT = 5
OUT_DIR = Path(__file__).with_name("data") / "preprocessed"
HEADER_SUFFIXES = {".h", ".hh", ".hpp", ".hxx"}
CPP_SUFFIXES = {".c", ".cc", ".cpp", ".cxx"}

# 타입 변수;  / 타입 *변수;
DECL = re.compile(
    r"\b(?:struct|class|enum|union)?\s*([A-Za-z_]\w*)\s+"
    r"(?:\*+\s*)?([A-Za-z_]\w*)\s*[;=,\[]"
)
MEMBER = re.compile(r"\b([A-Za-z_]\w*)\s*(?:\.|->)\s*[A-Za-z_]\w*")


def _extract_struct_typedef(text: str) -> list[dict[str, Any]]:
    """헤더에서 struct/typedef만 꺼낸다. 본문은 잘리지 않은 원문."""
    masked = _mask_comments(text)
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    def add(name: str, kind: str, start: int, end: int) -> None:
        key = (name, start)
        if not name or name in PRIMITIVE or key in seen:
            return
        seen.add(key)
        body = text[start:end].strip()
        deps = sorted(
            {
                token
                for token in IDENT.findall(body)
                if token not in PRIMITIVE and token != name
            }
        )
        found.append(
            {
                "symbol_name": name,
                "kind": kind,
                "line_start": text.count("\n", 0, start) + 1,
                "text": body,
                "dependencies": deps[:80],
            }
        )

    for match in STRUCT_START.finditer(masked):
        open_at = match.end() - 1
        close_at = _close_brace(masked, open_at)
        tail = masked[close_at : close_at + 80]
        alias_match = re.match(r"\s*(\w+)\s*;", tail)
        end = close_at + (alias_match.end() if alias_match else 0)
        tag = match.group(1) or ""
        if tag:
            add(tag, "struct", match.start(), end)
        if alias_match:
            add(alias_match.group(1), "struct", match.start(), end)

    for match in TYPEDEF_ALIAS.finditer(masked):
        add(match.group(1), "typedef", match.start(), match.end())
    return found


def collect_cpp_seeds(cpp_paths: list[Path]) -> dict[str, Any]:
    """CPP에서 타입·변수·멤버접근 식별자를 모은다."""
    idents: set[str] = set()
    var_types: dict[str, str] = {}
    for path in cpp_paths:
        text = read_text(path)
        for token in IDENT.findall(text):
            if token not in PRIMITIVE:
                idents.add(token)
        for match in DECL.finditer(text):
            type_name, var_name = match.group(1), match.group(2)
            if type_name in PRIMITIVE:
                continue
            idents.add(type_name)
            idents.add(var_name)
            var_types[var_name] = type_name
        for match in MEMBER.finditer(text):
            var_name = match.group(1)
            idents.add(var_name)
            if var_name in var_types:
                idents.add(var_types[var_name])
    # 변수→타입이 있으면 타입명을 시드에 반드시 포함
    for type_name in var_types.values():
        idents.add(type_name)
    return {"idents": idents, "var_types": var_types}


def _pick_symbols(
    symbols: list[dict[str, Any]],
    seeds: set[str],
    *,
    depth: int = 2,
) -> list[dict[str, Any]]:
    """시드 이름과 의존 타입을 depth까지 포함한다. 동일 본문은 한 번만."""
    by_name: dict[str, list[dict[str, Any]]] = {}
    for item in symbols:
        by_name.setdefault(item["symbol_name"], []).append(item)

    chosen: list[dict[str, Any]] = []
    seen_text: set[str] = set()
    frontier = set(seeds)
    for _ in range(max(0, depth) + 1):
        next_frontier: set[str] = set()
        for name in sorted(frontier):
            for item in by_name.get(name) or []:
                text = item["text"]
                if text in seen_text:
                    continue
                seen_text.add(text)
                chosen.append(item)
                for dep in item.get("dependencies") or []:
                    if dep in by_name:
                        next_frontier.add(dep)
        frontier = next_frontier - {item["symbol_name"] for item in chosen}
        if not frontier:
            break
    return chosen


def preprocess_headers(
    header_paths: list[Path],
    cpp_paths: list[Path],
    *,
    out_dir: Path | None = None,
    out_name: str | None = None,
) -> dict[str, Any]:
    """CPP 기준으로 헤더 struct/typedef를 추려 data/preprocessed 에 저장한다."""
    headers = [Path(p) for p in header_paths][:MAX_SELECT]
    cpps = [Path(p) for p in cpp_paths][:MAX_SELECT]
    if not headers:
        raise ValueError("헤더 파일을 1개 이상 선택하세요. (최대 5개)")
    if not cpps:
        raise ValueError("CPP 파일을 1개 이상 선택하세요. (최대 5개)")
    for path in headers:
        if path.suffix.lower() not in HEADER_SUFFIXES:
            raise ValueError(f"헤더가 아닙니다: {path.name}")
        if not path.is_file():
            raise ValueError(f"헤더 파일이 없습니다: {path}")
    for path in cpps:
        if path.suffix.lower() not in CPP_SUFFIXES:
            raise ValueError(f"CPP가 아닙니다: {path.name}")
        if not path.is_file():
            raise ValueError(f"CPP 파일이 없습니다: {path}")

    seed_info = collect_cpp_seeds(cpps)
    all_symbols: list[dict[str, Any]] = []
    per_header: dict[str, int] = {}
    for path in headers:
        items = _extract_struct_typedef(read_text(path))
        for item in items:
            item = dict(item)
            item["file_path"] = str(path.resolve())
            item["file_name"] = path.name
            all_symbols.append(item)
        per_header[path.name] = len(items)

    picked = _pick_symbols(all_symbols, seed_info["idents"], depth=2)
    destination = Path(out_dir) if out_dir else OUT_DIR
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = out_name or f"slim_{cpps[0].stem}_{stamp}.h"
    if not base.lower().endswith((".h", ".hpp", ".hh", ".hxx")):
        base += ".h"
    out_path = destination / base

    lines = [
        "/* Auto-generated slim header for DB size reduction",
        f" * cpp: {', '.join(p.name for p in cpps)}",
        f" * from: {', '.join(p.name for p in headers)}",
        f" * symbols: {len(picked)}",
        " */",
        "",
        "#pragma once",
        "",
    ]
    for item in picked:
        lines.append(f"/* {item['kind']} {item['symbol_name']} <- {item.get('file_name', '')} */")
        lines.append(item["text"])
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "out_path": str(out_path.resolve()),
        "picked_count": len(picked),
        "header_symbol_total": len(all_symbols),
        "per_header": per_header,
        "cpp_seed_count": len(seed_info["idents"]),
        "picked_names": [item["symbol_name"] for item in picked],
        "var_types": seed_info["var_types"],
    }
