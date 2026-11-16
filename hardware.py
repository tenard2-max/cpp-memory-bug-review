"""그래픽 메모리와 메인 메모리에 맞춘 로컬 모델 설정."""

from __future__ import annotations

PROFILES = {
    ("lt1", "16"): {
        "model": "qwen2.5-coder:3b",
        "num_ctx": 2048,
        "note": "그래픽 메모리가 거의 없어 CPU로 돌립니다. 메인 메모리 16GB에서는 3B가 맞습니다.",
    },
    ("lt1", "32"): {
        "model": "qwen2.5-coder:7b",
        "num_ctx": 4096,
        "note": "그래픽 메모리 없이 메인 메모리 32GB로 7B를 돌립니다.",
    },
    ("8", "16"): {
        "model": "qwen2.5-coder:7b",
        "num_ctx": 4096,
        "note": "8GB 그래픽에는 7B 4비트가 맞습니다. 컨텍스트는 4096으로 제한합니다.",
    },
    ("8", "32"): {
        "model": "qwen2.5-coder:7b",
        "num_ctx": 4096,
        "note": "8GB 그래픽에는 더 큰 모델이 들어가지 않습니다. 메인 메모리 32GB는 여유만 늘립니다.",
    },
    ("11", "16"): {
        "model": "qwen3:14b",
        "num_ctx": 16384,
        "note": "GTX 1080 Ti 11GB에는 qwen3:14b(Q4)가 맞습니다. num_ctx=16384로 Full GPU 적재를 유지합니다.",
    },
    ("11", "32"): {
        "model": "qwen3:14b",
        "num_ctx": 16384,
        "note": "11GB 그래픽 + 32GB 메인에서도 qwen3:14b, num_ctx=16384가 안정적입니다.",
    },
    ("20", "16"): {
        "model": "qwen3:14b",
        "num_ctx": 16384,
        "note": "20GB 그래픽에는 qwen3:14b를 권장합니다. 컨텍스트는 16384입니다.",
    },
    ("20", "32"): {
        "model": "qwen3:14b",
        "num_ctx": 16384,
        "note": "20GB 그래픽 + 32GB 메인에서는 qwen3:14b, num_ctx=16384가 맞습니다.",
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
