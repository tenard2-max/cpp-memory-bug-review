"""C++ 메모리 버그 로컬 검토 화면."""

from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile

import pandas as pd
import streamlit as st

from analyzer import cppcheck_path
from cpu_meter import cpu_label, sample_cpu
from hardware import RAM_LABELS, VRAM_LABELS, hardware_profile, ollama_call_options
from report import save_reports
from reviewer import (
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_URL,
    PREDICT_CHOICES,
    ReviewError,
    installed_models,
    ollama_reachable,
    review_paths,
)
from server_status import (
    collect_server_status,
    download_remote_file,
    load_server_config,
    save_server_config,
)
from samples_db import (
    SAMPLES_PATH,
    add_sample,
    delete_sample,
    import_samples,
    load_samples,
    register_false_positive,
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
st.set_page_config(page_title="C++ 메모리·초기화 버그 검토", layout="wide")
st.title("C++ 메모리·초기화 버그 검토")
st.caption("메모리 누수, 해제 오류와 함께 미초기화, 구조체 부분 초기화, 포인터 sizeof 오용을 함수 단위로 검증합니다. 소스는 이 PC 밖으로 나가지 않습니다.")

notice = st.session_state.pop("sample_notice", "")
if notice:
    st.success(notice)
screen = st.segmented_control(
    "화면",
    options=["코드 검토", "헤더 인덱스", "샘플 학습 관리", "초기화 화이트리스트"],
    default="코드 검토",
    key="screen",
)
if not screen:
    screen = "코드 검토"

if "vram" not in st.session_state:
    st.session_state.vram = "8"
if "ram" not in st.session_state:
    st.session_state.ram = "16"
if not str(st.session_state.get("ollama_url") or "").strip():
    st.session_state.ollama_url = DEFAULT_OLLAMA_URL
if "model_name" not in st.session_state:
    st.session_state.model_name = DEFAULT_MODEL
if "cross_enabled" not in st.session_state:
    st.session_state.cross_enabled = False
if "deepseek_model" not in st.session_state:
    st.session_state.deepseek_model = DEFAULT_MODEL
if "llama_model" not in st.session_state:
    st.session_state.llama_model = DEFAULT_MODEL
if "num_predict" not in st.session_state:
    st.session_state.num_predict = 1024
if st.session_state.get("predict_default_version") != 3:
    st.session_state.num_predict = 1024
    st.session_state.predict_default_version = 3
if st.session_state.get("model_defaults_version") != 4:
    st.session_state.model_name = DEFAULT_MODEL
    st.session_state.deepseek_model = DEFAULT_MODEL
    st.session_state.llama_model = DEFAULT_MODEL
    st.session_state.model_defaults_version = 4
if "project_root" not in st.session_state:
    st.session_state.project_root = ""
pending_model = st.session_state.pop("_pending_model", None)
if pending_model:
    st.session_state.model_name = pending_model
pending_root = st.session_state.pop("_pending_root", None)
if pending_root:
    st.session_state.project_root = pending_root


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


@st.dialog("하드웨어 옵션")
def hardware_dialog() -> None:
    """그래픽 메모리와 메인 메모리를 고르면 모델과 컨텍스트 길이가 바뀐다."""
    vram = st.radio(
        "그래픽 메모리",
        list(VRAM_LABELS),
        format_func=lambda key: VRAM_LABELS[key],
        index=list(VRAM_LABELS).index(st.session_state.vram),
    )
    ram = st.radio(
        "메인 메모리",
        list(RAM_LABELS),
        format_func=lambda key: RAM_LABELS[key],
        index=list(RAM_LABELS).index(st.session_state.ram),
    )
    chosen = hardware_profile(vram, ram)
    gpu_note = f" · GPU {chosen['num_gpu']}층" if "num_gpu" in chosen else ""
    st.write(f"{chosen['model']} · num_ctx {chosen['num_ctx']}{gpu_note}")
    st.caption(chosen["note"])
    installed = installed_models(st.session_state.ollama_url)
    if installed and chosen["model"] not in installed:
        st.warning(f"{chosen['model']} 이 이 PC에 없습니다. 적용한 뒤 검토 화면에서 받아야 검토가 시작됩니다.")
    if st.button("적용", type="primary"):
        st.session_state.vram = vram
        st.session_state.ram = ram
        st.session_state["_pending_model"] = chosen["model"]
        st.rerun()


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


def _remember_server_status(rows: list[dict]) -> None:
    st.session_state.server_status_rows = rows


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
        _remember_server_status(
            collect_server_status(
                str(st.session_state.ollama_url),
                _server_config_from_state(),
                str(st.session_state.server_password),
            )
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
        st.session_state["index_error"] = ""
        st.session_state["index_notice"] = f"갱신 {result['updated']}개, 그대로 {result['unchanged']}개"

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
    status = index_status()
    st.write(
        f"인덱스 파일 {status['files']}개, 심볼 {status['symbols']}개. "
        f"예산 {int(st.session_state.context_token_budget)}토큰."
    )
    if not status["roots"]:
        st.info("헤더 루트가 비어 있습니다. 폴더를 저장한 뒤 인덱싱하세요. 그때까지 검토는 기존 정규식 헤더 조회를 사용합니다.")
    for item in status["skipped"]:
        st.warning(f"{item['path']}: {item['message']}")


def render_sample_admin() -> None:
    """화면에서 버그 샘플과 오탐 예외를 추가하고, 지우고, JSON으로 주고받는다."""
    st.subheader("샘플 학습 관리")
    st.caption("저장한 샘플은 다음 검토부터 바로 쓰입니다. 지금 보는 함수와 키워드가 맞는 샘플만 최대 3개 프롬프트에 넣습니다.")
    try:
        samples = load_samples()
    except ValueError as error:
        st.error(str(error))
        return

    with st.form("new_sample", clear_on_submit=True):
        category = st.text_input("버그 종류", placeholder="조기 리턴 시 미해제")
        keywords = st.text_input("키워드", placeholder="malloc, return")
        bad_code = st.text_area("문제 코드", height=140)
        good_code = st.text_area("수정 코드", height=100)
        explanation = st.text_area("해설", height=80)
        false_positive = st.checkbox("오탐 방지 (이 패턴은 정상 코드)")
        submitted = st.form_submit_button("샘플 저장", type="primary")
    if submitted:
        try:
            add_sample(
                {
                    "category": category,
                    "keywords": keywords,
                    "bad_code": bad_code,
                    "good_code": good_code,
                    "explanation": explanation,
                    "is_false_positive": false_positive,
                }
            )
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state["sample_notice"] = "샘플을 저장했습니다. 다음 검토부터 반영됩니다."
            st.rerun()

    export_col, import_col = st.columns(2)
    if SAMPLES_PATH.exists():
        export_col.download_button(
            "JSON 내보내기",
            SAMPLES_PATH.read_bytes(),
            file_name="bug_samples.json",
            mime="application/json",
        )
    uploaded = import_col.file_uploader("JSON 불러오기", type=["json"], key="sample_import")
    replace = st.checkbox("불러올 때 기존 샘플을 모두 교체")
    if st.button("불러오기", disabled=uploaded is None):
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
left, right = st.columns(2)
if cppcheck_path():
    left.info(f"cppcheck: {cppcheck_path()}")
else:
    left.warning("cppcheck가 없습니다. 메모리 호출이 있는 함수만 검토합니다.")
if online:
    right.success("Ollama 연결됨")
else:
    right.error("Ollama가 실행 중이지 않습니다. START.bat으로 준비하세요.")


@st.fragment(run_every=2)
def show_cpu() -> None:
    """검토 중이 아닐 때도 CPU 사용률을 2초마다 갱신한다."""
    system, ollama = sample_cpu()
    system_col, ollama_col = st.columns(2)
    system_col.metric("시스템 CPU", f"{system:.0f}%")
    ollama_col.metric("Ollama CPU", "없음" if ollama is None else f"{ollama:.0f}%")


show_cpu()

_ensure_server_settings()
option_column, server_column = st.columns(2)
if option_column.button("옵션", use_container_width=True):
    hardware_dialog()
if server_column.button("서버 설정", use_container_width=True):
    server_dialog()


def show_server_status() -> None:
    """마지막 서버 확인 결과를 보여 준다. 노트북에는 상태 확인을 누를 때만 접속한다."""
    if "server_status_rows" not in st.session_state:
        _remember_server_status(
            collect_server_status(
                str(st.session_state.ollama_url),
                _server_config_from_state(),
                str(st.session_state.get("server_password") or ""),
            )
        )
    rows = st.session_state.server_status_rows
    columns = st.columns(len(rows))
    for column, row in zip(columns, rows):
        if row["ok"]:
            column.success(f"{row['name']}\n\n{row['detail']}")
        else:
            column.error(f"{row['name']}\n\n{row['detail']}")


show_server_status()
_analysis_for_opts = st.session_state.model_name.strip() or DEFAULT_MODEL
_ollama_opts = ollama_call_options(
    st.session_state.vram,
    st.session_state.ram,
    int(st.session_state.num_predict),
    _analysis_for_opts,
)
_gpu_label = (
    f", num_gpu {_ollama_opts['num_gpu']}"
    if "num_gpu" in _ollama_opts
    else ""
)
st.info(
    f"그래픽 {VRAM_LABELS[st.session_state.vram]} · 메인 {RAM_LABELS[st.session_state.ram]} · "
    f"권장 {profile['model']} · Ollama 호출: temperature 0, num_ctx {_ollama_opts['num_ctx']}, "
    f"num_predict {_ollama_opts['num_predict']}, num_batch {_ollama_opts.get('num_batch', 512)}{_gpu_label}, num_thread 8"
)
# 다른 화면을 갔다 오면 입력칸이 비워진 채 다시 그려진다. 저장값을 다시 넣어 주소가 보이게 한다.
st.session_state.ollama_url = str(st.session_state.ollama_url).strip() or DEFAULT_OLLAMA_URL
st.text_input("Ollama 주소", key="ollama_url")


def _model_choices(current: str) -> list[str]:
    """기본 모델, 공식 대형 코더, 이 PC에 설치된 모델을 선택 목록으로 만든다."""
    offered = (
        DEFAULT_MODEL,
        "qwen2.5-coder:14b",
        "qwen2.5-coder:32b",
        current,
        *models,
    )
    choices: list[str] = []
    for name in offered:
        cleaned = name.strip()
        if cleaned and cleaned not in choices:
            choices.append(cleaned)
    return choices


def _select_model(label: str, key: str, help_text: str) -> None:
    """세 단계가 각자 설치된 모델 중 하나를 고르게 한다."""
    current = str(st.session_state.get(key) or DEFAULT_MODEL)
    choices = _model_choices(current)
    if current not in choices:
        st.session_state[key] = choices[0]
    st.selectbox(label, choices, key=key, help=help_text)


_select_model("분석 모델", "model_name", "메모리·초기화 1차 분석. 기본은 qwen2.5-coder:7b")
st.checkbox("교차 검증", key="cross_enabled", help="켜져 있을 때만 두 번째 모델을 호출합니다. 기본은 끔입니다.")
_select_model("교차 검증 모델", "deepseek_model", "교차 검증을 켰을 때 쓰는 모델. 기본은 qwen2.5-coder:7b")
_select_model("문장 정리 모델", "llama_model", "발견 항목의 한국어 해설만 다듬습니다. 기본은 qwen2.5-coder:7b")
st.selectbox(
    "토큰 상한",
    PREDICT_CHOICES,
    key="num_predict",
    help="모델이 한 번 호출에서 생성하는 최대 토큰입니다. 기본은 1024입니다.",
)
standard = st.selectbox("cppcheck 언어 표준", ["c++03", "c++17"], help="VS 2008 소스는 c++03이 맞습니다.")
analysis_model = st.session_state.model_name.strip() or DEFAULT_MODEL
model_missing = bool(models) and analysis_model not in models
if model_missing:
    st.error(
        f"{analysis_model} 모델이 이 PC에 없어 검토를 시작하지 않습니다. "
        f"설치된 모델: {', '.join(models)}"
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
    st.warning(f"{chosen_model} 이 아직 없습니다. 터미널에서 ollama pull {chosen_model} 을 실행하세요.")

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
        st.write(
            f"함수 {stats.get('functions', 0)}개 중 소거 {stats.get('pruned', 0)}개, "
            f"분석 창 {stats.get('windows', len(result['chunks']))}개"
        )
    for note_text in result.get("stage_notes") or []:
        st.info(note_text)
    if result.get("unconfirmed") and result.get("findings"):
        st.warning("교차 검증이 끝나지 않았습니다. 아래 목록만으로 정상이라고 보지 않습니다.")
    st.write(f"모델에 넘긴 함수 조각 {len(result['chunks'])}개")
    with st.expander("cppcheck"):
        st.code(result["report"] or "결과 없음")
    with st.expander("모델에 넘긴 코드"):
        for chunk in result["chunks"]:
            injected = chunk.get("injected_samples") or []
            names = ", ".join(
                f"{item['id']}. {item['category']}" + (" (정상)" if item["is_false_positive"] else "")
                for item in injected
            )
            header_note = "헤더 정의 포함" if chunk.get("headers") else "헤더 정의 없음"
            omitted = ", ".join(chunk.get("context_omitted") or [])
            st.code(
                f"{chunk['file']} {chunk.get('function_name', '')} {chunk['start']}-{chunk['end']} / {header_note}\n"
                f"넣은 컨텍스트: {', '.join(chunk.get('context_included') or []) or '없음'}\n"
                f"미포함 컨텍스트: {omitted or '없음'}\n"
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


if st.button("메모리·초기화 버그 검토", type="primary", disabled=not online or model_missing):
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
        progress = st.progress(0, text="진행 0% · cppcheck로 함수를 나누는 중")
        shown = {"percent": 0.0}

        def on_progress(percent: float, label: str) -> None:
            shown["percent"] = max(0.0, min(float(percent), 100.0))
            progress.progress(
                shown["percent"] / 100.0,
                text=f"진행 {shown['percent']:.0f}% · {cpu_label()} · {label}",
            )

        try:
            result = review_paths(
                targets,
                note,
                model=st.session_state.model_name.strip() or DEFAULT_MODEL,
                standard=standard,
                num_ctx=int(_ollama_opts["num_ctx"]),
                num_predict=int(_ollama_opts["num_predict"]),
                num_gpu=_ollama_opts.get("num_gpu"),
                num_batch=int(_ollama_opts.get("num_batch", 512)),
                on_progress=on_progress,
                ollama_url=st.session_state.ollama_url,
                project_root=project_root,
                deepseek_model=st.session_state.deepseek_model.strip() if st.session_state.cross_enabled else "",
                llama_model=st.session_state.llama_model.strip(),
            )
            markdown_path, csv_path = save_reports(result["findings"], BUG_LABELS)
            result["markdown_path"] = str(markdown_path)
            result["csv_path"] = str(csv_path)
            st.session_state["last_review"] = result
            st.session_state["show_done_dialog"] = True
        except ReviewError as error:
            progress.progress(shown["percent"] / 100.0, text=f"진행 {shown['percent']:.0f}%에서 중단")
            st.error(str(error))
        except OSError as error:
            progress.progress(shown["percent"] / 100.0, text=f"진행 {shown['percent']:.0f}%에서 중단")
            st.error(f"소스를 읽지 못했습니다: {error}")
        finally:
            if temp_dir is not None:
                temp_dir.cleanup()

if st.session_state.get("last_review"):
    show_review(st.session_state["last_review"])
if st.session_state.get("show_done_dialog") and st.session_state.get("last_review"):
    review_done_dialog()
