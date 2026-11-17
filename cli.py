"""폴더나 파일을 명령줄에서 검토한다."""

from __future__ import annotations

import argparse
from pathlib import Path

from hardware import hardware_profile, ollama_call_options
from report import save_reports
from reviewer import (
    DEFAULT_MODEL,
    DEFAULT_THINK_MODE,
    PREDICT_CHOICES,
    THINK_MODES,
    ReviewError,
    is_qwen3_model,
    review_paths,
)

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


def main() -> int:
    parser = argparse.ArgumentParser(description="C/C++ 메모리 버그와 초기화 버그를 로컬 모델로 검토합니다.")
    parser.add_argument("paths", nargs="+", help="소스 파일 또는 폴더")
    parser.add_argument("--vram", default="8", choices=["lt1", "8", "11", "20"], help="lt1은 1GB 미만, 8, 11, 20")
    parser.add_argument("--ram", default="16", choices=["16", "32"])
    parser.add_argument("--std", default="c++03", choices=["c++03", "c++17"])
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--think-mode",
        default=DEFAULT_THINK_MODE,
        choices=list(THINK_MODES),
        help="qwen3:14b 전용. 기본 FAST(/no_think).",
    )
    parser.add_argument("--deepseek", default="", help="비우면 교차 검증을 하지 않습니다.")
    parser.add_argument("--llama", default=DEFAULT_MODEL)
    parser.add_argument("--ollama", default="http://127.0.0.1:11434")
    parser.add_argument("--note", default="이 소스의 메모리 버그와 초기화 버그를 찾아 주세요.")
    parser.add_argument("--num-predict", type=int, default=512, choices=PREDICT_CHOICES)
    args = parser.parse_args()
    profile = hardware_profile(args.vram, args.ram)
    ollama_opts = ollama_call_options(args.vram, args.ram, args.num_predict, args.model)
    if is_qwen3_model(args.model):
        ollama_opts["num_ctx"] = max(int(ollama_opts["num_ctx"]), 16384)
    print(
        f"모델 {args.model} / Ollama {args.ollama} / num_ctx {ollama_opts['num_ctx']} / {profile['note']}"
    )
    try:
        def on_progress(percent: float, label: str) -> None:
            print(f"[진행 {percent:.0f}%] {label}")

        result = review_paths(
            [Path(path) for path in args.paths],
            args.note,
            model=args.model,
            standard=args.std,
            num_ctx=int(ollama_opts["num_ctx"]),
            num_gpu=ollama_opts.get("num_gpu"),
            num_batch=int(ollama_opts.get("num_batch", 512)),
            on_progress=on_progress,
            ollama_url=args.ollama,
            deepseek_model=args.deepseek,
            llama_model=args.llama,
            num_predict=int(ollama_opts["num_predict"]),
            think_mode=args.think_mode,
        )
    except ReviewError as error:
        print(error)
        return 1
    print(result["report"])
    print(f"모델에 넘긴 조각: {len(result['chunks'])}")
    markdown_path, csv_path = save_reports(result["findings"], BUG_LABELS)
    print(f"마크다운: {markdown_path}")
    print(f"CSV: {csv_path}")
    if result["rejected"]:
        print(result["reject_reason"] or "메모리 버그와 초기화 버그 검토만 처리합니다.")
        return 0
    if not result["findings"]:
        print("보고할 메모리 버그와 초기화 버그가 없습니다.")
        return 0
    for finding in result["findings"]:
        label = BUG_LABELS.get(finding["bug_type"], finding["bug_type"])
        print(
            f"{finding['confidence']}\t{label}\t{finding['file']}:{finding['line']}\t"
            f"{finding.get('function_name', '')}\t{finding['summary']}"
        )
        if finding.get("before_code"):
            print(finding["before_code"])
        if finding.get("after_code"):
            print(finding["after_code"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
