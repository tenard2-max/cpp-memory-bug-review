"""그래픽 메모리와 메인 메모리에 맞춘 로컬 모델 설정."""

from __future__ import annotations

PROFILES = {
    ("lt1", "16"): {
        "model": "qwen2.5-coder:3b",
        "num_ctx": 2048,
        "num_gpu": 0,
        "note": "그래픽 메모리가 거의 없어 CPU로 돌립니다. 메인 메모리 16GB에서는 3B가 맞습니다.",
    },
    ("lt1", "32"): {
        "model": "qwen2.5-coder:7b",
        "num_ctx": 4096,
        "num_gpu": 0,
        "note": "그래픽 메모리 없이 메인 메모리 32GB로 7B를 CPU에서 돌립니다.",
    },
    ("8", "16"): {
        "model": "qwen2.5-coder:7b",
        "num_ctx": 24576,
        "num_batch": 1024,
        "note": "7B, 컨텍스트 24576, 배치 1024. 남은 약 1GB는 프롬프트 처리에 씁니다.",
    },
    ("8", "32"): {
        "model": "qwen2.5-coder:7b",
        "num_ctx": 24576,
        "num_batch": 1024,
        "note": "7B, 컨텍스트 24576, 배치 1024. 남은 약 1GB는 프롬프트 처리에 씁니다.",
    },
    ("11", "16"): {
        "model": "qwen2.5-coder:7b",
        "num_ctx": 4096,
        "num_batch": 512,
        "num_gpu": 99,
        "note": "1080 Ti 11GB 기본은 qwen2.5-coder:7b(빠른 편). qwen3:14b는 선택 가능하나 VRAM이 거의 꽉 차 초당 ~2토큰·첫 토큰 지연이 큽니다. 14B 쓸 때는 num_ctx 2048 고정.",
    },
    ("11", "32"): {
        "model": "qwen2.5-coder:7b",
        "num_ctx": 4096,
        "num_batch": 512,
        "num_gpu": 99,
        "note": "11GB는 7B가 체감 속도에 맞습니다. qwen3:14b는 FAST+/no_think·num_ctx 2048로만 권장. 문장 정리는 llama3.1:8b. RAG(BGE-M3)는 CPU라 VRAM을 안 씁니다.",
    },
    ("20", "16"): {
        "model": "qwen3:14b",
        "num_ctx": 16384,
        "note": "20GB 그래픽에는 qwen3:14b와 num_ctx 16384가 들어갑니다.",
    },
    ("20", "32"): {
        "model": "qwen3:14b",
        "num_ctx": 16384,
        "note": "20GB 그래픽 + 32GB 메인에서는 qwen3:14b, num_ctx 16384가 맞습니다.",
    },
}

VRAM_LABELS = {"lt1": "1GB 미만", "8": "8GB", "11": "11GB (1080 Ti)", "20": "20GB"}
RAM_LABELS = {"16": "16GB", "32": "32GB"}


def hardware_profile(vram: str, ram: str) -> dict:
    """선택한 메모리에 해당하는 모델과 컨텍스트 길이를 반환한다."""
    try:
        return PROFILES[(vram, ram)]
    except KeyError as error:
        raise ValueError(
            "그래픽 메모리는 1GB 미만, 8GB, 11GB, 20GB, 메인 메모리는 16GB, 32GB 중에서 고르세요."
        ) from error


def ollama_call_options(vram: str, ram: str, num_predict: int, model: str = "") -> dict:
    """Ollama API options. qwen3:14b는 11GB급에서 ctx 상한을 강제한다."""
    profile = hardware_profile(vram, ram)
    options: dict = {
        "temperature": 0.0,
        "num_ctx": int(profile["num_ctx"]),
        "num_thread": 8,
        "num_predict": int(num_predict),
    }
    if "num_gpu" in profile:
        options["num_gpu"] = int(profile["num_gpu"])
    if "num_batch" in profile:
        options["num_batch"] = int(profile["num_batch"])
    lowered = (model or "").strip().lower()
    # 잘못된 vram 프로필(8GB 등)이어도 14B가 CPU로 새지 않게 막는다.
    if lowered.startswith("qwen3:14b") or lowered.startswith("qwen3-14b"):
        # 11GB에서 4096도 전용 VRAM ~10.4GB + 공유 메모리로 넘어가 체감이 급락한다.
        options["num_ctx"] = min(int(options["num_ctx"]), 2048)
        options["num_gpu"] = int(options.get("num_gpu") or 99)
        options["num_batch"] = min(int(options.get("num_batch") or 256), 256)
    return options
