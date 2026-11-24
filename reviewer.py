"""로컬 Ollama 모델에 잘린 C++ 메모리 조각만 넘긴다."""

from __future__ import annotations

import json
import queue
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from analyzer import run_cppcheck
from chunks import build_chunks, function_name_at, load_memory_rules, read_lines, source_snippet
from prompts import (
    CROSS_SYSTEM,
    OUTPUT_SCHEMA,
    POLISH_SYSTEM,
    build_cross_prompt,
    build_polish_prompt,
    build_system_prompt,
    build_user_prompt,
)
from samples_db import format_samples, select_samples
from whitelist import format_whitelist, load_whitelist

DEFAULT_MODEL = "qwen2.5-coder:7b"
QWEN3_MODEL = "qwen3:14b"
DEFAULT_DEEPSEEK = "qwen2.5-coder:7b"
DEFAULT_LLAMA = "llama3.1:8b"
POLISH_MODELS = (
    "llama3.1:8b",
    "llama3.2:3b",
    "llama3.2:1b",
    "qwen2.5-coder:7b",
)
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_OPTIONS = {"temperature": 0.0, "num_ctx": 4096, "num_thread": 8, "num_predict": 512}
PREDICT_CHOICES = [512, 1024, 2048, 4096, 5120, 6144, 7168, 8190]
# FAST=/no_think 기본. AUTO는 의심 시에만 Thinking.
THINK_MODES = ("FAST", "AUTO", "DEEP")
DEFAULT_THINK_MODE = "FAST"
SOURCE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
BUG_TYPES = set(OUTPUT_SCHEMA["properties"]["findings"]["items"]["properties"]["bug_type"]["enum"])
CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}
MAX_FILES = 30
RULES_PATH = Path(__file__).with_name("memory_rules.txt")
THINK_LOG_DIR = Path(__file__).with_name("logs") / "think"
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


class ReviewError(RuntimeError):
    """검토 요청을 모델까지 보내지 못했을 때 사용한다."""


def is_qwen3_model(model: str) -> bool:
    """Qwen3 계열이면 Hybrid Thinking 옵션을 적용한다."""
    name = (model or "").strip().lower()
    return name.startswith("qwen3:") or name.startswith("qwen3-")


def normalize_think_mode(mode: str | None) -> str:
    text = str(mode or DEFAULT_THINK_MODE).strip().upper()
    return text if text in THINK_MODES else DEFAULT_THINK_MODE


def qwen3_call_preset(stage: str) -> dict:
    """FAST=/no_think, DEEP=Thinking 프리셋. num_ctx는 하드웨어 프로필 값을 쓴다."""
    if stage == "DEEP":
        return {
            "think": True,
            "temperature": 0.6,
            "top_p": 0.95,
            "stage": "DEEP_TRACE",
        }
    return {
        "think": False,
        "temperature": 0.1,
        "top_p": 0.8,
        "stage": "FAST_SCAN",
    }


def strip_think_blocks(text: str) -> tuple[str, str]:
    """응답에서 <think> 블록을 분리한다. (본문, think 텍스트)."""
    raw = text or ""
    thoughts = [block.strip() for block in _THINK_BLOCK.findall(raw) if block.strip()]
    cleaned = _THINK_BLOCK.sub("", raw).strip()
    return cleaned, "\n\n".join(thoughts)


def save_think_log(chunk: dict, stage: str, think_text: str) -> str:
    """심층 추론 혼잣말을 logs/think 에 남긴다."""
    if not think_text.strip():
        return ""
    THINK_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    safe_file = re.sub(r"[^\w.-]+", "_", str(chunk.get("file") or "chunk"))[:80]
    path = THINK_LOG_DIR / f"{stamp}_{safe_file}_{chunk.get('start', 0)}_{stage}.log"
    path.write_text(
        (
            f"file={chunk.get('file')}\n"
            f"function={chunk.get('function_name')}\n"
            f"range={chunk.get('start')}-{chunk.get('end')}\n"
            f"stage={stage}\n\n"
            f"{think_text.strip()}\n"
        ),
        encoding="utf-8",
        errors="replace",
    )
    return str(path)


def is_source(path: Path) -> bool:
    return path.suffix.lower() in SOURCE_EXTENSIONS


