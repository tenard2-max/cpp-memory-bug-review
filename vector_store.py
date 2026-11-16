"""ChromaDB + BGE-M3 로컬 벡터 검색. 임베딩은 CPU에서 돌려 VRAM을 LLM에 양보한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).with_name("data")
CHROMA_DIR = DATA_DIR / "chroma"
SAMPLES_COLLECTION = "bug_samples"
HEADERS_COLLECTION = "header_symbols"
SOURCES_COLLECTION = "source_chunks"
# 하위 호환 별칭
COLLECTION_NAME = SAMPLES_COLLECTION
EMBED_MODEL = "BAAI/bge-m3"
META_PATH = CHROMA_DIR / "samples_index_meta.json"
HEADERS_META_PATH = CHROMA_DIR / "headers_index_meta.json"
SOURCES_META_PATH = CHROMA_DIR / "sources_index_meta.json"
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
SKIP_DIRS = {".git", "node_modules", "ipch", "debug", "release", "x64", "x86", "__pycache__", "data", "reports"}
MAX_SOURCE_FILES = 250
MAX_SOURCE_CHUNKS = 400
MAX_FUNC_LINES = 80
MAX_FILE_BYTES = 1_500_000

_CLIENT = None
_COLLECTIONS: dict[str, Any] = {}
_EMBED_FN = None
_ST_MODEL = None
_LAST_ERROR = ""


def last_error() -> str:
    return _LAST_ERROR


def is_available() -> bool:
    """chromadb / sentence-transformers 설치 여부만 본다. 모델 다운로드는 하지 않는다."""
    try:
        import chromadb  # noqa: F401
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


def _read_meta(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_meta(path: Path, payload: dict) -> None:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_meta() -> dict:
    return _read_meta(META_PATH)


def _save_meta(payload: dict) -> None:
    _write_meta(META_PATH, payload)


def status() -> dict[str, Any]:
    """샘플 인덱스 UI용 상태 요약."""
    meta = _load_meta()
    return {
        "available": is_available(),
        "persist_dir": str(CHROMA_DIR),
        "embed_model": EMBED_MODEL,
        "device": "cpu",
        "indexed_count": int(meta.get("count") or 0),
        "content_hash": str(meta.get("content_hash") or ""),
        "last_error": _LAST_ERROR,
        "ready": bool(meta.get("count")) and CHROMA_DIR.exists(),
    }


def status_all() -> dict[str, Any]:
    """샘플·헤더·소스 인덱스 상태를 한번에 본다."""
    samples = status()
    headers = _read_meta(HEADERS_META_PATH)
    sources = _read_meta(SOURCES_META_PATH)
    return {
        "available": is_available(),
        "persist_dir": str(CHROMA_DIR),
        "embed_model": EMBED_MODEL,
        "device": "cpu",
        "last_error": _LAST_ERROR,
        "samples": samples,
        "headers": {
            "indexed_count": int(headers.get("count") or 0),
            "ready": bool(headers.get("count")),
            "content_hash": str(headers.get("content_hash") or ""),
        },
        "sources": {
            "indexed_count": int(sources.get("count") or 0),
            "ready": bool(sources.get("count")),
            "root": str(sources.get("root") or ""),
            "content_hash": str(sources.get("content_hash") or ""),
        },
    }


def samples_content_hash(samples: list[dict]) -> str:
    """샘플 내용이 바뀌었는지 비교할 해시."""
    normalized = [
        {
            "id": item.get("id"),
            "category": item.get("category"),
            "keywords": item.get("keywords"),
            "bad_code": item.get("bad_code"),
            "good_code": item.get("good_code"),
            "explanation": item.get("explanation"),
            "is_false_positive": item.get("is_false_positive"),
        }
        for item in samples
    ]
    blob = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _embedding_function():
    """BGE-M3를 CPU에 올린다. 첫 호출 시 모델 다운로드가 있을 수 있다."""
    global _EMBED_FN, _LAST_ERROR
    if _EMBED_FN is not None:
        return _EMBED_FN
    try:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

        _EMBED_FN = SentenceTransformerEmbeddingFunction(
            model_name=EMBED_MODEL,
            device="cpu",
            normalize_embeddings=True,
        )
        _LAST_ERROR = ""
        return _EMBED_FN
    except Exception as error:  # noqa: BLE001
        _LAST_ERROR = f"BGE-M3 임베딩 초기화 실패: {error}"
        raise RuntimeError(_LAST_ERROR) from error


def _client():
    global _CLIENT, _LAST_ERROR
    if _CLIENT is not None:
        return _CLIENT
    import chromadb
    from chromadb.config import Settings

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    _CLIENT = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    _LAST_ERROR = ""
    return _CLIENT


def _get_collection(name: str, *, create: bool = True):
    global _LAST_ERROR
    if name in _COLLECTIONS:
        return _COLLECTIONS[name]
    try:
        collection = _client().get_or_create_collection(
            name=name,
            embedding_function=_embedding_function(),
            metadata={"hnsw:space": "cosine"},
        )
        _COLLECTIONS[name] = collection
        _LAST_ERROR = ""
        return collection
    except Exception as error:  # noqa: BLE001
        _LAST_ERROR = f"Chroma 컬렉션({name}) 초기화 실패: {error}"
        if not create:
            return None
        raise RuntimeError(_LAST_ERROR) from error


def _collection(create: bool = True):
    """샘플 컬렉션(하위 호환)."""
    return _get_collection(SAMPLES_COLLECTION, create=create)


def reset_client() -> None:
    """캐시된 클라이언트·컬렉션 핸들을 비운다. 디스크 데이터는 유지."""
    global _CLIENT
    _CLIENT = None
    _COLLECTIONS.clear()


def _recreate_collection(name: str):
    reset_client()
    client = _client()
    try:
        client.delete_collection(name)
    except Exception:
        pass
    return _get_collection(name, create=True)


def sample_document(sample: dict) -> str:
    """검색·임베딩에 넣을 텍스트."""
    keywords = ", ".join(sample.get("keywords") or [])
    kind = "오탐예외" if sample.get("is_false_positive") else "버그사례"
    return "\n".join(
        [
            f"category: {sample.get('category') or ''}",
            f"kind: {kind}",
            f"keywords: {keywords}",
            "bad_code:",
            str(sample.get("bad_code") or ""),
            "good_code:",
            str(sample.get("good_code") or ""),
            "explanation:",
            str(sample.get("explanation") or ""),
        ]
    )


def rebuild_sample_index(samples: list[dict]) -> dict[str, Any]:
    """bug_samples 전체를 Chroma에 다시 넣는다."""
    global _LAST_ERROR
    if not is_available():
        _LAST_ERROR = "chromadb 또는 sentence-transformers 가 설치되어 있지 않습니다."
        raise RuntimeError(_LAST_ERROR)
    collection = _recreate_collection(SAMPLES_COLLECTION)
    if not samples:
        _save_meta({"count": 0, "content_hash": samples_content_hash([]), "embed_model": EMBED_MODEL})
        return status()
    ids = [f"sample-{item['id']}" for item in samples]
    documents = [sample_document(item) for item in samples]
    metadatas = [
        {
            "sample_id": int(item["id"]),
            "category": str(item.get("category") or "")[:200],
            "is_false_positive": bool(item.get("is_false_positive")),
        }
        for item in samples
    ]
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    _save_meta(
        {
            "count": len(samples),
            "content_hash": samples_content_hash(samples),
            "embed_model": EMBED_MODEL,
            "device": "cpu",
        }
    )
    _LAST_ERROR = ""
    return status()


def ensure_sample_index(samples: list[dict], *, force: bool = False) -> dict[str, Any]:
    """해시가 같으면 재구축을 건너뛴다."""
    meta = _load_meta()
    digest = samples_content_hash(samples)
    if (
        not force
        and meta.get("content_hash") == digest
        and int(meta.get("count") or 0) == len(samples)
        and CHROMA_DIR.exists()
    ):
        return status()
    return rebuild_sample_index(samples)


def query_similar_samples(query_text: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """쿼리와 비슷한 샘플 id·거리를 반환한다. 실패 시 빈 목록."""
    global _LAST_ERROR
    text = (query_text or "").strip()
    if not text or not is_available():
        return []
    try:
        collection = _get_collection(SAMPLES_COLLECTION, create=True)
        if collection.count() <= 0:
            return []
        result = collection.query(
            query_texts=[text],
            n_results=min(limit, max(1, collection.count())),
            include=["distances", "metadatas", "documents"],
        )
    except Exception as error:  # noqa: BLE001
        _LAST_ERROR = f"벡터 검색 실패: {error}"
        return []
    return _rows_from_query(result, id_field="sample_id")


def _rows_from_query(result: dict, *, id_field: str | None = None) -> list[dict[str, Any]]:
    ids = (result.get("ids") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    rows: list[dict[str, Any]] = []
    for index, item_id in enumerate(ids):
        meta = metadatas[index] if index < len(metadatas) else {}
        distance = distances[index] if index < len(distances) else None
        score = 0.0 if distance is None else max(0.0, 1.0 - float(distance))
        row = {
            "chroma_id": item_id,
            "distance": distance,
            "score": score,
            "document": documents[index] if index < len(documents) else "",
            "metadata": meta,
        }
        if id_field and meta.get(id_field) is not None:
            try:
                row["id"] = int(meta[id_field])
            except (TypeError, ValueError):
                row["id"] = meta[id_field]
        rows.append(row)
    global _LAST_ERROR
    _LAST_ERROR = ""
    return rows


def rebuild_header_symbol_index(symbols: list[dict] | None = None) -> dict[str, Any]:
    """SQLite 헤더 심볼(또는 전달 목록)을 Chroma header_symbols 에 넣는다."""
    global _LAST_ERROR
    if not is_available():
        _LAST_ERROR = "chromadb 또는 sentence-transformers 가 설치되어 있지 않습니다."
        raise RuntimeError(_LAST_ERROR)
    if symbols is None:
        symbols = _load_symbols_from_sqlite()
    collection = _recreate_collection(HEADERS_COLLECTION)
    if not symbols:
        _write_meta(
            HEADERS_META_PATH,
            {"count": 0, "content_hash": "", "embed_model": EMBED_MODEL, "device": "cpu"},
        )
        return status_all()["headers"]

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []
    for index, item in enumerate(symbols):
        name = str(item.get("symbol_name") or "")
        path = str(item.get("file_path") or "")
        line_start = int(item.get("line_start") or 0)
        text = str(item.get("text") or "")
        kind = str(item.get("kind") or "")
        doc_id = hashlib.sha1(f"{path}|{name}|{line_start}".encode("utf-8")).hexdigest()[:24]
        ids.append(f"hdr-{doc_id}")
        documents.append(
            f"symbol: {name}\nkind: {kind}\nfile: {Path(path).name}\n{text}"
        )
        metadatas.append(
            {
                "symbol_name": name[:200],
                "kind": kind[:80],
                "file_path": path[:500],
                "line_start": line_start,
                "line_end": int(item.get("line_end") or line_start),
            }
        )
        if len(ids) >= 64:
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            ids, documents, metadatas = [], [], []
    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    digest = hashlib.sha256(
        json.dumps(
            [(s.get("symbol_name"), s.get("file_path"), s.get("line_start"), s.get("text")) for s in symbols],
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    payload = {
        "count": len(symbols),
        "content_hash": digest,
        "embed_model": EMBED_MODEL,
        "device": "cpu",
    }
    _write_meta(HEADERS_META_PATH, payload)
    _LAST_ERROR = ""
    return payload


def _load_symbols_from_sqlite() -> list[dict]:
    db_path = DATA_DIR / "symbol_index.sqlite"
    if not db_path.is_file():
        return []
    import sqlite3

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT symbol_name, kind, file_path, line_start, line_end, text FROM symbols"
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def ensure_header_symbol_index(*, force: bool = False) -> dict[str, Any]:
    symbols = _load_symbols_from_sqlite()
    meta = _read_meta(HEADERS_META_PATH)
    digest = hashlib.sha256(
        json.dumps(
            [(s.get("symbol_name"), s.get("file_path"), s.get("line_start"), s.get("text")) for s in symbols],
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    if (
        not force
        and meta.get("content_hash") == digest
        and int(meta.get("count") or 0) == len(symbols)
    ):
        return {"count": int(meta.get("count") or 0), "content_hash": digest, "skipped": True}
    return rebuild_header_symbol_index(symbols)


def query_similar_headers(query_text: str, *, limit: int = 8) -> list[dict[str, Any]]:
    """헤더 심볼 벡터 검색."""
    global _LAST_ERROR
    text = (query_text or "").strip()
    if not text or not is_available():
        return []
    try:
        collection = _get_collection(HEADERS_COLLECTION, create=True)
        if collection.count() <= 0:
            return []
        result = collection.query(
            query_texts=[text],
            n_results=min(limit, max(1, collection.count())),
            include=["distances", "metadatas", "documents"],
        )
    except Exception as error:  # noqa: BLE001
        _LAST_ERROR = f"헤더 벡터 검색 실패: {error}"
        return []
    rows = []
    for item in _rows_from_query(result):
        meta = item.get("metadata") or {}
        rows.append(
            {
                "symbol_name": meta.get("symbol_name") or "",
                "kind": meta.get("kind") or "",
                "file_path": meta.get("file_path") or "",
                "line_start": int(meta.get("line_start") or 0),
                "line_end": int(meta.get("line_end") or 0),
                "text": _strip_header_doc(item.get("document") or ""),
                "score": item.get("score") or 0.0,
                "source": "vector",
            }
        )
    return rows


def _strip_header_doc(document: str) -> str:
    lines = document.splitlines()
    # symbol/kind/file 헤더 3줄 제거
    if len(lines) >= 3 and lines[0].startswith("symbol:"):
        return "\n".join(lines[3:]).strip()
    return document.strip()


def _source_root_hash(root: Path, files: list[Path]) -> str:
    parts = [str(root.resolve())]
    for path in files:
        try:
            stat = path.stat()
            parts.append(f"{path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}")
        except OSError:
            parts.append(str(path))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def list_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.is_dir():
        return files
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        if any(part.lower() in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
        if len(files) >= MAX_SOURCE_FILES:
            break
    return sorted(files)


def rebuild_source_chunk_index(root: Path | str) -> dict[str, Any]:
    """프로젝트 소스 함수 조각을 Chroma source_chunks 에 넣는다."""
    global _LAST_ERROR
    if not is_available():
        _LAST_ERROR = "chromadb 또는 sentence-transformers 가 설치되어 있지 않습니다."
        raise RuntimeError(_LAST_ERROR)
    root_path = Path(root)
    if not root_path.is_dir():
        raise RuntimeError(f"소스 루트가 없습니다: {root_path}")
    from chunks import function_name, function_ranges, read_lines

    files = list_source_files(root_path)
    collection = _recreate_collection(SOURCES_COLLECTION)
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []
    total = 0
    for path in files:
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            lines = read_lines(path)
        except OSError:
            continue
        for start, end in function_ranges(lines):
            if total >= MAX_SOURCE_CHUNKS:
                break
            clipped_end = min(end, start + MAX_FUNC_LINES - 1)
            body = "\n".join(lines[start : clipped_end + 1])
            name = function_name(lines, start, end) or "(unnamed)"
            resolved = str(path.resolve())
            doc_id = hashlib.sha1(f"{resolved}|{start}|{end}".encode("utf-8")).hexdigest()[:24]
            ids.append(f"src-{doc_id}")
            documents.append(
                f"file: {path.name}\nfunction: {name}\nrange: {start + 1}-{end + 1}\n{body}"
            )
            metadatas.append(
                {
                    "file_path": resolved[:500],
                    "file_name": path.name[:200],
                    "function_name": name[:200],
                    "line_start": start + 1,
                    "line_end": end + 1,
                }
            )
            total += 1
            if len(ids) >= 48:
                collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
                ids, documents, metadatas = [], [], []
        if total >= MAX_SOURCE_CHUNKS:
            break
    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    payload = {
        "count": total,
        "root": str(root_path.resolve()),
        "content_hash": _source_root_hash(root_path, files),
        "embed_model": EMBED_MODEL,
        "device": "cpu",
        "files": len(files),
    }
    _write_meta(SOURCES_META_PATH, payload)
    _LAST_ERROR = ""
    return payload


def ensure_source_chunk_index(root: Path | str, *, force: bool = False) -> dict[str, Any]:
    root_path = Path(root)
    files = list_source_files(root_path)
    digest = _source_root_hash(root_path, files)
    meta = _read_meta(SOURCES_META_PATH)
    if (
        not force
        and meta.get("content_hash") == digest
        and str(meta.get("root") or "") == str(root_path.resolve())
        and int(meta.get("count") or 0) > 0
    ):
        return {**meta, "skipped": True}
    return rebuild_source_chunk_index(root_path)


def query_similar_sources(
    query_text: str,
    *,
    limit: int = 3,
    exclude_path: str | None = None,
) -> list[dict[str, Any]]:
    """프로젝트 소스 함수 조각 벡터 검색."""
    global _LAST_ERROR
    text = (query_text or "").strip()
    if not text or not is_available():
        return []
    try:
        collection = _get_collection(SOURCES_COLLECTION, create=True)
        if collection.count() <= 0:
            return []
        result = collection.query(
            query_texts=[text],
            n_results=min(max(limit * 3, limit), max(1, collection.count())),
            include=["distances", "metadatas", "documents"],
        )
    except Exception as error:  # noqa: BLE001
        _LAST_ERROR = f"소스 벡터 검색 실패: {error}"
        return []
    exclude = str(Path(exclude_path).resolve()) if exclude_path else ""
    rows: list[dict[str, Any]] = []
    for item in _rows_from_query(result):
        meta = item.get("metadata") or {}
        file_path = str(meta.get("file_path") or "")
        if exclude and file_path == exclude:
            continue
        document = item.get("document") or ""
        body = document
        if "\n" in document:
            # file/function/range 헤더 다음이 본문
            parts = document.split("\n", 3)
            body = parts[3] if len(parts) == 4 else document
        rows.append(
            {
                "file_path": file_path,
                "file_name": meta.get("file_name") or Path(file_path).name,
                "function_name": meta.get("function_name") or "",
                "line_start": int(meta.get("line_start") or 0),
                "line_end": int(meta.get("line_end") or 0),
                "text": body.strip(),
                "score": item.get("score") or 0.0,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _sentence_model():
    """순위 계산용 SentenceTransformer(CPU). Chroma 임베딩과 동일 모델명을 쓴다."""
    global _ST_MODEL, _LAST_ERROR
    if _ST_MODEL is not None:
        return _ST_MODEL
    try:
        from sentence_transformers import SentenceTransformer

        _ST_MODEL = SentenceTransformer(EMBED_MODEL, device="cpu")
        _LAST_ERROR = ""
        return _ST_MODEL
    except Exception as error:  # noqa: BLE001
        _LAST_ERROR = f"BGE-M3 순위 모델 로드 실패: {error}"
        raise RuntimeError(_LAST_ERROR) from error


def rank_by_similarity(query: str, items: list[dict], *, text_key: str = "text") -> list[dict]:
    """이미 고른 후보를 BGE-M3 유사도로 다시 정렬한다. 실패 시 원본 순서를 유지한다."""
    if not items or not (query or "").strip() or not is_available():
        return items
    try:
        model = _sentence_model()
        documents = [str(item.get(text_key) or "") for item in items]
        query_vec = model.encode([query], normalize_embeddings=True)
        doc_vecs = model.encode(documents, normalize_embeddings=True)
        scores = (query_vec @ doc_vecs.T)[0]
        order = sorted(range(len(items)), key=lambda index: float(scores[index]), reverse=True)
        ranked: list[dict] = []
        for index in order:
            row = dict(items[index])
            row["_vector_score"] = float(scores[index])
            ranked.append(row)
        return ranked
    except Exception as error:  # noqa: BLE001
        global _LAST_ERROR
        _LAST_ERROR = f"유사도 순위 실패: {error}"
        return items
