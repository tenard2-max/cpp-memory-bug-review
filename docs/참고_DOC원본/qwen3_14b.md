# [개발요건서] Qwen 3 14B 로컬 GPU 최적화 및 속도/품질 이중화(Hybrid Thinking) 파이프라인 구축

* **문서 버전:** v1.0
* **타겟 하드웨어:** NVIDIA GTX 1080 Ti (11GB VRAM, 484GB/s 대역폭)
* **베이스 엔진:** Ollama + `qwen3:14b` (Q4_K_M) + FastAPI Orchestrator
* **통제 기준:** `project_status.ini` (초기 개발 한도 60%, 독립 QA 검증 통과 후 100%)

---

## 1. 개요 및 목표
GTX 1080 Ti (11GB VRAM) 환경에서 `Qwen 3 14B` 모델의 모든 레이어(40/40 Layers)를 CPU 오프로딩 없이 **100% Full GPU**에 적재하여 최대 토큰 생성 속도를 확보한다. 
또한, 엔터프라이즈 코드(EMV L2, CEN/XFS 등) 정적 스캔 및 결함 추적 파이프라인(FastAPI)에서 작업 성격에 따라 **`/no_think` (고속 스캔 모드)**와 **`Thinking` (심층 추론 모드)**을 동적으로 스위칭하는 이중화(Dual-Mode) 라우팅 아키텍처를 구현한다.

---

## 2. 하드웨어 및 런타임 최적화 요건 (Ollama Layer)

### 2.1. VRAM 100% 적재 및 KV 캐시 최적화
* **대상 환경 변수 (System/Service Level):**
  * `OLLAMA_FLASH_ATTENTION=1` (Flash Attention 활성화로 연산 속도 향상 및 메모리 단편화 방지)
  * `OLLAMA_KV_CACHE_TYPE=q8_0` (KV 캐시 8비트 양자화를 통해 컨텍스트 메모리 점유율 약 50% 절감)
  * `OLLAMA_MAX_LOADED_MODELS=1` (11GB VRAM 내 모델 스와핑 오버헤드 원천 차단)
* **컨텍스트 윈도우 상한 통제:**
  * 기본 `num_ctx`는 `16384` (16K)로 제한하여 모델 가중치(약 9.1GB) + KV 캐시(약 1.2GB) 합계가 10.5GB를 초과하지 않도록 보장한다.
  * 실행 후 `ollama ps` 출력 기준 `PROCESSOR` 항목이 반드시 **`100% GPU`**로 유지되어야 한다.

### 2.2. 전용 커스텀 Modelfile 프로파일 정의
* 기본 `qwen3:14b` 외에 파이프라인 호출 안정성을 위해 두 가지 파생 모델 또는 파라미터 프리셋을 구성한다.
  1. `qwen3-14b-fast`: 기본 `/no_think` 지시어 내장, `temperature=0.1`, `top_p=0.8`, `num_ctx=16384` (정형화된 JSON/Diff 추출 및 고속 스캔용)
  2. `qwen3-14b-deep`: 기본 `Thinking` 모드 활성화, `temperature=0.6`, `top_p=0.95`, `num_ctx=16384` (복잡한 프로토콜 상태 머신, 메모리 누수, 엣지 케이스 역추적용)

---

## 3. 속도/품질 이중화(Hybrid Routing) 아키텍처 (FastAPI Layer)

### 3.1. 2-Stage 하이브리드 파이프라인 워크플로우
모든 코드 분석 및 QA 요청은 단일 호출이 아닌 아래 2단계 라우팅 정책을 따른다.

* **Stage 1: 1차 고속 정적 스캔 (`FAST_SCAN` / `/no_think` 모드)**
  * **트리거 조건:** 전체 소스 트리 순회, 문법/코딩 컨벤션 검사, 단순 스펙 누락 체크, 로그 1차 필터링.
  * **동작 방식:** 시스템/유저 프롬프트 말미에 `/no_think` 제어 토큰을 주입하거나 `think: false` 옵션을 활성화하여 `<think>` 태그 생성을 차단하고 즉각적인 JSON 구조화 결과를 반환한다.
  * **목표 응답 시간:** 파일당 3~8초 이내 (초당 30+ tokens 유지).
  * **출력 판정:** `[CLEAN]` 또는 `[SUSPECT_ANOMALY]` (의심 구간 플래그 및 라인 번호 추출).

