"""C++ 메모리 버그 로컬 검토 화면."""

from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time

# 다른 라이브러리 import 전에 텔레메트리·HF 오프라인 차단을 건다.
from security_audit import apply_local_security_env, ensure_streamlit_config

apply_local_security_env()
ensure_streamlit_config()

import pandas as pd
import streamlit as st

from analyzer import cppcheck_path
from cpu_meter import cpu_label, sample_cpu
from hardware import RAM_LABELS, VRAM_LABELS, hardware_profile, ollama_call_options
from server_status import (
    collect_server_status,
    download_remote_file,
    load_server_config,
    save_server_config,
)
from sys_panel import render_command_panel, sample_host
from report import save_reports
from reviewer import (
    DEFAULT_LLAMA,
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_URL,
    DEFAULT_THINK_MODE,
    POLISH_MODELS,
    PREDICT_CHOICES,
    QWEN3_MODEL,
    THINK_MODES,
    ReviewError,
    installed_models,
    is_qwen3_model,
    normalize_think_mode,
    ollama_reachable,
    review_paths,
)
from samples_db import (
    SAMPLE_MD_TEMPLATE,
    SAMPLES_PATH,
    add_sample,
    delete_sample,
    import_samples,
    import_samples_from_markdown,
    load_samples,
    register_false_positive,
    set_vector_search_enabled,
)
from whitelist import add_name, load_whitelist, remove_name


def _choose_project_folder() -> str:
    """이 PC에서 프로젝트 폴더를 고른다. 대화상자가 없으면 경로를 직접 입력한다."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        window = tk.Tk()
        window.withdraw()
        window.attributes("-topmost", True)
        selected = filedialog.askdirectory(title="프로젝트 루트 폴더")
        window.destroy()
    except Exception:
        return ""
    return selected or ""


def _choose_files(title: str, patterns: list[tuple[str, str]], *, max_count: int = 5) -> list[str]:
    """파일 다중 선택(최대 max_count). 실패 시 빈 목록."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        window = tk.Tk()
        window.withdraw()
        window.attributes("-topmost", True)
        selected = filedialog.askopenfilenames(title=title, filetypes=patterns)
        window.destroy()
    except Exception:
        return []
    paths = [str(item) for item in (selected or [])][:max_count]
    return paths


def _ollama_exe() -> str:
    """설치된 ollama 실행 파일을 찾는다."""
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Ollama" / "ollama.exe",
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    return shutil.which("ollama") or ""