def list_sources(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(item for item in path.rglob("*") if item.is_file() and is_source(item))
        elif path.is_file() and is_source(path):
            files.append(path)
    files = sorted(set(files))[:MAX_FILES]
    if not files:
        raise ReviewError("C 또는 C++ 소스 파일이 없습니다.")
    return files


def extract_json(text: str) -> dict:
    stripped, _think = strip_think_blocks(text.strip())
    if stripped.startswith("```"):
        lines = stripped.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    start = stripped.find("{")
    if start < 0:
        raise ReviewError("모델 응답에서 JSON을 찾지 못했습니다.")
    body = stripped[start:]
    repaired = False
    try:
        end = body.rfind("}")
        data = json.loads(body if end < 0 else body[: end + 1])
    except json.JSONDecodeError:
        data = _salvage_json(body)
        repaired = True
        if data is None:
            raise ReviewError("모델 응답 JSON이 잘려 완료된 항목을 읽지 못했습니다.")
    if not isinstance(data, dict):
        raise ReviewError("모델 응답이 JSON 객체가 아닙니다.")
    result = normalize_result(data)
    result["json_repaired"] = repaired
    return result


def _salvage_json(body: str) -> dict | None:
    """토큰 제한으로 뒤에서 잘린 JSON에서, 닫힌 findings 항목만 꺼낸다."""
    marker = body.find("[")
    if marker < 0:
        return None
    items: list[dict] = []
    index = marker + 1
    decoder = json.JSONDecoder()
    while index < len(body):
        while index < len(body) and body[index] in " \n\r\t,":
            index += 1
        if index >= len(body) or body[index] == "]":
            break
        try:
            item, end = decoder.raw_decode(body, index)
        except json.JSONDecodeError:
            break
        if isinstance(item, dict):
            items.append(item)
        index = end
    if not items:
        return None
    return {"rejected": False, "reject_reason": "", "findings": items}


def normalize_result(data: dict) -> dict:
    findings = []
    for item in data.get("findings") or []:
        if not isinstance(item, dict):
            continue
        bug_type = str(item.get("bug_type", "")).strip()
        if bug_type not in BUG_TYPES:
            continue
        try:
            line = int(item.get("line", 0))
        except (TypeError, ValueError):
            line = 0
        confidence = str(item.get("confidence", "low")).strip().lower()
        if confidence not in CONFIDENCE_ORDER:
            confidence = "low"
        findings.append(
            {
                "file": str(item.get("file", "")),
                "line": line,
                "function_name": str(item.get("function_name", "")).strip(),
                "bug_type": bug_type,
                "summary": str(item.get("summary", "")).strip(),
                "evidence": str(item.get("evidence", "")).strip(),
                "before_code": str(item.get("before_code", "")).strip(),
                "after_code": str(item.get("after_code", "")).strip(),
                "confidence": confidence,
            }
        )
    findings.sort(key=lambda item: (CONFIDENCE_ORDER[item["confidence"]], item["file"], item["line"]))
    return {
        "rejected": bool(data.get("rejected")),
        "reject_reason": str(data.get("reject_reason", "")).strip(),
        "findings": [] if data.get("rejected") else findings,
    }


def ollama_base(url: str = DEFAULT_OLLAMA_URL) -> str:
    """끝 슬래시를 뺀 http 주소만 허용한다."""
    cleaned = url.strip().rstrip("/")
    if not cleaned.startswith(("http://", "https://")):
        raise ReviewError("Ollama 주소는 http:// 로 시작해야 합니다.")
    return cleaned


def ollama_reachable(url: str = DEFAULT_OLLAMA_URL) -> bool:
    try:
        base = ollama_base(url)
    except ReviewError:
        return False
    try:
        with urllib.request.urlopen(base + "/api/tags", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def installed_models(url: str = DEFAULT_OLLAMA_URL) -> list[str]:
    try:
        base = ollama_base(url)
        with urllib.request.urlopen(base + "/api/tags", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ReviewError):
        return []
    return [item.get("name", "") for item in payload.get("models", []) if item.get("name")]


def prepare_review(paths: list[Path], standard: str = "c++03", project_root: Path | None = None) -> dict:
    """cppcheck 뒤, 메모리·구조체 함수만 줄 번호를 붙여 잘라 낸다."""
    files = list_sources(paths)
    issues, report = run_cppcheck(files, standard=standard)
    root = project_root
    if root is None:
        for path in paths:
            if path.is_dir():
                root = path
                break
    source_index = {"count": 0, "skipped": True}
    if root is not None:
        try:
            from samples_db import vector_search_enabled
            from vector_store import ensure_source_chunk_index, is_available

            if vector_search_enabled() and is_available():
                source_index = ensure_source_chunk_index(root)
        except Exception as error:  # noqa: BLE001
            source_index = {"count": 0, "error": str(error)}
    chunks, scan_stats = build_chunks(files, issues, root)
    scan_stats = dict(scan_stats)
    scan_stats["source_rag_chunks"] = int(source_index.get("count") or 0)
    if source_index.get("error"):
        scan_stats["source_rag_error"] = str(source_index["error"])
    return {
        "files": files,
        "issues": issues,
        "report": report,
        "chunks": chunks,
        "scan_stats": scan_stats,
        "source_index": source_index,
    }


def _line_cache(chunks: list[dict]) -> dict[str, list[str]]:
    cache: dict[str, list[str]] = {}
    for chunk in chunks:
        path = chunk["path"]
        if path not in cache:
            cache[path] = read_lines(Path(path))
    return cache


def _fill_context(finding: dict, chunk: dict, lines_by_path: dict[str, list[str]]) -> dict:
    """줄 번호가 가리키는 원본 코드와 함수 이름을 리포트에 채운다."""
    lines = lines_by_path.get(chunk["path"], [])
    if not finding["file"]:
        finding["file"] = chunk["file"]
    if finding["line"] <= 0:
        finding["line"] = chunk["start"]
    finding["before_code"] = source_snippet(lines, finding["line"], radius=3)
    detected = function_name_at(lines, finding["line"])
    if detected:
        finding["function_name"] = detected
    elif not finding["function_name"]:
        finding["function_name"] = chunk.get("function_name", "")
    return finding


def _findings_from_suspects(chunk: dict) -> list[dict]:
    """정적 스캐너가 확정한 항목은 모델이 다른 버그만 적어도 남긴다."""
    findings = []
    for item in chunk.get("suspect_lines") or []:
        message = item["message"]
        if "스택" in message:
            bug_type = "buffer_overflow"
            evidence = "고정 길이 스택 배열보다 sprintf가 쓰는 최소 길이가 깁니다."
            name_match = re.search(r"sprintf\((\w+)\)", message)
            name = name_match.group(1) if name_match else "buf"
            after_code = f"snprintf({name}, sizeof({name}), ...);"
        elif "sizeof" in message:
            bug_type = "pointer_sizeof_misuse"
            evidence = "정적 스캐너가 포인터에 sizeof(포인터)를 넣는 패턴을 확정했습니다."
            after_code = "memset(p, 0, sizeof(*p));"
        else:
            bug_type = "other_memory"
            evidence = "정적 스캐너가 이 줄을 메모리 버그로 확정했습니다."
            after_code = ""
        findings.append(
            {
                "file": chunk["file"],
                "line": item["line"],
                "function_name": chunk.get("function_name") or "",
                "bug_type": bug_type,
                "summary": message,
                "evidence": evidence,
                "before_code": "",
                "after_code": after_code,
                "confidence": "high",
            }
        )
    return findings


def _merge_suspects(
    checked: list[dict],
    suspects: list[dict],
    chunk: dict,
    lines_by_path: dict[str, list[str]],
) -> list[dict]:
    """교차 검증이 빠뜨린 강력 의심 줄은 결과 뒤에 다시 붙인다."""
    kept = list(checked)
    covered = {item.get("line") for item in kept}
    for item in suspects:
        if item["line"] in covered:
            continue
        kept.append(_fill_context(dict(item), chunk, lines_by_path))
        covered.add(item["line"])
    return kept


def _analysis_label(stats: dict, index: int, total: int, stage: str, chunk: dict | None = None) -> str:
    """진행 문장은 분석 창을 앞에 두고, 소거 수는 분석 전 제외 수로만 붙인다."""
    pruned = f"소거 {stats['pruned']}/{stats['functions']}함수는 분석 전 제외"
    if chunk is None:
        return f"분석 {index}/{total}창 · {stage} · {pruned}"
    name = chunk.get("function_name") or "(함수 밖)"
    piece = ""
    if chunk.get("window_count", 1) > 1:
        piece = f" 조각 {chunk.get('window_index', 1)}/{chunk['window_count']}"
    return (
        f"분석 {index}/{total}창 · {stage} · {chunk['file']} {name} "
        f"{chunk['start']}-{chunk['end']}{piece} · {pruned}"
    )


def _percent(done: int, total: int, intra: float) -> float:
    """끝난 창 수에 현재 창의 진행을 더한다. 마지막 응답 전에는 99%를 넘기지 않는다."""
    if total <= 0:
        return 0.0
    value = (done + intra) / total * 100.0
    if done == 0 and intra > 0:
        value = max(value, 1.0)
    return min(99.0, max(0.0, value))


def _emit(on_progress, percent: float, label: str) -> None:
    if on_progress:
        on_progress(percent, label)


def _dedupe_findings(findings: list[dict]) -> list[dict]:
    """겹친 창에서 같은 줄, 같은 종류로 나온 버그는 확신도가 높은 하나만 남긴다."""
    deduped: dict[tuple, dict] = {}
    for finding in findings:
        key = (finding["file"], finding["line"], finding["bug_type"])
        current = deduped.get(key)
        if current is None or CONFIDENCE_ORDER[finding["confidence"]] < CONFIDENCE_ORDER[current["confidence"]]:
            deduped[key] = finding
    return sorted(deduped.values(), key=lambda item: (CONFIDENCE_ORDER[item["confidence"]], item["file"], item["line"]))


def _model_missing(error: ReviewError) -> bool:
    text = str(error).lower()
    return "404" in text or "not found" in text


def review_paths(
    paths: list[Path],
    note: str,
    model: str = DEFAULT_MODEL,
    standard: str = "c++03",
    timeout: int = 300,
    num_ctx: int = 4096,
    on_progress=None,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    project_root: Path | None = None,
    deepseek_model: str = DEFAULT_DEEPSEEK,
    llama_model: str = DEFAULT_LLAMA,
    num_predict: int = 512,
    think_mode: str = DEFAULT_THINK_MODE,
    num_gpu: int | None = None,
    num_batch: int = 512,
) -> dict:
    """분석 모델이 창을 보고, 교차 검증이 켜진 경우에만 두 번째 모델이 다시 본다."""
    mode = normalize_think_mode(think_mode)
    use_qwen3 = is_qwen3_model(model)
    prepared = prepare_review(paths, standard, project_root)
    chunks = prepared["chunks"]
    stats = prepared["scan_stats"]
    result = {
        "rejected": False,
        "reject_reason": "",
        "findings": [],
        "report": prepared["report"],
        "chunks": chunks,
        "scan_stats": stats,
        "stage_notes": [],
        "unconfirmed": False,
        "think_mode": mode if use_qwen3 else "",
        "think_logs": [],
        "executed_stages": [],
    }
    if use_qwen3:
        result["stage_notes"].append(
            f"Qwen3 추론 모드 {mode} · 모델 {model} · "
            + ("think=false 고정(FAST)" if mode == "FAST" else "AUTO=의심 시 Thinking" if mode == "AUTO" else "Thinking 강제(DEEP)")
        )
    total = len(chunks)
    last_pulse = {"percent": 0.0, "label": "", "wait_ticks": 0}

    def emit(percent: float, label: str) -> None:
        last_pulse["percent"] = percent
        last_pulse["label"] = label
        last_pulse["wait_ticks"] = 0
        _emit(on_progress, percent, label)

    def on_wait() -> None:
        if not last_pulse["label"]:
            return
        last_pulse["wait_ticks"] = int(last_pulse["wait_ticks"]) + 1
        ticks = int(last_pulse["wait_ticks"])
        # 첫 응답 전에는 스트림이 없어 0~1%에 멈춘 것처럼 보인다. 대기 초를 표시한다.
        waiting = min(0.35, 0.04 + ticks * 0.01)
        base = float(last_pulse["percent"])
        _emit(
            on_progress,
            min(99.0, base + waiting),
            f"{last_pulse['label']} · 모델 적재/프롬프트 대기 {ticks}초",
        )

    if not chunks:
        result["analysis_complete"] = False
        emit(
            0.0,
            f"분석 창 0개 · 모델 호출 없음 · 함수 {stats['functions']}개는 소거만 되었고 분석은 시작하지 않음",
        )
        return result

    lines_by_path = _line_cache(chunks)
    findings: list[dict] = []
    rejected_count = 0
    reject_reason = ""
    deepseek_skipped = False
    emit(
        0.0,
        (
            f"분석 창 {total}개 시작 · 소거 {stats['pruned']}/{stats['functions']}함수 · "
            f"키워드 없는 조각 {stats.get('dropped_windows', 0)}개 제외"
        ),
    )

    def watch(stage: str, done_windows: int, chunk: dict):
        last_chars = {"value": -400}

        def on_stream(chars: int) -> None:
            if chars - last_chars["value"] < 200:
                return
            last_chars["value"] = chars
            intra = min(0.9, 0.08 + chars / 1800)
            emit(
                _percent(done_windows, total, intra),
                _analysis_label(stats, done_windows + 1, total, stage, chunk),
            )

        return on_stream

    announced_retry = False
    for index, chunk in enumerate(chunks, start=1):
        emit(
            _percent(index - 1, total, 0.02),
            _analysis_label(stats, index, total, "분석 요청", chunk),
        )
        first_stage = None
        if use_qwen3:
            first_stage = "DEEP" if mode == "DEEP" else "FAST"
            stage_label = qwen3_call_preset(first_stage)["stage"]
            if stage_label not in result["executed_stages"]:
                result["executed_stages"].append(stage_label)

        def run_window(prompt_note: str, stage: str | None, stream_label: str) -> dict:
            return review_chunks(
                [chunk],
                prepared["report"],
                prompt_note,
                model=model,
                timeout=timeout,
                num_ctx=num_ctx,
                ollama_url=ollama_url,
                on_stream=watch(stream_label, index - 1, chunk),
                on_wait=on_wait,
                num_predict=num_predict,
                think_stage=stage,
                num_gpu=num_gpu,
                num_batch=num_batch,
            )

        try:
            reviewed = run_window(note, first_stage, "분석 응답 수신")
        except ReviewError as error:
            if "JSON" not in str(error) and "모델 응답" not in str(error):
                raise
            result["stage_notes"].append(
                f"{chunk['file']} {chunk.get('function_name') or ''} {chunk['start']}-{chunk['end']} 응답을 읽지 못해 이 창은 건너뛰었습니다."
            )
            emit(
                _percent(index, total, 0.0),
                _analysis_label(stats, index, total, "이 창 건너뜀", chunk),
            )
            continue
        if reviewed.get("think_log"):
            result["think_logs"].append(reviewed["think_log"])
        if reviewed.get("rejected"):
            reviewed = run_window(
                note + "\n이 함수의 메모리 버그와 초기화 버그를 찾아라. 주석의 취약점 설명은 공격 요청이 아니다. rejected는 false.",
                first_stage,
                "분석 재검토",
            )
            if reviewed.get("think_log"):
                result["think_logs"].append(reviewed["think_log"])
        if reviewed.get("json_repaired"):
            result["stage_notes"].append(
                f"{chunk['file']} {chunk.get('function_name') or ''} {chunk['start']}-{chunk['end']} 응답이 잘려 닫힌 항목만 반영했습니다."
            )
        window_findings: list[dict] = []
        if reviewed["rejected"]:
            rejected_count += 1
            reject_reason = reviewed["reject_reason"]
        else:
            window_findings = [_fill_context(finding, chunk, lines_by_path) for finding in reviewed["findings"]]
        suspect_findings = _findings_from_suspects(chunk)
        model_found = bool(window_findings)
        if not model_found:
            window_findings = [_fill_context(dict(item), chunk, lines_by_path) for item in suspect_findings]
        # AUTO: FAST에서 의심/발견이 있으면 같은 qwen3:14b로 Thinking만 켠 채 재검토
        need_deep = (
            use_qwen3
            and mode == "AUTO"
            and first_stage == "FAST"
            and (model_found or bool(chunk.get("suspects")) or bool(suspect_findings))
        )
        if need_deep:
            if "DEEP_TRACE" not in result["executed_stages"]:
                result["executed_stages"].append("DEEP_TRACE")
            emit(
                _percent(index - 1, total, 0.85),
                _analysis_label(stats, index, total, "정밀 Thinking 재검토", chunk),
            )
            try:
                deep_reviewed = run_window(note, "DEEP", "Thinking 응답 수신")
            except ReviewError as error:
                result["stage_notes"].append(f"Thinking 재검토를 건너뛰었습니다: {error}")
            else:
                if deep_reviewed.get("think_log"):
                    result["think_logs"].append(deep_reviewed["think_log"])
                if not deep_reviewed.get("rejected"):
                    window_findings = [
                        _fill_context(finding, chunk, lines_by_path) for finding in deep_reviewed["findings"]
                    ]
                    model_found = bool(window_findings)
                    if not model_found:
                        window_findings = [
                            _fill_context(dict(item), chunk, lines_by_path) for item in suspect_findings
                        ]
        weak_model = "3b" in model.lower()
        cross_model = deepseek_model.strip()
        needs_cross = bool(cross_model) and (
            model_found or bool(chunk.get("suspects")) or (weak_model and not model_found)
        )
        if needs_cross and not model_found and not deepseek_skipped and not announced_retry:
            announced_retry = True
            result["stage_notes"].append("분석 모델이 비운 창은 교차 검증 모델이 한 번 더 봅니다.")
        if needs_cross and not deepseek_skipped:
            emit(
                _percent(index - 1, total, 0.92),
                _analysis_label(stats, index, total, "교차 검증 요청", chunk),
            )
            try:
                checked = cross_check_chunk(
                    chunk,
                    window_findings,
                    cross_model,
                    timeout if model_found else max(timeout, 480),
                    ollama_url,
                    on_stream=watch("교차 검증 응답 수신", index - 1, chunk),
                    on_wait=on_wait,
                    num_predict=num_predict,
                )
            except ReviewError as error:
                if _model_missing(error):
                    deepseek_skipped = True
                    result["stage_notes"].append(f"교차 검증 모델 {deepseek_model}이 없어 이 단계를 건너뛰었습니다.")
                else:
                    result["stage_notes"].append(f"교차 검증을 건너뛰었습니다: {error}")
                if not model_found:
                    result["unconfirmed"] = True
            else:
                if not checked["rejected"]:
                    window_findings = [
                        _fill_context(finding, chunk, lines_by_path) for finding in checked["findings"]
                    ]
        elif needs_cross and deepseek_skipped:
            result["unconfirmed"] = True
        window_findings = _merge_suspects(window_findings, suspect_findings, chunk, lines_by_path)
        findings.extend(window_findings)
        emit(
            _percent(index, total, 0.0),
            _analysis_label(stats, index, total, "이 창 반영", chunk),
        )

    ordered = _dedupe_findings(findings)
    if ordered and llama_model.strip():
        emit(
            99.0,
            f"분석 {total}/{total}창 반영 후 라마 문장 정리 · 소거 {stats['pruned']}/{stats['functions']}함수는 분석 전 제외",
        )
        ordered, polish_note = polish_findings(
            ordered,
            llama_model,
            timeout,
            ollama_url,
            on_stream=lambda chars: emit(
                99.0,
                f"분석 {total}/{total}창 · 라마 응답 수신 {chars}자",
            ),
            on_wait=on_wait,
            num_predict=num_predict,
        )
        if polish_note:
            result["stage_notes"].append(polish_note)
    if rejected_count and not ordered:
        result["rejected"] = True
        result["reject_reason"] = reject_reason or "모델이 함수 검토를 거절해서 정상이라고 볼 수 없습니다."
    elif rejected_count:
        result["stage_notes"].append("일부 창은 모델이 검토를 거절했습니다. 그 창은 버그 없음으로 세지 않았습니다.")
    result["findings"] = ordered
    result["analysis_complete"] = True
    emit(
        100.0,
        (
            f"검토 완료 · 분석 {total}/{total}창 · 소거 {stats['pruned']}/{stats['functions']}함수 · "
            f"키워드 없는 조각 {stats.get('dropped_windows', 0)}개 제외"
        ),
    )
    return result


def _samples_for(chunks: list[dict]) -> list[dict]:
    """이 요청에 들어 있는 함수 본문, 의심 문구, 함수명과 맞는 샘플만 고른다."""
    parts = []
    for chunk in chunks:
        parts.append(chunk.get("text", ""))
        parts.append("\n".join(chunk.get("reasons") or []))
    function_name = chunks[0].get("function_name", "") if len(chunks) == 1 else ""
    return select_samples("\n".join(parts), function_name)


def _ollama_chat(
    model: str,
    system: str,
    user: str,
    ollama_url: str,
    timeout: int,
    num_predict: int = 512,
    on_stream=None,
    on_wait=None,
    *,
    think: bool | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    num_ctx: int | None = None,
    num_gpu: int | None = None,
    num_batch: int | None = None,
    chunk: dict | None = None,
    stage_name: str = "",
) -> dict:
    """스키마를 강제해 한 모델을 호출하고, 응답이 쌓이는 동안 글자 수를 알린다."""
    base = ollama_base(ollama_url)
    if not ollama_reachable(base):
        raise ReviewError(f"Ollama가 {base} 에서 응답하지 않습니다. Ollama를 실행하세요.")
    options = dict(OLLAMA_OPTIONS)
    options["num_predict"] = num_predict
    if temperature is not None:
        options["temperature"] = float(temperature)
    if top_p is not None:
        options["top_p"] = float(top_p)
    if num_ctx is not None:
        options["num_ctx"] = int(num_ctx)
    if num_batch is not None:
        options["num_batch"] = int(num_batch)
    if num_gpu is not None:
        options["num_gpu"] = int(num_gpu)
    # 11GB급에서 qwen3:14b ctx가 커지면 VRAM이 꽉 차 공유 메모리·CPU로 새어 초당 ~2토큰이 된다.
    lowered = (model or "").strip().lower()
    if lowered.startswith("qwen3:14b") or lowered.startswith("qwen3-14b"):
        options["num_ctx"] = min(int(options.get("num_ctx") or 2048), 2048)
        options["num_gpu"] = int(options.get("num_gpu") or 99)
        options["num_batch"] = min(int(options.get("num_batch") or 256), 256)
    # Qwen3 FAST/AUTO 1차는 think=false + /no_think. DEEP만 Thinking.
    prompt_user = user
    if think is False:
        if "/no_think" not in user:
            prompt_user = user.rstrip() + "\n\n/no_think"
        body_think = False
    elif think is True:
        body_think = True
    else:
        body_think = None
    body = {
        "model": model,
        "stream": True,
        "format": OUTPUT_SCHEMA,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt_user},
        ],
        "options": options,
    }
    if body_think is not None:
        body["think"] = body_think
    request = urllib.request.Request(
        base + "/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    parts: list[str] = []
    thinking: list[str] = []
    received = 0
    reported = 0
    deadline = time.monotonic() + timeout
    timed_out = False
    incoming: queue.Queue = queue.Queue()

    def read_lines() -> None:
        try:
            while True:
                raw_line = response.readline()
                incoming.put(raw_line)
                if not raw_line:
                    break
        except BaseException as error:
            incoming.put(error)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            reader = threading.Thread(target=read_lines, daemon=True)
            reader.start()
            while time.monotonic() < deadline:
                try:
                    raw = incoming.get(timeout=1.0)
                except queue.Empty:
                    if on_wait:
                        on_wait()
                    continue
                if isinstance(raw, BaseException):
                    raise raw
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = event.get("message") or {}
                piece = message.get("content") or ""
                thought = message.get("thinking") or ""
                if piece:
                    parts.append(piece)
                if thought:
                    thinking.append(thought)
                received = sum(len(item) for item in parts) + sum(len(item) for item in thinking)
                if on_stream and received and (received - reported >= 200 or event.get("done")):
                    reported = received
                    on_stream(received)
                if event.get("done"):
                    break
            else:
                timed_out = True
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        if error.code == 404 and "not found" in detail.lower():
            raise ReviewError(
                f"{model} 모델이 이 PC의 Ollama에 없습니다. 검토 화면에서 모델을 받은 뒤 다시 시작하세요."
            ) from error
        raise ReviewError(f"Ollama 요청이 실패했습니다 ({error.code}). {detail}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ReviewError(f"Ollama와 통신하지 못했습니다: {error}") from error
    except ReviewError:
        raise
    except Exception as error:
        raise ReviewError(f"Ollama와 통신하지 못했습니다: {error}") from error
    content = "".join(parts)
    api_thinking = "".join(thinking)
    if not content.strip() and api_thinking.strip():
        content = api_thinking
    cleaned, tagged_think = strip_think_blocks(content)
    think_text = "\n\n".join(part for part in (api_thinking, tagged_think) if part.strip())
    think_log = ""
    if think_text and chunk is not None:
        think_log = save_think_log(chunk, stage_name or "THINK", think_text)
    parse_source = cleaned or content
    if timed_out and parse_source.strip():
        try:
            partial = extract_json(parse_source)
        except ReviewError:
            partial = None
        if partial is not None:
            partial["json_repaired"] = True
            if think_log:
                partial["think_log"] = think_log
            return partial
    if timed_out:
        raise ReviewError("Ollama 응답 대기 시간이 초과되었습니다.")
    parsed = extract_json(parse_source)
    if think_log:
        parsed["think_log"] = think_log
    return parsed


def cross_check_chunk(
    chunk: dict,
    findings: list[dict],
    model: str,
    timeout: int,
    ollama_url: str,
    on_stream=None,
    on_wait=None,
    num_predict: int = 512,
) -> dict:
    """교차 검증 모델이 같은 창과 1차 결과를 보고 오탐을 빼거나 누락을 보탠다."""
    return _ollama_chat(
        model,
        CROSS_SYSTEM,
        build_cross_prompt(chunk, findings),
        ollama_url,
        timeout,
        num_predict=num_predict,
        on_stream=on_stream,
        on_wait=on_wait,
    )


def polish_findings(
    findings: list[dict],
    model: str,
    timeout: int,
    ollama_url: str,
    on_stream=None,
    on_wait=None,
    num_predict: int = 512,
) -> tuple[list[dict], str]:
    """라마가 해설 문장만 다듬는다. 줄 번호와 버그 종류는 파이썬이 유지한다."""
    try:
        reviewed = _ollama_chat(
            model,
            POLISH_SYSTEM,
            build_polish_prompt(findings),
            ollama_url,
            timeout,
            num_predict=num_predict,
            on_stream=on_stream,
            on_wait=on_wait,
        )
    except ReviewError as error:
        if _model_missing(error):
            return findings, f"라마 모델 {model}이 없어 문장 정리를 건너뛰었습니다."
        return findings, f"라마 문장 정리를 건너뛰었습니다: {error}"
    by_key = {
        (item["file"], item["line"], item["bug_type"]): item
        for item in reviewed["findings"]
    }
    for finding in findings:
        updated = by_key.get((finding["file"], finding["line"], finding["bug_type"]))
        if updated is None:
            continue
        for field in ("summary", "evidence", "after_code"):
            if updated.get(field):
                finding[field] = updated[field]
    return findings, ""


def review_chunks(
    chunks: list[dict],
    static_report: str,
    note: str,
    model: str = DEFAULT_MODEL,
    timeout: int = 300,
    num_ctx: int = 4096,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    on_stream=None,
    on_wait=None,
    num_predict: int = 512,
    think_stage: str | None = None,
    num_gpu: int | None = None,
    num_batch: int = 512,
) -> dict:
    rules = load_memory_rules(RULES_PATH)
    picked = _samples_for(chunks)
    if len(chunks) == 1:
        chunks[0]["injected_samples"] = [
            {
                "id": item["id"],
                "category": item["category"],
                "is_false_positive": item["is_false_positive"],
                "select_reason": item.get("_select_reason") or "keyword",
                "select_score": item.get("_select_score"),
                "vector_score": item.get("_vector_score"),
                "keyword_score": item.get("_keyword_score"),
            }
            for item in picked
        ]
    call_think = None
    call_temperature = None
    call_top_p = None
    call_ctx = num_ctx
    stage_name = "STANDARD"
    if is_qwen3_model(model) and think_stage in {"FAST", "DEEP"}:
        preset = qwen3_call_preset(think_stage)
        call_think = bool(preset["think"])
        call_temperature = float(preset["temperature"])
        call_top_p = float(preset["top_p"])
        stage_name = str(preset["stage"])
    return _ollama_chat(
        model,
        build_system_prompt(rules, format_samples(picked), format_whitelist(load_whitelist())),
        build_user_prompt(chunks, static_report, note),
        ollama_url,
        timeout,
        num_predict=num_predict,
        on_stream=on_stream,
        on_wait=on_wait,
        think=call_think,
        temperature=call_temperature,
        top_p=call_top_p,
        num_ctx=call_ctx,
        num_gpu=num_gpu,
        num_batch=num_batch,
        chunk=chunks[0] if len(chunks) == 1 else None,
        stage_name=stage_name,
    )