* **Stage 2: 의심 구간 정밀 추적 (`DEEP_TRACE` / `Thinking` 모드)**
  * **트리거 조건:** Stage 1에서 `[SUSPECT_ANOMALY]`가 감지된 파일/함수, 혹은 사용자가 UI에서 **[정밀 QA 재평가 요청]**을 누른 항목.
  * **동작 방식:** `<think>` 내부 사고 프로세스를 전면 개방하여 오픈소스 레퍼런스 대비 프로토콜 상태 전이, 포인터 연산, 예외 처리 결함을 심층 추론한다.
  * **후처리 파서(Response Sanitizer):** 모델 출력에서 `<think>...</think>` 블록과 최종 답변 블록을 정규식으로 분리하여, 추론 과정은 `audit_trace.log`에 별도 기록하고 최종 결함 리포트(Diff)만 API 응답 및 `QA_ROUND.md`로 전달한다.

### 3.2. FastAPI 엔드포인트 및 옵션 제어 명세
* **Endpoint:** `POST /api/v1/analyze/hybrid`
* **Request Payload Schema:**
  ```json
  {
    "task_id": "TASK_01",
    "mode": "AUTO | FAST_ONLY | DEEP_ONLY",
    "target_files": ["src/tlv_parser.cpp"],
    "context_window": 16384,
    "save_think_log": true
  }
  ```
* **Response Payload Schema:**
  ```json
  {
    "task_id": "TASK_01",
    "executed_stages": ["FAST_SCAN", "DEEP_TRACE"],
    "gpu_offload_status": "100% GPU",
    "latency_ms": {
      "fast_scan": 4120,
      "deep_trace": 18450
    },
    "status": "FAILED_REWORK",
    "findings_diff": "...",
    "think_summary_path": "logs/think/TASK_01_trace.log"
  }
  ```

---

## 4. 관제 UI 및 `project_status.ini` 연동 요건

### 4.1. 관제 대시보드 옵션 추가
* 기존 `project_status.ini` 기반 관제 UI의 각 태스크 카드에 **추론 모드 선택 드롭다운**을 추가한다.
  * `AUTO (1차 Fast ➔ 의심 시 Deep 자동 전환)` [기본값]
  * `FAST (/no_think 강제)`
  * `DEEP (Thinking 강제)`
* 대시보드 상단 하드웨어 모니터 위젯에 `ollama ps` 기반 **현재 VRAM 점유율 및 `100% GPU` 적재 상태 뱃지**를 실시간 표시한다.

### 4.2. 폐루프(Closed-Loop) 상태 전이 규칙
* `FAST_SCAN`만 통과한 항목은 최대 `progress = 75`까지만 부여한다.
* `DEEP_TRACE` 검증까지 통과하고 결함이 0건일 때만 `progress = 100`, `status = VERIFIED`로 승격한다.

---

## 5. 단계별 개발 태스크 (`project_status.ini` 등록용)

| Task ID | 카테고리 | 작업 내용 | 완료 기준 (DoD) | 초기 완성도 |
| :--- | :--- | :--- | :--- | :---: |
| **TASK_QWEN_01** | Infra / Ollama | 1080 Ti (11GB) 환경 변수 설정 및 `qwen3-14b-fast` / `deep` Modelfile 빌드 | `ollama ps` 실행 시 `100% GPU` 적재 확인 및 `num_ctx=16384` 메모리 안정성 검증 | `60%` |
| **TASK_QWEN_02** | Backend / API | FastAPI 하이브리드 라우터(`/api/v1/analyze/hybrid`) 및 `<think>` 태그 분리 파서 구현 | `AUTO` 모드 호출 시 `[SUSPECT_ANOMALY]` 감지 후 `DEEP_TRACE` 자동 승격 동작 확인 | `60%` |
| **TASK_QWEN_03** | Frontend / UI | 관제 대시보드에 모드 선택(`AUTO`/`FAST`/`DEEP`) 및 GPU 상태 모니터링 UI 연동 | UI에서 모드 변경 시 `project_status.ini` 반영 및 Think 로그 뷰어 정상 출력 | `60%` |
| **TASK_QWEN_04** | QA / Benchmark | EMV/XFS 샘플 코드 10종 대상 `FAST_ONLY` vs `AUTO` 속도·결함 검출률 비교 검증 | 그록 봇 QA 검증 통과 및 `QA_BENCHMARK.md` 리포트 생성 | `60%` |