def _pull_model(name: str) -> None:
    """없는 모델을 이 PC의 Ollama로 받는다."""
    exe = _ollama_exe()
    if not exe:
        st.error("ollama.exe 를 찾지 못했습니다.")
        return
    with st.status(f"{name} 받는 중", expanded=True) as status:
        process = subprocess.Popen(
            [exe, "pull", name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output = st.empty()
        lines: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            lines.append(line.rstrip())
            output.code("\n".join(lines[-15:]))
        code = process.wait()
        if code == 0:
            status.update(label=f"{name} 받음", state="complete")
        else:
            status.update(label=f"{name} 받기 실패", state="error")
            st.error(f"{name} 받기에 실패했습니다.")
            return
    st.rerun()

BUG_LABELS = {
    "use_after_free": "해제 후 사용",
    "double_free": "중복 해제",
    "memory_leak": "누수",
    "buffer_overflow": "버퍼 넘침",
    "uninitialized_read": "미초기화 읽기",
    "struct_partial_uninit": "구조체 부분 미초기화",
    "pointer_sizeof_misuse": "포인터 sizeof 오용",
    "dangling_pointer": "댕글링 포인터",
    "new_delete_mismatch": "new/delete 불일치",
    "other_memory": "기타 메모리",
}
SCREEN_OPTIONS = ["코드 검토", "헤더 인덱스", "샘플 학습 관리", "초기화 화이트리스트"]
DIALOG_FLAGS = (
    "_open_options",
    "_open_server",
    "_open_security",
    "_open_header_prep",
    "show_done_dialog",
)


def _close_all_dialogs(*, keep: str | None = None) -> None:
    """메뉴/화면 전환 때 이전 다이얼로그가 다시 뜨지 않게 닫는다."""
    for key in DIALOG_FLAGS:
        if keep and key == keep:
            continue
        st.session_state[key] = False


def _format_stopwatch(seconds: float) -> str:
    """초를 스톱워치 표기(MM:SS 또는 H:MM:SS)로 바꾼다."""
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

st.set_page_config(page_title="C++ 메모리·초기화 버그 검토", layout="wide")
st.markdown(
    """
<style>
div[data-testid="stAppViewContainer"] > .main > div.block-container {
    padding-top: 1.2rem;
}
.st-key-app_header {
    background: #0a0a0a;
    padding: 0.75rem 1rem 0.55rem 1rem;
    margin: 0 0 1rem 0;
    border-radius: 8px;
}
.st-key-app_header .st-key-header_title,
.st-key-app_header .st-key-header_title p,
.st-key-app_header .st-key-header_title span {
    color: #f5f5f5 !important;
    margin: 0 0 0.45rem 0 !important;
    font-size: 1.45rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
    line-height: 1.25 !important;
}
.st-key-main_nav {
    background: transparent;
    padding: 0;
    margin: 0;
}
.st-key-main_nav div[data-testid="stHorizontalBlock"] {
    gap: 0 !important;
}
.st-key-main_nav button {
    background: transparent !important;
    border: none !important;
    color: #d8d8d8 !important;
    box-shadow: none !important;
    font-weight: 500;
    width: 100%;
}
.st-key-main_nav button[kind="primary"] {
    background: #6e6e6e !important;
    color: #ffffff !important;
    border-radius: 4px !important;
}
.st-key-main_nav button:hover {
    background: rgba(255, 255, 255, 0.12) !important;
    color: #ffffff !important;
}
.st-key-main_nav button[kind="primary"]:hover {
    background: #808080 !important;
    color: #ffffff !important;
}
.st-key-main_nav .st-key-nav-option {
    border-left: 1px solid rgba(255, 255, 255, 0.22) !important;
    margin-left: 0.35rem;
}
.st-key-guide_canvas,
.st-key-status_canvas {
    border-radius: 10px;
    padding: 0.85rem 1rem 1rem 1rem;
    min-height: 460px;
    height: 100%;
}
.st-key-guide_canvas {
    background: #1b1e24 !important;
    border: 1px solid #3d4550 !important;
    overflow: hidden;
}
.st-key-status_canvas {
    background: #3a3a3a !important;
    border: 1px solid #555555 !important;
}
.st-key-status_canvas,
.st-key-status_canvas p,
.st-key-status_canvas span,
.st-key-status_canvas label {
    color: #f2f2f2 !important;
}
.st-key-status_canvas h5 {
    margin: 0 0 0.55rem 0;
    color: #ffffff !important;
}
.st-key-status_canvas [data-testid="stMetricLabel"],
.st-key-status_canvas [data-testid="stMetricValue"] {
    color: #f5f5f5 !important;
}
.st-key-status_canvas [data-testid="stCaptionContainer"] {
    color: #d8d8d8 !important;
}
.st-key-guide_canvas .cmd-panel {
    font-family: Consolas, "Courier New", monospace;
    color: #9ad7ef;
    font-size: 0.72rem;
    line-height: 1.25;
}
.st-key-guide_canvas .cmd-title {
    color: #8fd3f4;
    font-weight: 700;
    font-size: 0.86rem;
    letter-spacing: 0.02em;
}
.st-key-guide_canvas .cmd-sub {
    color: #e0872f;
    margin-top: 0.12rem;
}
.st-key-guide_canvas .cmd-meta {
    color: #9aa7b5;
    margin-top: 0.18rem;
    margin-bottom: 0.45rem;
}
.st-key-guide_canvas .cmd-grid {
    display: grid;
    grid-template-columns: 1.05fr 1fr;
    gap: 0.55rem;
}
.st-key-guide_canvas .cmd-left,
.st-key-guide_canvas .cmd-right {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
}
.st-key-guide_canvas .cmd-card,
.st-key-guide_canvas .cmd-chart {
    position: relative;
    border: 1px solid rgba(224, 135, 47, 0.55);
    background: rgba(10, 12, 16, 0.55);
    padding: 0.4rem 0.45rem 0.35rem 0.45rem;
}
.st-key-guide_canvas .cmd-card:before,
.st-key-guide_canvas .cmd-card:after,
.st-key-guide_canvas .cmd-chart:before,
.st-key-guide_canvas .cmd-chart:after {
    content: "";
    position: absolute;
    width: 10px;
    height: 10px;
    border-color: #e0872f;
    border-style: solid;
}
.st-key-guide_canvas .cmd-card:before,
.st-key-guide_canvas .cmd-chart:before {
    top: -1px;
    left: -1px;
    border-width: 2px 0 0 2px;
}
.st-key-guide_canvas .cmd-card:after,
.st-key-guide_canvas .cmd-chart:after {
    right: -1px;
    bottom: -1px;
    border-width: 0 2px 2px 0;
}
.st-key-guide_canvas .cmd-card-title,
.st-key-guide_canvas .cmd-chart-title {
    color: #d7e7f2;
    margin-bottom: 0.28rem;
    font-size: 0.72rem;
}
.st-key-guide_canvas .cmd-metric {
    margin-bottom: 0.22rem;
}
.st-key-guide_canvas .cmd-metric-row {
    display: flex;
    justify-content: space-between;
    gap: 0.4rem;
    color: #b7c4d1;
    margin-bottom: 0.08rem;
}
.st-key-guide_canvas .cmd-metric-emphasis,
.st-key-guide_canvas .cmd-metric-shared {
    margin: 0.45rem 0 0.5rem 0;
    padding: 0.42rem 0.5rem 0.4rem 0.5rem;
}
.st-key-guide_canvas .cmd-metric-emphasis {
    background: #3a3224;
    border: 1px solid #e0872f;
    box-shadow: inset 0 0 0 1px rgba(224, 135, 47, 0.18);
}
.st-key-guide_canvas .cmd-metric-shared {
    background: #243038;
    border: 1px solid #7ec8e3;
    box-shadow: inset 0 0 0 1px rgba(126, 200, 227, 0.18);
}
.st-key-guide_canvas .cmd-metric-emphasis .cmd-metric-row,
.st-key-guide_canvas .cmd-metric-shared .cmd-metric-row {
    margin-bottom: 0.18rem;
    letter-spacing: 0.02em;
}
.st-key-guide_canvas .cmd-metric-emphasis .cmd-metric-row {
    color: #fff3e0;
}
.st-key-guide_canvas .cmd-metric-shared .cmd-metric-row {
    color: #e8f7fc;
}
.st-key-guide_canvas .cmd-metric-emphasis .cmd-metric-label {
    color: #ffd089 !important;
    font-weight: 700;
    font-size: 0.8rem;
}
.st-key-guide_canvas .cmd-metric-shared .cmd-metric-label {
    color: #9ad7ef !important;
    font-weight: 700;
    font-size: 0.8rem;
}
.st-key-guide_canvas .cmd-metric-emphasis .cmd-metric-value,
.st-key-guide_canvas .cmd-metric-shared .cmd-metric-value {
    color: #ffffff !important;
    font-weight: 700;
    font-size: 0.8rem;
}
.st-key-guide_canvas .cmd-metric-emphasis .cmd-track,
.st-key-guide_canvas .cmd-metric-shared .cmd-track {
    height: 9px;
    margin-top: 0.12rem;
}
.st-key-guide_canvas .cmd-metric-emphasis .cmd-track {
    background: #241c12;
    border: 1px solid #c07828;
}
.st-key-guide_canvas .cmd-metric-shared .cmd-track {
    background: #152028;
    border: 1px solid #5aa7c2;
}
.st-key-guide_canvas .cmd-track {
    height: 7px;
    background: #2a3038;
    border: 1px solid #3f4854;
}
.st-key-guide_canvas .cmd-fill {
    height: 100%;
}
.st-key-guide_canvas .cmd-spark {
    width: 100%;
    height: 54px;
    display: block;
    background: rgba(0, 0, 0, 0.25);
}
.st-key-guide_canvas .cmd-chart-foot {
    color: #8fa0b0;
    margin-top: 0.15rem;
}
.st-key-guide_canvas .cmd-foot {
    margin-top: 0.45rem;
    border-top: 1px solid #3a4450;
    padding-top: 0.35rem;
}
.st-key-guide_canvas .cmd-task {
    color: #8fd3f4;
    margin-bottom: 0.2rem;
}
.st-key-guide_canvas .cmd-log {
    color: #9aa7b5;
    min-height: 2.2em;
}
.st-key-guide_canvas .cmd-alert {
    margin-top: 0.25rem;
    border: 1px solid #d64545;
    color: #ff8f8f;
    padding: 0.2rem 0.35rem;
}
.st-key-work_canvas {
    background: #3a3a3a !important;
    border: 1px solid #555555 !important;
    border-radius: 10px;
    padding: 1rem 1.1rem 1.15rem 1.1rem;
    margin-top: 0.85rem;
}
.st-key-work_canvas,
.st-key-work_canvas p,
.st-key-work_canvas span,
.st-key-work_canvas label,
.st-key-work_canvas small,
.st-key-work_canvas h5 {
    color: #f2f2f2 !important;
}
.st-key-work_canvas [data-testid="stCaptionContainer"],
.st-key-work_canvas [data-testid="stCaptionContainer"] p {
    color: #c8c8c8 !important;
}
.st-key-work_canvas [data-testid="stTextInputRootElement"] input,
.st-key-work_canvas [data-testid="stTextAreaRootElement"] textarea,
.st-key-work_canvas input,
.st-key-work_canvas textarea {
    background: #2f2f2f !important;
    color: #f2f2f2 !important;
    border: 1px solid #5a5a5a !important;
    caret-color: #f2f2f2 !important;
}
.st-key-work_canvas [data-testid="stTextInputRootElement"],
.st-key-work_canvas [data-testid="stTextAreaRootElement"],
.st-key-work_canvas [data-baseweb="base-input"],
.st-key-work_canvas [data-baseweb="input"],
.st-key-work_canvas [data-baseweb="textarea"] {
    background: #2f2f2f !important;
    color: #f2f2f2 !important;
}
.st-key-work_canvas [data-testid="stFileUploaderDropzone"] {
    background: #2f2f2f !important;
    border: 1px dashed #6a6a6a !important;
    color: #e6e6e6 !important;
}
.st-key-work_canvas [data-testid="stFileUploaderDropzone"] *,
.st-key-work_canvas [data-testid="stFileUploaderDropzone"] small,
.st-key-work_canvas [data-testid="stFileUploaderDropzone"] span {
    color: #d8d8d8 !important;
}
.st-key-work_canvas [data-testid="stFileUploaderDropzone"] button,
.st-key-work_canvas button {
    background: #6e6e6e !important;
    color: #f5f5f5 !important;
    border: 1px solid #808080 !important;
    box-shadow: none !important;
}
.st-key-work_canvas button:hover {
    background: #808080 !important;
    color: #ffffff !important;
    border-color: #959595 !important;
}
.st-key-work_canvas button[kind="primary"] {
    background: #7a7a7a !important;
    color: #ffffff !important;
    border: 1px solid #939393 !important;
}
.st-key-work_canvas button[kind="primary"]:hover {
    background: #8a8a8a !important;
}
</style>
""",
    unsafe_allow_html=True,
)
notice = st.session_state.pop("sample_notice", "")
if notice:
    st.success(notice)
if "screen" not in st.session_state or st.session_state.screen not in SCREEN_OPTIONS:
    st.session_state.screen = "코드 검토"
with st.container(key="app_header", border=False):
    with st.container(key="header_title"):
        st.markdown("C++ 메모리·초기화 버그 검토")
    with st.container(key="main_nav", horizontal=True, gap=None):
        for name in SCREEN_OPTIONS:
            selected = st.session_state.screen == name
            if st.button(
                name,
                key=f"nav-{name}",
                type="primary" if selected else "secondary",
                use_container_width=True,
            ):
                # 화면 바꿀 때 옵션/서버/보안/전처리 창을 모두 닫아 이전 창 잔존을 막는다.
                _close_all_dialogs()
                st.session_state.screen = name
                st.rerun()
        if st.button("옵션", key="nav-option", type="secondary", use_container_width=True):
            # 다이얼로그 위젯은 별도 키를 쓰고, 열 때 현재 저장값을 복사한다.
            st.session_state["dlg_vram"] = st.session_state.get("vram", "8")
            st.session_state["dlg_ram"] = st.session_state.get("ram", "16")
            st.session_state["dlg_shared_memory"] = bool(st.session_state.get("shared_memory"))
            st.session_state["dlg_model_name"] = st.session_state.get("model_name", DEFAULT_MODEL)
            st.session_state["dlg_think_mode"] = normalize_think_mode(st.session_state.get("think_mode"))
            st.session_state["dlg_cross_enabled"] = bool(st.session_state.get("cross_enabled"))
            st.session_state["dlg_deepseek_model"] = st.session_state.get("deepseek_model", DEFAULT_MODEL)
            st.session_state["dlg_llama_model"] = st.session_state.get("llama_model", DEFAULT_LLAMA)
            st.session_state["dlg_num_predict"] = st.session_state.get("num_predict", 2048)
            st.session_state["dlg_cpp_standard"] = st.session_state.get("cpp_standard", "c++03")
            st.session_state["dlg_vector_search"] = bool(st.session_state.get("vector_search", True))
            _close_all_dialogs(keep="_open_options")
            st.session_state["_open_options"] = True
            st.rerun()
        if st.button("서버 설정", key="nav-server", type="secondary", use_container_width=True):
            _close_all_dialogs(keep="_open_server")
            st.session_state["_open_server"] = True
            st.rerun()
        if st.button("보안점검", key="nav-security", type="secondary", use_container_width=True):
            _close_all_dialogs(keep="_open_security")
            st.session_state["_open_security"] = True
            st.rerun()
screen = st.session_state.screen
# 헤더 인덱스가 아니면 전처리 창은 강제로 닫는다.
if screen != "헤더 인덱스":
    st.session_state["_open_header_prep"] = False

if "vram" not in st.session_state:
    st.session_state.vram = "8"
if "ram" not in st.session_state:
    st.session_state.ram = "16"
if "shared_memory" not in st.session_state:
    st.session_state.shared_memory = False
if not str(st.session_state.get("ollama_url") or "").strip():
    st.session_state.ollama_url = DEFAULT_OLLAMA_URL
if "model_name" not in st.session_state:
    st.session_state.model_name = DEFAULT_MODEL
if "think_mode" not in st.session_state:
    st.session_state.think_mode = DEFAULT_THINK_MODE
if "vector_search" not in st.session_state:
    st.session_state.vector_search = True
if "cross_enabled" not in st.session_state:
    st.session_state.cross_enabled = False
if "deepseek_model" not in st.session_state:
    st.session_state.deepseek_model = DEFAULT_MODEL
if "llama_model" not in st.session_state:
    st.session_state.llama_model = DEFAULT_LLAMA
if "num_predict" not in st.session_state:
    st.session_state.num_predict = 2048
if "cpp_standard" not in st.session_state:
    st.session_state.cpp_standard = "c++03"
if st.session_state.get("predict_default_version") != 3:
    st.session_state.num_predict = 2048
    st.session_state.predict_default_version = 3
if st.session_state.get("model_defaults_version") != 5:
    st.session_state.model_name = DEFAULT_MODEL
    st.session_state.deepseek_model = DEFAULT_MODEL
    st.session_state.llama_model = DEFAULT_LLAMA
    st.session_state.model_defaults_version = 5
if st.session_state.get("think_mode_defaults_version") != 1:
    st.session_state.think_mode = DEFAULT_THINK_MODE
    st.session_state.think_mode_defaults_version = 1
if "project_root" not in st.session_state:
    st.session_state.project_root = ""
st.session_state.think_mode = normalize_think_mode(st.session_state.get("think_mode"))
set_vector_search_enabled(bool(st.session_state.get("vector_search", True)))
pending_model = st.session_state.pop("_pending_model", None)
if pending_model:
    st.session_state.model_name = pending_model
pending_root = st.session_state.pop("_pending_root", None)
if pending_root:
    st.session_state.project_root = pending_root


def _model_choices(current: str, installed: list[str] | None = None) -> list[str]:
    """기본 모델, Qwen3 14B, 공식 대형 코더, 이 PC에 설치된 모델을 선택 목록으로 만든다."""
    offered = (
        DEFAULT_MODEL,
        QWEN3_MODEL,
        "qwen2.5-coder:14b",
        "qwen2.5-coder:32b",
        current,
        *(installed or []),
    )
    choices: list[str] = []
    for name in offered:
        cleaned = name.strip()
        if cleaned and cleaned not in choices:
            choices.append(cleaned)
    return choices


def _polish_model_choices(current: str, installed: list[str] | None = None) -> list[str]:
    """문장 정리는 빠른 Llama를 앞에 두고, 설치된 llama 계열도 넣는다."""
    installed_llama = [
        name for name in (installed or []) if name.strip().lower().startswith("llama")
    ]
    offered = (
        *POLISH_MODELS,
        DEFAULT_LLAMA,
        current,
        *installed_llama,
        *(installed or []),
    )
    choices: list[str] = []
    for name in offered:
        cleaned = name.strip()
        if cleaned and cleaned not in choices:
            choices.append(cleaned)
    return choices


def _select_model(label: str, key: str, help_text: str, installed: list[str], *, polish: bool = False) -> None:
    """세 단계가 각자 설치된 모델 중 하나를 고르게 한다."""
    fallback = DEFAULT_LLAMA if polish else DEFAULT_MODEL
    current = str(st.session_state.get(key) or fallback)
    choices = _polish_model_choices(current, installed) if polish else _model_choices(current, installed)
    if current not in choices:
        # 위젯 생성 전에만 기본값을 보정한다.
        st.session_state[key] = choices[0]
        current = choices[0]
    st.selectbox(label, choices, key=key, help=help_text)


def _commit_options_from_dialog() -> None:
    """옵션 다이얼로그 임시 키를 앱 저장값으로 옮긴다."""
    st.session_state.vram = str(st.session_state.get("dlg_vram") or st.session_state.get("vram") or "8")
    st.session_state.ram = str(st.session_state.get("dlg_ram") or st.session_state.get("ram") or "16")
    st.session_state.shared_memory = bool(st.session_state.get("dlg_shared_memory"))
    st.session_state.model_name = str(
        st.session_state.get("dlg_model_name") or st.session_state.get("model_name") or DEFAULT_MODEL
    )
    st.session_state.think_mode = normalize_think_mode(
        st.session_state.get("dlg_think_mode") or st.session_state.get("think_mode")
    )
    st.session_state.cross_enabled = bool(st.session_state.get("dlg_cross_enabled"))
    st.session_state.deepseek_model = str(
        st.session_state.get("dlg_deepseek_model") or st.session_state.get("deepseek_model") or DEFAULT_MODEL
    )
    st.session_state.llama_model = str(
        st.session_state.get("dlg_llama_model") or st.session_state.get("llama_model") or DEFAULT_LLAMA
    )
    st.session_state.num_predict = int(
        st.session_state.get("dlg_num_predict") or st.session_state.get("num_predict") or 2048
    )
    st.session_state.cpp_standard = str(
        st.session_state.get("dlg_cpp_standard") or st.session_state.get("cpp_standard") or "c++03"
    )
    st.session_state.vector_search = bool(st.session_state.get("dlg_vector_search", True))
    set_vector_search_enabled(st.session_state.vector_search)


@st.dialog("검토 결과")
def review_done_dialog() -> None:
    """분석 창을 모두 처리한 뒤에만 완료로 보여 준다. 소거만 된 경우는 완료가 아니다."""
    result = st.session_state.get("last_review") or {}
    stats = result.get("scan_stats") or {}
    windows = int(stats.get("windows") or 0)
    findings = len(result.get("findings") or [])
    if result.get("analysis_complete") and windows > 0:
        st.success(f"진행 100%. 분석 창 {windows}개를 모두 처리했습니다.")
    else:
        st.warning("모델 분석은 하지 않았습니다. 메모리·포인터·구조체가 있는 함수가 없어 소거만 되었습니다.")
    st.write(
        f"함수 {stats.get('functions', 0)}개 중 {stats.get('pruned', 0)}개는 분석 전에 제외했습니다. "
        f"키워드 없는 긴 함수 조각 {int(stats.get('dropped_windows') or 0)}개는 모델에 넘기지 않았습니다. "
        f"발견 {findings}건."
    )
    if result.get("unconfirmed") and findings == 0:
        st.warning("교차 검증이 끝나지 않았습니다. 버그 없음으로 확정하지 않습니다.")
    elif result.get("unconfirmed"):
        st.warning("교차 검증이 끝나지 않았습니다. 위에 나온 항목 외에 놓친 버그가 더 있을 수 있습니다.")
    if st.button("확인", type="primary", key="close-review-done"):
        st.session_state["show_done_dialog"] = False
        st.rerun()


@st.dialog("옵션")
def options_dialog() -> None:
    """하드웨어, 분석 모델, 토큰, cppcheck 표준을 한곳에서 관리한다."""
    # 위젯 생성 전에 다이얼로그 키 기본값을 보장한다.
    st.session_state.setdefault("dlg_vram", st.session_state.get("vram", "8"))
    st.session_state.setdefault("dlg_ram", st.session_state.get("ram", "16"))
    st.session_state.setdefault("dlg_shared_memory", bool(st.session_state.get("shared_memory")))
    st.session_state.setdefault("dlg_model_name", st.session_state.get("model_name", DEFAULT_MODEL))
    st.session_state.setdefault(
        "dlg_think_mode",
        normalize_think_mode(st.session_state.get("think_mode", DEFAULT_THINK_MODE)),
    )
    st.session_state.setdefault("dlg_cross_enabled", bool(st.session_state.get("cross_enabled")))
    st.session_state.setdefault("dlg_deepseek_model", st.session_state.get("deepseek_model", DEFAULT_MODEL))
    st.session_state.setdefault("dlg_llama_model", st.session_state.get("llama_model", DEFAULT_LLAMA))
    st.session_state.setdefault("dlg_num_predict", st.session_state.get("num_predict", 2048))
    st.session_state.setdefault("dlg_cpp_standard", st.session_state.get("cpp_standard", "c++03"))
    st.session_state.setdefault("dlg_vector_search", bool(st.session_state.get("vector_search", True)))

    installed = installed_models(st.session_state.ollama_url)
    st.markdown("**하드웨어**")
    # 다이얼로그 전용 키(dlg_*)만 위젯에 연결한다. 닫을 때 앱 저장키로 커밋한다.
    st.radio(
        "그래픽 메모리",
        list(VRAM_LABELS),
        format_func=lambda key: VRAM_LABELS[key],
        key="dlg_vram",
    )
    st.radio(
        "메인 메모리",
        list(RAM_LABELS),
        format_func=lambda key: RAM_LABELS[key],
        key="dlg_ram",
    )
    st.checkbox(
        "공유 메모리 사용",
        key="dlg_shared_memory",
        help="켜면 안내 패널의 VRAM 아래에 시스템 공유 메모리 사용량을 표시합니다. "
        "내장 그래픽처럼 VRAM과 메인 메모리를 같이 쓰는 PC에 맞습니다.",
    )
    chosen = hardware_profile(st.session_state.dlg_vram, st.session_state.dlg_ram)
    st.write(f"권장 {chosen['model']} · 컨텍스트 {chosen['num_ctx']}")
    st.caption(chosen["note"])
    if installed and chosen["model"] not in installed:
        st.warning(f"{chosen['model']} 이 이 PC에 없습니다. 적용한 뒤 검토 화면에서 받아야 검토가 시작됩니다.")
    if st.button("하드웨어 권장 적용", type="secondary"):
        _commit_options_from_dialog()
        st.session_state["_pending_model"] = chosen["model"]
        st.rerun()

    st.markdown("**모델·호출**")
    _select_model(
        "분석 모델",
        "dlg_model_name",
        f"메모리·초기화 1차 분석. Qwen3는 {QWEN3_MODEL} 하나만 쓰고 FAST에서 think를 끕니다.",
        installed,
    )
    think_labels = {
        "FAST": "FAST (/no_think, 기본·고속)",
        "AUTO": "AUTO (FAST 후 의심 시 Thinking)",
        "DEEP": "DEEP (Thinking 강제)",
    }
    st.selectbox(
        "Qwen3 추론 모드",
        list(THINK_MODES),
        format_func=lambda key: think_labels.get(key, key),
        key="dlg_think_mode",
        help="qwen3:14b 선택 시에만 적용됩니다. 기본은 FAST로 think=false 고정입니다. "
        "별도 fast/deep 모델명은 쓰지 않습니다.",
    )
    if is_qwen3_model(str(st.session_state.get("dlg_model_name") or "")):
        st.caption("현재 분석 모델이 Qwen3입니다. FAST면 Ollama 요청에 think=false 를 넣습니다.")
    else:
        st.caption("Qwen3가 아니면 추론 모드는 무시되고 기존 temperature 0 호출을 씁니다.")
    st.checkbox("교차 검증", key="dlg_cross_enabled", help="켜져 있을 때만 두 번째 모델을 호출합니다. 기본은 끔입니다.")
    _select_model("교차 검증 모델", "dlg_deepseek_model", "교차 검증을 켰을 때 쓰는 모델. 기본은 qwen2.5-coder:7b", installed)
    _select_model(
        "문장 정리 모델",
        "dlg_llama_model",
        "발견 항목의 한국어 해설만 다듬습니다. 권장: llama3.1:8b (FAST Thinking 없음)",
        installed,
        polish=True,
    )
    st.selectbox(
        "토큰 상한",
        PREDICT_CHOICES,
        key="dlg_num_predict",
        help="한 번 호출에서 생성하는 최대 토큰. 다건 탐지는 2048 권장. "
        "속도 우선이면 512~1024, 4096은 총 시간이 더 걸립니다.",
    )
    st.selectbox(
        "cppcheck 언어 표준",
        ["c++03", "c++17"],
        key="dlg_cpp_standard",
        help="VS 2008 소스는 c++03이 맞습니다.",
    )
    st.markdown("**벡터 검색 (ChromaDB + BGE-M3)**")
    st.checkbox(
        "벡터 검색 사용 (샘플·헤더·소스 RAG)",
        key="dlg_vector_search",
        help="켜면 BGE-M3(CPU)+Chroma로 샘플 few-shot, 헤더 심볼 보충, 프로젝트 소스 RAG를 씁니다. "
        "임베딩은 CPU라 GPU VRAM을 거의 쓰지 않습니다. 다만 관련 소스·샘플이 프롬프트에 붙어 "
        "첫 토큰(prefill)이 길어질 수 있습니다. 꺼지면 키워드·exact·정규식만 씁니다.",
    )
    try:
        from vector_store import (
            last_error,
            rebuild_header_symbol_index,
            rebuild_sample_index,
            rebuild_source_chunk_index,
            status_all,
        )

        all_status = status_all()
        if all_status["available"]:
            samples = all_status["samples"]
            headers = all_status["headers"]
            sources = all_status["sources"]
            st.caption(
                f"저장: {all_status['persist_dir']} · {all_status['embed_model']}({all_status['device']}) · "
                f"샘플 {samples.get('indexed_count', 0)} · 헤더 {headers.get('indexed_count', 0)} · "
                f"소스 {sources.get('indexed_count', 0)}"
            )
            sample_col, header_col, source_col = st.columns(3)
            if sample_col.button("샘플 재구축", type="secondary", use_container_width=True):
                with st.spinner("샘플 벡터 인덱스 재구축 중"):
                    rebuilt = rebuild_sample_index(load_samples())
                st.success(f"샘플 {rebuilt['indexed_count']}건")
            if header_col.button("헤더 재구축", type="secondary", use_container_width=True):
                with st.spinner("헤더 심볼 벡터 인덱스 재구축 중"):
                    rebuilt = rebuild_header_symbol_index()
                st.success(f"헤더 {rebuilt.get('count', 0)}건")
            if source_col.button("소스 재구축", type="secondary", use_container_width=True):
                root_text = str(st.session_state.get("project_root") or "").strip()
                if not root_text:
                    st.warning("메인 화면의 프로젝트 루트를 먼저 입력하세요.")
                else:
                    with st.spinner("프로젝트 소스 RAG 인덱스 재구축 중"):
                        rebuilt = rebuild_source_chunk_index(Path(root_text))
                    st.success(f"소스 청크 {rebuilt.get('count', 0)}건 · 파일 {rebuilt.get('files', 0)}개")
            if sources.get("root"):
                st.caption(f"소스 인덱스 루트: {sources['root']}")
        else:
            st.warning("chromadb / sentence-transformers 미설치. pip install -r requirements.txt 후 재시작하세요.")
        if last_error():
            st.caption(f"최근 오류: {last_error()}")
    except Exception as error:  # noqa: BLE001
        st.caption(f"벡터 상태 확인 실패: {error}")
    st.caption("닫기를 누르면 선택 내용이 저장됩니다.")
    if st.button("닫기", type="primary"):
        _commit_options_from_dialog()
        st.session_state["_open_options"] = False
        st.rerun()


if st.session_state.get("_open_options"):
    options_dialog()


def _server_config_from_state() -> dict:
    """화면의 노트북 접속 값을 설정 dict로 모은다."""
    return {
        "host": str(st.session_state.get("server_host") or ""),
        "port": int(st.session_state.get("server_port") or 22),
        "user": str(st.session_state.get("server_user") or ""),
        "key": str(st.session_state.get("server_key") or ""),
        "remote_path": str(st.session_state.get("server_remote_path") or ""),
        "local_dir": str(st.session_state.get("server_local_dir") or ""),
    }


def _ensure_server_settings() -> None:
    """저장된 노트북 SFTP 접속 정보를 세션에 올린다."""
    if st.session_state.get("server_settings_version") == 2:
        return
    config = load_server_config()
    st.session_state.server_host = config["host"]
    st.session_state.server_port = int(config["port"])
    st.session_state.server_user = config["user"]
    st.session_state.server_key = config["key"]
    st.session_state.server_remote_path = config["remote_path"]
    st.session_state.server_local_dir = config["local_dir"]
    st.session_state.server_password = ""
    st.session_state.server_settings_version = 2


@st.dialog("서버 설정")
def server_dialog() -> None:
    """노트북 SFTP 서버 접속 정보를 저장하고, 접속과 파일 받기를 확인한다."""
    _ensure_server_settings()
    st.caption("이 PC는 SFTP 클라이언트입니다. 노트북에서 OpenSSH 서버가 떠 있어야 파일을 받을 수 있습니다.")
    st.text_input("노트북 주소", key="server_host")
    st.number_input("SSH 포트", min_value=1, max_value=65535, step=1, key="server_port")
    st.text_input("사용자", key="server_user")
    st.text_input("개인키 파일", key="server_key", help="비우면 ssh-agent 또는 아래 비밀번호를 씁니다.")
    st.text_input("비밀번호", type="password", key="server_password", help="저장하지 않습니다. 이번 확인에만 씁니다.")
    st.text_input("원격 파일", key="server_remote_path", help="노트북에 있는 소스 파일 하나. 예: C:/work/sample.cpp")
    st.text_input("받을 폴더", key="server_local_dir", help="이 PC에 파일을 저장할 폴더입니다.")
    save_column, check_column, fetch_column = st.columns(3)
    if save_column.button("저장", type="primary"):
        try:
            save_server_config(_server_config_from_state())
        except OSError as error:
            st.error(f"설정을 저장하지 못했습니다: {error}")
        else:
            st.success("저장했습니다.")
    if check_column.button("상태 확인"):
        st.session_state.server_status_rows = collect_server_status(
            str(st.session_state.ollama_url),
            _server_config_from_state(),
            str(st.session_state.server_password),
        )
    if fetch_column.button("파일 받기"):
        try:
            saved = download_remote_file(_server_config_from_state(), str(st.session_state.server_password))
        except Exception as error:
            st.error(str(error))
        else:
            st.success(f"받았습니다: {saved}")
    for row in st.session_state.get("server_status_rows") or []:
        if row["ok"]:
            st.success(f"{row['name']}: {row['detail']}")
        else:
            st.error(f"{row['name']}: {row['detail']}")
    if st.button("닫기", key="server-close"):
        st.session_state["_open_server"] = False
        st.rerun()


if st.session_state.get("_open_server"):
    server_dialog()


@st.dialog("보안점검 — 로컬 폐쇄성 검증")
def security_audit_dialog() -> None:
    """네트워크 격리·아웃바운드·텔레메트리/소스 감사를 증빙한다."""
    from security_audit import manual_checklist, run_security_audit

    st.caption(
        "로컬 LLM(Qwen/Llama)+RAG가 외부로 데이터를 보내지 않는지 "
        "①격리 테스트 안내 ②netstat 감시 ③소스·텔레메트리 감사로 검증합니다."
    )
    tab1, tab2, tab3 = st.tabs(["1. 격리 테스트", "2. 아웃바운드 감시", "3. 코드·텔레메트리"])

    with tab1:
        st.markdown(
            """
**가장 확실한 증빙**
1. Ollama 모델·BGE-M3 캐시를 미리 받아 둔다.  
2. Wi-Fi/랜을 끊거나 비행기 모드로 **완전 오프라인** 한다.  
3. `START.bat` → `http://127.0.0.1:8501` 에서 소스 검토(RAG+LLM)를 실행한다.  

**판정:** 오프라인에서 에러 없이 분석되면 로컬 자원만 사용한 것이다.  
`ConnectionError` / HuggingFace 접속 실패가 나면 외부 호출 경로를 고쳐야 한다.
            """.strip()
        )
        for item in manual_checklist():
            if item["id"] == "offline":
                st.checkbox(item["title"], key=f"sec_chk_{item['id']}", help=item["detail"])

    with tab2:
        st.markdown(
            """
분석 실행 중 관리자 CMD에서:

`netstat -ano | findstr ESTABLISHED`

python.exe / ollama.exe PID의 원격 주소가 **127.0.0.1·사설망만**이면 정상.  
공인 IP가 ESTABLISHED면 유출 의심.

선택: Windows 방화벽에서 python.exe·ollama.exe **아웃바운드 차단** 후에도 분석되면 외부 경로는 봉쇄된 것.
            """.strip()
        )
        for item in manual_checklist():
            if item["id"] in {"netstat", "firewall"}:
                st.checkbox(item["title"], key=f"sec_chk_{item['id']}", help=item["detail"])

    with tab3:
        st.markdown(
            """
자동 점검 항목:
- `ANONYMIZED_TELEMETRY` / `HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE`
- `.streamlit/config.toml` → `gatherUsageStats = false`, bind `127.0.0.1`
- 프로젝트 `.py` 외부 URL·상용 AI API 엔드포인트 문자열 스캔
- Ollama URL이 로컬인지
- netstat 스냅샷(공인 IP ESTABLISHED)
            """.strip()
        )
        for item in manual_checklist():
            if item["id"] in {"telemetry", "ollama_bind"}:
                st.checkbox(item["title"], key=f"sec_chk_{item['id']}", help=item["detail"])

    run_col, close_col = st.columns(2)
    if run_col.button("자동 점검 실행", type="primary", use_container_width=True):
        with st.spinner("보안 점검 중"):
            report = run_security_audit(ollama_url=str(st.session_state.get("ollama_url") or DEFAULT_OLLAMA_URL))
        st.session_state["security_report"] = report
        if report.get("auto_ok"):
            st.success(report.get("summary") or "자동 항목 통과")
        else:
            st.warning(report.get("summary") or "주의 항목 있음")
        st.caption(f"증빙: {report.get('md_path')}")

    report = st.session_state.get("security_report")
    if report:
        st.write(
            f"자동 판정: {'통과' if report.get('auto_ok') else '주의'} · "
            f"인터넷 지금: {'연결' if report.get('internet_now') else '오프라인'} · "
            f"소스 findings {len((report.get('source_scan') or {}).get('findings') or [])}건 · "
            f"netstat 의심 {len((report.get('netstat') or {}).get('suspects') or [])}건"
        )
        findings = (report.get("source_scan") or {}).get("findings") or []
        if findings:
            st.dataframe(pd.DataFrame(findings), use_container_width=True, hide_index=True)
        suspects = (report.get("netstat") or {}).get("suspects") or []
        if suspects:
            st.error("공인 IP ESTABLISHED 감지")
            st.dataframe(pd.DataFrame(suspects), use_container_width=True, hide_index=True)
        env_rows = (report.get("env") or {}).get("rows") or []
        if env_rows:
            st.dataframe(pd.DataFrame(env_rows), use_container_width=True, hide_index=True)
        md_path = Path(report.get("md_path") or "")
        if md_path.is_file():
            st.download_button(
                "증빙 마크다운 받기",
                md_path.read_bytes(),
                file_name=md_path.name,
                mime="text/markdown",
            )

    if close_col.button("닫기", use_container_width=True):
        st.session_state["_open_security"] = False
        st.rerun()


if st.session_state.get("_open_security"):
    security_audit_dialog()


@st.dialog("DB(헤더) 전처리")
def header_preprocess_dialog() -> None:
    """CPP가 쓰는 struct/typedef만 추려 슬림 헤더를 만든다."""
    from header_preprocess import MAX_SELECT, OUT_DIR, preprocess_headers

    st.caption(
        f"이미 전처리된 헤더·CPP를 각각 최대 {MAX_SELECT}개까지 고릅니다. "
        f"CPP 기준으로 struct/typedef만 남겨 `{OUT_DIR.name}/`에 저장합니다."
    )
    if "prep_headers" not in st.session_state:
        st.session_state.prep_headers = []
    if "prep_cpps" not in st.session_state:
        st.session_state.prep_cpps = []

    header_col, cpp_col = st.columns(2)
    if header_col.button("헤더 선택", use_container_width=True):
        chosen = _choose_files(
            "헤더 선택 (최대 5개)",
            [("Header", "*.h *.hpp *.hh *.hxx"), ("All", "*.*")],
            max_count=MAX_SELECT,
        )
        if chosen:
            st.session_state.prep_headers = chosen
            st.rerun()
    if cpp_col.button("CPP 선택", use_container_width=True):
        chosen = _choose_files(
            "CPP 선택 (최대 5개)",
            [("C/C++", "*.c *.cc *.cpp *.cxx"), ("All", "*.*")],
            max_count=MAX_SELECT,
        )
        if chosen:
            st.session_state.prep_cpps = chosen
            st.rerun()

    headers = list(st.session_state.get("prep_headers") or [])
    cpps = list(st.session_state.get("prep_cpps") or [])
    st.write("헤더:", ", ".join(Path(p).name for p in headers) or "(없음)")
    st.write("CPP:", ", ".join(Path(p).name for p in cpps) or "(없음)")

    run_col, close_col = st.columns(2)
    if run_col.button("추출 실행", type="primary", use_container_width=True, disabled=not (headers and cpps)):
        try:
            with st.spinner("슬림 헤더 생성 중"):
                result = preprocess_headers(
                    [Path(p) for p in headers],
                    [Path(p) for p in cpps],
                )
            st.session_state["prep_result"] = result
            st.success(
                f"심볼 {result['picked_count']}개 / 헤더 전체 {result['header_symbol_total']}개 → "
                f"{result['out_path']}"
            )
            st.write("포함:", ", ".join(result.get("picked_names") or []) or "(없음)")
        except ValueError as error:
            st.error(str(error))
        except OSError as error:
            st.error(f"저장 실패: {error}")
    if close_col.button("닫기", use_container_width=True):
        st.session_state["_open_header_prep"] = False
        st.rerun()


if st.session_state.get("_open_header_prep") and st.session_state.get("screen") == "헤더 인덱스":
    header_preprocess_dialog()


def render_header_index() -> None:
    """설정 파일의 헤더 루트를 보여주고, SQLite 심볼 인덱스를 만들거나 갱신한다."""
    from symbol_index import build_index, index_status, load_config, save_header_roots

    config = load_config()
    if st.session_state.get("header_roots_version") != 3:
        st.session_state.header_roots_text = "\n".join(config["header_roots"])
        st.session_state.header_roots_version = 2
    if st.session_state.get("context_budget_version") != 1:
        st.session_state.context_token_budget = min(4096, max(1500, int(config["context_token_budget"])))
        st.session_state.context_budget_version = 1
    st.caption("헤더 파일은 하나씩 고르지 않습니다. 아래 루트는 config/index.yaml 에 저장되고, 그 안의 헤더만 인덱싱합니다.")
    prep_col, _ = st.columns([1, 3])
    if prep_col.button("DB(헤더) 전처리", type="secondary", use_container_width=True):
        _close_all_dialogs(keep="_open_header_prep")
        st.session_state["_open_header_prep"] = True
        st.rerun()
    prev = st.session_state.get("prep_result")
    if prev:
        st.caption(f"최근 전처리: {prev.get('picked_count', 0)}심볼 → {prev.get('out_path', '')}")
    st.text_area("헤더 루트", key="header_roots_text", height=120, help="한 줄에 폴더 하나. 예: D:\\Work\\src")
    save_column, budget_column = st.columns([1, 2], vertical_alignment="bottom")
    budget_column.number_input(
        "토큰 예산",
        min_value=1500,
        max_value=4096,
        step=1,
        key="context_token_budget",
        help="함수에 붙이는 헤더 컨텍스트의 최대 토큰입니다. 1500부터 4096까지입니다.",
    )
    chosen_budget = int(st.session_state.context_token_budget)
    if chosen_budget != int(load_config()["context_token_budget"]):
        save_header_roots(load_config()["header_roots"], budget=chosen_budget)
    if save_column.button("경로 저장", use_container_width=True):
        save_header_roots(
            [line.strip() for line in st.session_state.header_roots_text.splitlines() if line.strip()],
            budget=chosen_budget,
        )
        st.success("헤더 루트와 토큰 예산을 저장했습니다.")
    build_column, update_column = st.columns(2)

    def run_index(full: bool) -> None:
        roots = [line.strip() for line in st.session_state.header_roots_text.splitlines() if line.strip()]
        save_header_roots(roots, budget=int(st.session_state.context_token_budget))
        result = build_index(full=full)
        missing = result.get("missing_roots") or []
        if missing:
            st.session_state["index_error"] = (
                "폴더를 찾지 못했습니다: "
                + ", ".join(missing)
                + ". 헤더 파일명은 적지 않습니다. 헤더가 들어 있는 폴더 경로만 적으면 하위 폴더까지 읽습니다."
            )
            st.session_state["index_notice"] = ""
            return
        chroma_n = result.get("chroma_headers")
        chroma_note = f", Chroma 헤더 {chroma_n}건" if chroma_n is not None else ""
        chroma_err = result.get("chroma_error")
        st.session_state["index_error"] = ""
        st.session_state["index_notice"] = (
            f"갱신 {result['updated']}개, 그대로 {result['unchanged']}개{chroma_note}"
        )
        if chroma_err:
            st.session_state["index_chroma_error"] = str(chroma_err)

    if build_column.button("전체 인덱싱", type="primary"):
        with st.spinner("헤더 심볼을 다시 만드는 중"):
            run_index(True)
    if update_column.button("변경분만 갱신"):
        with st.spinner("바뀐 헤더만 다시 읽는 중"):
            run_index(False)
    error = st.session_state.pop("index_error", "")
    if error:
        st.error(error)
    notice = st.session_state.pop("index_notice", "")
    if notice:
        st.success(notice)
    chroma_error = st.session_state.pop("index_chroma_error", "")
    if chroma_error:
        st.warning(f"Chroma 헤더 동기화 실패: {chroma_error}")
    status = index_status()
    chroma_headers = 0
    try:
        from vector_store import status_all

        chroma_headers = int(status_all()["headers"].get("indexed_count") or 0)
    except Exception:
        chroma_headers = 0
    st.write(
        f"인덱스 파일 {status['files']}개, 심볼 {status['symbols']}개"
        f"(Chroma {chroma_headers}건). "
        f"예산 {int(st.session_state.context_token_budget)}토큰."
    )
    if not status["roots"]:
        st.info("헤더 루트가 비어 있습니다. 폴더를 저장한 뒤 인덱싱하세요. 그때까지 검토는 기존 정규식 헤더 조회를 사용합니다.")
    for item in status["skipped"]:
        st.warning(f"{item['path']}: {item['message']}")


def render_sample_admin() -> None:
    """MD 파일로 버그 샘플을 등록하고, 목록을 관리한다."""
    st.subheader("샘플 학습 관리")
    st.caption(
        "수기 입력 대신 MD 파일로 등록합니다. "
        "다음 검토부터 키워드·벡터로 맞는 샘플을 종류별로 고르게, 최대 12개까지 프롬프트에 넣습니다."
    )
    notice = st.session_state.pop("sample_notice", None)
    if notice:
        st.success(notice)
    try:
        samples = load_samples()
    except ValueError as error:
        st.error(str(error))
        return

    st.markdown("**MD로 샘플 등록**")
    st.caption(
        "필수 절: `## 버그 종류` · `## 키워드` · `## 문제 코드` · `## 수정 코드` · `## 해설` · "
        "`## 오탐 방지`(예/아니오). 여러 건은 `---` 로 구분합니다."
    )
    samples_dir = Path("samples")
    local_mds = sorted(samples_dir.glob("*.md")) if samples_dir.is_dir() else []
    if local_mds:
        pick = st.selectbox(
            "프로젝트 samples/ 폴더에서 선택",
            options=[""] + [path.name for path in local_mds],
            format_func=lambda name: "(선택)" if not name else name,
            key="sample_md_local_pick",
        )
    else:
        pick = ""
    tmpl_col, _ = st.columns([1, 2])
    tmpl_col.download_button(
        "MD 템플릿 받기",
        SAMPLE_MD_TEMPLATE.encode("utf-8"),
        file_name="bug_sample_template.md",
        mime="text/markdown",
    )
    md_files = st.file_uploader(
        "MD 파일 선택 (여러 개 가능)",
        type=["md", "markdown"],
        accept_multiple_files=True,
        key="sample_md_import",
    )
    replace_md = st.checkbox("등록 시 기존 샘플을 모두 교체", key="sample_md_replace")
    can_register = bool(md_files) or bool(pick)
    if st.button("MD 등록", type="primary", disabled=not can_register):
        total = 0
        try:
            with st.spinner("MD 등록 중… (벡터 인덱스는 마지막에 한 번만 맞춥니다)"):
                texts: list[str] = []
                if pick:
                    texts.append((samples_dir / pick).read_text(encoding="utf-8-sig"))
                for item in md_files or []:
                    texts.append(item.getvalue().decode("utf-8-sig"))
                if replace_md:
                    first, *rest = texts
                    total += import_samples_from_markdown(first, replace=True)
                    for text in rest:
                        total += import_samples_from_markdown(text, replace=False)
                else:
                    for text in texts:
                        total += import_samples_from_markdown(text, replace=False)
        except (UnicodeDecodeError, ValueError, OSError) as error:
            st.error(f"MD 등록 실패: {error}")
        except Exception as error:
            st.error(f"MD 등록 중 오류: {error}")
        else:
            st.session_state["sample_notice"] = f"MD에서 샘플 {total}건을 등록했습니다."
            st.rerun()

    with st.expander("JSON 백업(선택)"):
        export_col, import_col = st.columns(2)
        if SAMPLES_PATH.exists():
            export_col.download_button(
                "JSON 내보내기",
                SAMPLES_PATH.read_bytes(),
                file_name="bug_samples.json",
                mime="application/json",
            )
        uploaded = import_col.file_uploader("JSON 불러오기", type=["json"], key="sample_import")
        replace = st.checkbox("JSON 불러올 때 기존 샘플을 모두 교체", key="sample_json_replace")
        if st.button("JSON 불러오기", disabled=uploaded is None):
            try:
                payload = json.loads(uploaded.getvalue().decode("utf-8-sig"))
                count = import_samples(payload, replace)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                st.error(f"불러오지 못했습니다: {error}")
            else:
                st.session_state["sample_notice"] = f"샘플 {count}건을 불러왔습니다."
                st.rerun()

    st.write(f"등록된 샘플 {len(samples)}건")
    if not samples:
        st.info("등록된 샘플이 없습니다.")
    for sample in samples:
        label = f"{sample['id']}. {sample['category']}"
        if sample["is_false_positive"]:
            label += " · 오탐 방지"
        with st.expander(label):
            st.write("키워드: " + ", ".join(sample["keywords"]))
            st.markdown("**문제 코드**")
            st.code(sample["bad_code"] or "")
            st.markdown("**수정 코드**")
            st.code(sample["good_code"] or "")
            if sample["explanation"]:
                st.write(sample["explanation"])
            if st.button("삭제", key=f"delete-sample-{sample['id']}"):
                delete_sample(sample["id"])
                st.session_state["sample_notice"] = f"샘플 {sample['id']}을 삭제했습니다."
                st.rerun()


def render_whitelist_admin() -> None:
    """초기화로 인정할 함수와 모듈 진입 함수를 화면에서 넣고 뺀다."""
    st.subheader("초기화 화이트리스트")
    st.caption("여기에 없는 함수에 주소를 넘긴 것은 초기화로 보지 않습니다. 저장은 버튼을 누르는 즉시 반영됩니다.")
    try:
        data = load_whitelist()
    except ValueError as error:
        st.error(str(error))
        return
    left, right = st.columns(2)
    with left:
        st.markdown("**초기화로 인정할 함수/매크로**")
        init_name = st.text_input("함수 이름", key="init_name", placeholder="memset")
        if st.button("초기화 함수 추가", type="primary"):
            try:
                created = add_name("init_functions", init_name)
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state["sample_notice"] = "추가했습니다." if created else "이미 등록된 함수입니다."
                st.rerun()
        for name in data["init_functions"]:
            column_name, column_button = st.columns([3, 1])
            column_name.write(name)
            if column_button.button("삭제", key=f"init-del-{name}"):
                remove_name("init_functions", name)
                st.rerun()
    with right:
        st.markdown("**초기화 진입 함수**")
        entry_name = st.text_input("진입 함수", key="entry_name", placeholder="Init")
        if st.button("진입 함수 추가"):
            try:
                created = add_name("entry_functions", entry_name)
            except ValueError as error:
                st.error(str(error))
            else:
                st.session_state["sample_notice"] = "추가했습니다." if created else "이미 등록된 함수입니다."
                st.rerun()
        for name in data["entry_functions"]:
            column_name, column_button = st.columns([3, 1])
            column_name.write(name)
            if column_button.button("삭제", key=f"entry-del-{name}"):
                remove_name("entry_functions", name)
                st.rerun()


profile = hardware_profile(st.session_state.vram, st.session_state.ram)

if screen == "헤더 인덱스":
    render_header_index()
    st.stop()
if screen == "샘플 학습 관리":
    render_sample_admin()
    st.stop()
if screen == "초기화 화이트리스트":
    render_whitelist_admin()
    st.stop()

online = ollama_reachable(st.session_state.ollama_url)
models = installed_models(st.session_state.ollama_url) if online else []
# 다른 화면을 갔다 오면 입력칸이 비워진 채 다시 그려진다. 저장값을 다시 넣어 주소가 보이게 한다.
st.session_state.ollama_url = str(st.session_state.ollama_url).strip() or DEFAULT_OLLAMA_URL
analysis_model = st.session_state.model_name.strip() or DEFAULT_MODEL
_ollama_opts = ollama_call_options(
    st.session_state.vram,
    st.session_state.ram,
    int(st.session_state.num_predict),
    analysis_model,
)
review_num_ctx = int(_ollama_opts["num_ctx"])
review_think_mode = normalize_think_mode(st.session_state.get("think_mode"))
standard = str(st.session_state.get("cpp_standard") or "c++03")
model_missing = bool(models) and analysis_model not in models


@st.fragment(run_every=2)
def show_guide_command_panel() -> None:
    """안내 캔버스를 커맨드센터 패널로 2초마다 갱신한다."""
    if "guide_mem_hist" not in st.session_state:
        st.session_state.guide_mem_hist = []
    if "guide_cpu_hist" not in st.session_state:
        st.session_state.guide_cpu_hist = []
    model_name = str(st.session_state.get("model_name") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    host = sample_host()
    st.session_state.guide_mem_hist = (list(st.session_state.guide_mem_hist) + [host.ram_percent])[-40:]
    st.session_state.guide_cpu_hist = (list(st.session_state.guide_cpu_hist) + [host.system_cpu])[-40:]
    markup, _ = render_command_panel(
        model_name=model_name,
        online=bool(st.session_state.get("_guide_online")),
        cppcheck_ok=bool(st.session_state.get("_guide_cppcheck")),
        vram_label=VRAM_LABELS.get(str(st.session_state.get("vram") or "8"), "8GB"),
        ram_label=RAM_LABELS.get(str(st.session_state.get("ram") or "16"), "16GB"),
        mem_history=st.session_state.guide_mem_hist,
        cpu_history=st.session_state.guide_cpu_hist,
        host=host,
        shared_memory=bool(st.session_state.get("shared_memory")),
    )
    st.markdown(markup, unsafe_allow_html=True)


@st.fragment(run_every=2)
def show_ollama_cpu() -> None:
    """상태 캔버스의 Ollama CPU만 2초마다 갱신한다."""
    _, ollama_cpu = sample_cpu()
    st.metric("Ollama CPU", "없음" if ollama_cpu is None else f"{ollama_cpu:.0f}%")


st.session_state["_guide_online"] = online
st.session_state["_guide_cppcheck"] = bool(cppcheck_path())
guide_column, status_column = st.columns(2, gap="medium")
with guide_column:
    with st.container(border=True, key="guide_canvas", height=460):
        show_guide_command_panel()
with status_column:
    with st.container(border=True, key="status_canvas", height=460):
        st.markdown("##### 상태")
        if online:
            st.success("Ollama 연결됨")
        else:
            st.error("Ollama가 실행 중이지 않습니다. START.bat으로 준비하세요.")
        show_ollama_cpu()
        analysis_name = str(st.session_state.get("model_name") or DEFAULT_MODEL)
        if is_qwen3_model(analysis_name):
            mode = normalize_think_mode(st.session_state.get("think_mode"))
            call_note = (
                f"Qwen3 {mode} · num_ctx {_ollama_opts['num_ctx']} · "
                + ("think=false" if mode == "FAST" else "AUTO/Thinking")
            )
            if str(st.session_state.get("vram") or "") == "11":
                st.warning(
                    "11GB에서 qwen3:14b는 VRAM이 거의 꽉 차 초당 ~2토큰·첫 토큰 지연이 큽니다. "
                    "속도가 우선이면 분석 모델을 qwen2.5-coder:7b로 바꾸세요. "
                    "RAG(BGE-M3)는 CPU라 이 VRAM 점유의 원인이 아닙니다."
                )
        else:
            call_note = (
                f"temperature 0, num_ctx {_ollama_opts['num_ctx']}, "
                f"num_batch {_ollama_opts.get('num_batch', 512)}"
            )
        st.info(
            f"그래픽 {VRAM_LABELS[st.session_state.vram]} · 메인 {RAM_LABELS[st.session_state.ram]} · "
            f"권장 {profile['model']} · 호출은 {call_note}, "
            f"num_predict {st.session_state.num_predict}, num_thread 8"
        )
        st.text_input("Ollama 주소", key="ollama_url")


with st.container(border=True, key="work_canvas"):
    st.markdown("##### 검토 작업")
    if model_missing:
        st.error(
            f"{analysis_model} 모델이 이 PC에 없어 검토를 시작하지 않습니다. "
            f"헤더의 옵션에서 모델을 바꾸거나 아래에서 받으세요. 설치된 모델: {', '.join(models)}"
        )
        if st.button(f"{analysis_model} 받기", type="primary"):
            _pull_model(analysis_model)
    warned_models = {analysis_model}
    optional_models = ["deepseek_model", "llama_model"]
    for model_key in optional_models:
        chosen_model = st.session_state[model_key].strip()
        if not models or not chosen_model or chosen_model in models or chosen_model in warned_models:
            continue
        warned_models.add(chosen_model)
        st.warning(
            f"{chosen_model} 이 아직 없습니다. 헤더 옵션에서 바꾸거나 터미널에서 ollama pull {chosen_model} 을 실행하세요."
        )

    uploads = st.file_uploader(
        "소스 파일",
        type=["c", "cc", "cpp", "cxx", "h", "hh", "hpp", "hxx"],
        accept_multiple_files=True,
    )
    folder_input, folder_button = st.columns([4, 1])
    folder_input.text_input(
        "프로젝트 루트 폴더",
        key="project_root",
        placeholder=r"D:\work\src",
        help="이 폴더에서 .cpp를 찾고, #include \"파일.h\" 헤더의 구조체와 매크로를 읽습니다.",
    )
    if folder_button.button("폴더 선택", use_container_width=True):
        chosen_folder = _choose_project_folder()
        if chosen_folder:
            st.session_state["_pending_root"] = chosen_folder
            st.rerun()
    note = st.text_area(
        "요청",
        value="이 소스의 메모리 버그와 초기화 버그를 찾아 주세요.",
        height=80,
        key="review_note",
    )
    st.caption("사내 SAFE_FREE 같은 매크로는 memory_rules.txt에 적습니다. 명령줄은 py -3 cli.py 파일.cpp 입니다.")

    def show_review(result: dict) -> None:
        """저장된 검토 결과를 표, 수정 제안, 다운로드 버튼으로 보여 준다."""
        stats = result.get("scan_stats") or {}
        if stats:
            rag_n = stats.get("source_rag_chunks")
            rag_note = f", 소스 RAG {rag_n}청크" if rag_n is not None else ""
            st.write(
                f"함수 {stats.get('functions', 0)}개 중 소거 {stats.get('pruned', 0)}개, "
                f"분석 창 {stats.get('windows', len(result['chunks']))}개{rag_note}"
            )
            if stats.get("source_rag_error"):
                st.caption(f"소스 RAG: {stats['source_rag_error']}")
        for note_text in result.get("stage_notes") or []:
            st.info(note_text)
        if result.get("think_mode") or result.get("executed_stages"):
            stages = ", ".join(result.get("executed_stages") or []) or "-"
            st.caption(f"Qwen3 모드 {result.get('think_mode') or '-'} · 실행 단계 {stages}")
        if result.get("think_logs"):
            with st.expander(f"Thinking 로그 {len(result['think_logs'])}개"):
                for path in result["think_logs"]:
                    st.code(path)
        if result.get("unconfirmed") and result.get("findings"):
            st.warning("교차 검증이 끝나지 않았습니다. 아래 목록만으로 정상이라고 보지 않습니다.")
        st.write(f"모델에 넘긴 함수 조각 {len(result['chunks'])}개")
        with st.expander("cppcheck"):
            st.code(result["report"] or "결과 없음")
        with st.expander("모델에 넘긴 코드"):
            for chunk in result["chunks"]:
                injected = chunk.get("injected_samples") or []
                names = ", ".join(
                    (
                        f"{item['id']}. {item['category']}"
                        + (" (정상)" if item["is_false_positive"] else "")
                        + (
                            f" [{item.get('select_reason')}"
                            + (
                                f":{item.get('select_score')}"
                                if item.get("select_score") is not None
                                else ""
                            )
                            + "]"
                            if item.get("select_reason")
                            else ""
                        )
                    )
                    for item in injected
                )
                header_note = "헤더 정의 포함" if chunk.get("headers") else "헤더 정의 없음"
                omitted = ", ".join(chunk.get("context_omitted") or [])
                related = chunk.get("related_sources") or []
                related_note = ", ".join(
                    f"{item.get('file_name')}:{item.get('function_name')}"
                    + (
                        f"({float(item.get('score')):.2f})"
                        if isinstance(item.get("score"), (int, float))
                        else ""
                    )
                    for item in related
                )
                st.code(
                    f"{chunk['file']} {chunk.get('function_name', '')} {chunk['start']}-{chunk['end']} / {header_note}\n"
                    f"넣은 컨텍스트: {', '.join(chunk.get('context_included') or []) or '없음'}\n"
                    f"미포함 컨텍스트: {omitted or '없음'}\n"
                    f"관련 소스 RAG: {related_note or '없음'}\n"
                    f"주입한 예제: {names or '없음'}\n{chunk.get('headers') or ''}\n{chunk['text']}"
                )
        markdown_path = Path(result["markdown_path"]) if result.get("markdown_path") else None
        csv_path = Path(result["csv_path"]) if result.get("csv_path") else None
        if markdown_path and csv_path and markdown_path.exists() and csv_path.exists():
            st.success(f"리포트 저장: {markdown_path.parent}")
            left_button, right_button = st.columns(2)
            left_button.download_button(
                "마크다운 받기",
                markdown_path.read_bytes(),
                file_name=markdown_path.name,
                mime="text/markdown",
            )
            right_button.download_button(
                "CSV 받기",
                csv_path.read_bytes(),
                file_name=csv_path.name,
                mime="text/csv",
            )
        if result["rejected"]:
            st.warning(result["reject_reason"] or "메모리 버그와 초기화 버그 검토 요청만 처리합니다.")
            return
        if not result["findings"]:
            if result.get("unconfirmed"):
                st.warning("교차 검증이 끝나지 않았습니다. 정상이라고 확정하지 않습니다.")
            else:
                st.success("보고할 메모리 버그와 초기화 버그가 없습니다.")
            return
        table = pd.DataFrame(
            [
                {
                    "파일명": finding["file"],
                    "줄 번호": finding["line"],
                    "함수명": finding.get("function_name", ""),
                    "버그 종류": BUG_LABELS.get(finding["bug_type"], finding["bug_type"]),
                    "확신도": {"high": "High", "medium": "Medium", "low": "Low"}.get(
                        finding["confidence"], finding["confidence"]
                    ),
                }
                for finding in result["findings"]
            ]
        )
        st.dataframe(table, hide_index=True, use_container_width=True)
        for index, finding in enumerate(result["findings"]):
            title = f"{finding['file']}:{finding['line']} {finding.get('function_name', '')}"
            with st.expander(title):
                st.markdown("**현재 코드 (Before)**")
                st.code(finding.get("before_code") or "")
                st.markdown("**수정 방향 및 제안 코드 (After)**")
                st.code(finding.get("after_code") or finding.get("summary") or "")
                if finding.get("summary"):
                    st.write(finding["summary"])
                if finding.get("before_code"):
                    if st.button("정상 코드로 예외 등록", key=f"fp-{index}-{finding['file']}-{finding['line']}"):
                        try:
                            _, created = register_false_positive(
                                finding["before_code"],
                                finding.get("function_name", ""),
                                finding.get("summary", ""),
                            )
                        except ValueError as error:
                            st.error(str(error))
                        else:
                            st.session_state["sample_notice"] = (
                                "정상 패턴으로 등록했습니다. 다음 검토부터 같은 키워드에서는 버그로 보고하지 않습니다."
                                if created
                                else "같은 정상 패턴이 이미 등록되어 있습니다."
                            )
                            st.rerun()
                function_name = finding.get("function_name") or ""
                if function_name:
                    if st.button("이 함수를 초기화 화이트리스트에 추가", key=f"wl-{index}-{finding['file']}-{finding['line']}"):
                        try:
                            created = add_name("init_functions", function_name)
                        except ValueError as error:
                            st.error(str(error))
                        else:
                            st.session_state["sample_notice"] = (
                                f"{function_name}을 초기화 인정 함수에 넣었습니다."
                                if created
                                else f"{function_name}은 이미 초기화 인정 함수입니다."
                            )
                            st.rerun()


    review_col, time_col = st.columns([2, 3], vertical_alignment="center")
    start_review = review_col.button(
        "메모리·초기화 버그 검토",
        type="primary",
        disabled=not online or model_missing,
        use_container_width=True,
    )
    time_slot = time_col.empty()
    last_timing = st.session_state.get("last_review_timing") or {}
    if last_timing.get("elapsed") is not None:
        time_slot.markdown(f"**⏱ {_format_stopwatch(float(last_timing['elapsed']))}**")
    else:
        time_slot.markdown("**⏱ 00:00**")

    if start_review:
        targets: list[Path] = []
        temp_dir = None
        project_text = st.session_state.project_root.strip()
        project_root = Path(project_text) if project_text else None
        if uploads:
            temp_dir = tempfile.TemporaryDirectory()
            root = Path(temp_dir.name)
            for item in uploads:
                destination = root / Path(item.name).name
                destination.write_bytes(item.getvalue())
                targets.append(destination)
        elif project_root is not None:
            targets.append(project_root)
        if not targets:
            st.warning("파일 또는 프로젝트 폴더를 지정하세요.")
        else:
            progress = st.progress(0, text="진행 0% · ⏱ 00:00 · cppcheck로 함수를 나누는 중")
            shown = {"percent": 0.0, "label": "cppcheck로 함수를 나누는 중"}
            started_at = time.monotonic()
            stop_clock = threading.Event()
            time_slot.markdown("**⏱ 00:00**")

            def _paint_clock(force_label: str | None = None) -> str:
                elapsed = time.monotonic() - started_at
                clock = _format_stopwatch(elapsed)
                label = force_label if force_label is not None else shown["label"]
                time_slot.markdown(f"**⏱ {clock}**")
                progress.progress(
                    shown["percent"] / 100.0,
                    text=f"진행 {shown['percent']:.0f}% · ⏱ {clock} · {cpu_label()} · {label}",
                )
                return clock

            def on_progress(percent: float, label: str) -> None:
                shown["percent"] = max(0.0, min(float(percent), 100.0))
                shown["label"] = label
                _paint_clock(label)

            def _clock_heartbeat() -> None:
                """진행 콜백이 없어도 1초마다 스톱워치를 갱신한다."""
                while not stop_clock.wait(1.0):
                    try:
                        _paint_clock()
                    except Exception:
                        break

            clock_thread = threading.Thread(target=_clock_heartbeat, daemon=True)
            clock_thread.start()
            try:
                result = review_paths(
                    targets,
                    note,
                    model=st.session_state.model_name.strip() or DEFAULT_MODEL,
                    standard=standard,
                    num_ctx=review_num_ctx,
                    num_predict=int(_ollama_opts["num_predict"]),
                    num_gpu=_ollama_opts.get("num_gpu"),
                    num_batch=int(_ollama_opts.get("num_batch", 512)),
                    on_progress=on_progress,
                    ollama_url=st.session_state.ollama_url,
                    project_root=project_root,
                    deepseek_model=st.session_state.deepseek_model.strip() if st.session_state.cross_enabled else "",
                    llama_model=st.session_state.llama_model.strip(),
                    think_mode=review_think_mode,
                )
                elapsed = time.monotonic() - started_at
                clock = _format_stopwatch(elapsed)
                st.session_state["last_review_timing"] = {"elapsed": elapsed}
                time_slot.markdown(f"**⏱ {clock}**")
                markdown_path, csv_path = save_reports(result["findings"], BUG_LABELS)
                result["markdown_path"] = str(markdown_path)
                result["csv_path"] = str(csv_path)
                result["elapsed_seconds"] = elapsed
                st.session_state["last_review"] = result
                st.session_state["show_done_dialog"] = True
            except ReviewError as error:
                elapsed = time.monotonic() - started_at
                clock = _format_stopwatch(elapsed)
                progress.progress(
                    shown["percent"] / 100.0,
                    text=f"진행 {shown['percent']:.0f}% · ⏱ {clock}에서 중단",
                )
                time_slot.markdown(f"**⏱ {clock}**")
                st.error(str(error))
            except OSError as error:
                elapsed = time.monotonic() - started_at
                clock = _format_stopwatch(elapsed)
                progress.progress(
                    shown["percent"] / 100.0,
                    text=f"진행 {shown['percent']:.0f}% · ⏱ {clock}에서 중단",
                )
                time_slot.markdown(f"**⏱ {clock}**")
                st.error(f"소스를 읽지 못했습니다: {error}")
            finally:
                stop_clock.set()
                clock_thread.join(timeout=2.0)
                if temp_dir is not None:
                    temp_dir.cleanup()

    if st.session_state.get("last_review"):
        show_review(st.session_state["last_review"])
if st.session_state.get("show_done_dialog") and st.session_state.get("last_review"):
    review_done_dialog()
