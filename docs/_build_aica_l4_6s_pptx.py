"""AICA L4 6σ 양식 PPT — 샘플 폼 유지, C++ 소스 오류 검증 내용으로 교체."""

from __future__ import annotations

import shutil
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

TEMPLATE = Path(r"D:\AICA\L4\[AICA L4] AI를 활용한 프로그램 소스 오류 검증 시스템 개발_이평호.pptx")
OUT_DOCS = Path(__file__).with_name(
    "[AICA L4] AI를 활용한 프로그램 소스 오류 검증 시스템 개발_이평호.pptx"
)
OUT_AICA = Path(r"D:\AICA\L4\[AICA L4] AI를 활용한 프로그램 소스 오류 검증 시스템 개발_이평호_CPP메모리검증.pptx")


def set_tf(shape, text: str) -> None:
    """텍스트 프레임을 줄바꿈 기준으로 다시 채운다. 첫 문단 서식은 유지한다."""
    if not shape.has_text_frame:
        return
    tf = shape.text_frame
    lines = text.split("\n") if text is not None else [""]
    # 기존 문단 수 맞추기
    while len(tf.paragraphs) < len(lines):
        tf.add_paragraph()
    for index, para in enumerate(tf.paragraphs):
        line = lines[index] if index < len(lines) else ""
        if para.runs:
            para.runs[0].text = line
            for run in para.runs[1:]:
                run.text = ""
        else:
            para.text = line
    # 남는 문단 비우기
    for index in range(len(lines), len(tf.paragraphs)):
        para = tf.paragraphs[index]
        if para.runs:
            para.runs[0].text = ""
            for run in para.runs[1:]:
                run.text = ""
        else:
            para.text = ""


def set_table_cell(table, row: int, col: int, text: str) -> None:
    cell = table.cell(row, col)
    tf = cell.text_frame
    lines = text.split("\n")
    while len(tf.paragraphs) < len(lines):
        tf.add_paragraph()
    for index, para in enumerate(tf.paragraphs):
        line = lines[index] if index < len(lines) else ""
        if para.runs:
            para.runs[0].text = line
            for run in para.runs[1:]:
                run.text = ""
        else:
            para.text = line
    for index in range(len(lines), len(tf.paragraphs)):
        para = tf.paragraphs[index]
        if para.runs:
            for run in para.runs:
                run.text = ""
        else:
            para.text = ""


def text_shapes(slide):
    for shape in slide.shapes:
        if shape.has_text_frame and shape.shape_type != MSO_SHAPE_TYPE.TABLE:
            yield shape


def first_table(slide):
    for shape in slide.shapes:
        if shape.has_text_frame is False and shape.shape_type == MSO_SHAPE_TYPE.TABLE:
            return shape.table
        if shape.shape_type == MSO_SHAPE_TYPE.TABLE:
            return shape.table
    return None


def fill(prs: Presentation) -> None:
    s = prs.slides

    # --- 1 표지 ---
    shapes = list(text_shapes(s[0]))
    set_tf(shapes[0], "AI를 활용한 프로그램 소스 오류 검증 시스템 개발")
    set_tf(shapes[1], "2026.11.16\n솔루션개발팀 이평호")

    # --- 2 중간 표지 ---
    shapes = list(text_shapes(s[1]))
    set_tf(shapes[0], "AI를 활용한 C++ 소스 오류 검증")
    set_tf(shapes[1], "2026.11.16")

    # --- 3 목차 ---
    shapes = list(text_shapes(s[2]))
    # 0 목차, 1 항목, 2 로마숫자, 3~7 한줄 설명
    set_tf(shapes[0], "목   차")
    set_tf(shapes[1], "문제 정의\n원인 정의\n개선 컨셉\n개선안 실시\n실행 및 계획")
    set_tf(shapes[2], "Ⅰ.\nⅡ.\nⅢ.\nⅣ.\nⅤ. ")
    set_tf(shapes[3], "레거시 C/C++ 메모리·초기화 버그를 로컬에서 어떻게 검증할 것인가")
    set_tf(shapes[4], "클라우드 LLM·통째 파일 분석·줄번호/매크로 오탐으로 실무 적용이 어려움")
    set_tf(shapes[5], "로컬 Ollama + 정적힌트 + 함수청크 + 벡터 RAG로 검토 파이프라인 구성")
    set_tf(shapes[6], "Streamlit 도구·Qwen3 추론모드·Chroma/BGE-M3를 AI 협업으로 구현")
    set_tf(shapes[7], "검증·문서화·GitHub 반영까지 완료하여 실무 검토 품질·속도 확보")

    # --- 4 문제 정의 + 5W1H ---
    shapes = list(text_shapes(s[3]))
    set_tf(shapes[0], "1. 문제 정의")
    problem_q = "소스를 외부로 보내지 않고도\n메모리·초기화 버그를 빠르게 검증할 수 있는가?"
    problem_body = (
        "개발 대상 : 레거시 C/C++(VS 2008) 소스의 메모리·초기화 버그 로컬 검토\n"
        "개발 진행 시 문제점\n"
        "   - 금융·레거시 소스는 클라우드 LLM 업로드 불가\n"
        "   - 수천 줄 .cpp를 통째로 넣으면 줄번호·문맥이 틀어짐\n"
        "   - 사내 매크로/헤더 없이 LLM만 돌리면 오탐·미탐 증가"
    )
    for shape in shapes[1:]:
        # 짧은 박스는 질문, 긴 박스는 본문
        if shape.width < 6_000_000:
            set_tf(shape, problem_q)
        else:
            set_tf(shape, problem_body)
    table = first_table(s[3])
    if table is not None:
        set_table_cell(table, 0, 0, "구분")
        set_table_cell(table, 0, 2, "내용")
        set_table_cell(table, 1, 0, "What")
        set_table_cell(table, 1, 1, "문제대상")
        set_table_cell(table, 1, 2, "로컬에서 C++ 메모리·초기화 버그를 검증할 수 있는가?")
        set_table_cell(table, 2, 0, "How")
        set_table_cell(table, 2, 1, "측정방법")
        set_table_cell(table, 2, 2, "Streamlit+Ollama 검토 도구로 샘플·실소스 검증")
        set_table_cell(table, 3, 0, "When")
        set_table_cell(table, 3, 1, "측정기간")
        set_table_cell(table, 3, 2, "2026.10 ~ 2026.11 (1차+벡터/Qwen3 완료)")
        set_table_cell(table, 4, 0, "Where")
        set_table_cell(table, 4, 1, "발생장소")
        set_table_cell(table, 4, 2, "솔루션개발팀 로컬 PC (GTX 1080 Ti)")
        set_table_cell(table, 5, 0, "Who")
        set_table_cell(table, 5, 1, "측정담당")
        set_table_cell(table, 5, 2, "솔루션 개발팀 이평호 책임")
        set_table_cell(table, 6, 0, "Why")
        set_table_cell(table, 6, 1, "측정이유")
        set_table_cell(table, 6, 2, "소스 유출 없이 검토 품질·속도·재현성을 확보하기 위함")

    # --- 5 원인 정의 ---
    cause = (
        "기존 방식만으로는 실무 검증 요구와 충돌이 발생한다.\n"
        "    - Why(왜): 소스가 PC 밖으로 나가면 안 되는 보안·규정 제약\n"
        "    - Why: LLM은 줄 단위를 세지 못해 줄번호·함수 경계를 자주 틀림\n"
        "    - Why: SAFE_FREE 등 사내 매크로·헤더 정의가 없으면 누수 오탐\n"
        "    - Why: 파일 전체 통째 분석은 느리고 컨텍스트 한도를 초과\n"
        "    - Why: 키워드 few-shot만으로는 표현이 다른 유사 버그를 놓침\n"
        "2) 난이도·효과\n"
        "    - 정적분석(cppcheck)+청크+로컬 LLM+RAG를 묶어야 실무 수준에 도달"
    )
    shapes = list(text_shapes(s[4]))
    set_tf(shapes[0], "2. 원인 정의")
    for shape in shapes[1:]:
        set_tf(shape, cause)

    # --- 6 개선 컨셉 ---
    concept = (
        "목적: 로컬 전용으로 메모리·초기화 버그 검토 품질과 속도를 동시에 확보\n"
        "어떻게: 정적 힌트 → 함수 청크([L000n]) → 로컬 LLM(JSON) → 리포트\n"
        "보강: 헤더 심볼 인덱스 + Chroma/BGE-M3(샘플·헤더·소스 RAG)\n"
        "추론: Qwen3:14b FAST(기본)/AUTO/DEEP로 속도·심층 검증 이중화\n"
        "효과: 원본 미수정·외부 전송 없음·재현 가능한 MD/CSV 산출"
    )
    shapes = list(text_shapes(s[5]))
    set_tf(shapes[0], "3. 개선 컨셉")
    for shape in shapes[1:]:
        set_tf(shape, concept)

    # --- 7 개선안 실시 ---
    action = (
        "AI(Cursor)로 요건·아키텍처·구현·문서화를 일괄 진행.\n"
        "로컬 Ollama 모델을 호출하는 Streamlit 검토 UI를 구축.\n"
        "cppcheck/suspects + 헤더 SQLite + 벡터 RAG를 파이프라인에 연결.\n"
        "검증 보고서·체크리스트·GitHub 반영으로 완료 기준을 고정."
    )
    shapes = list(text_shapes(s[6]))
    set_tf(shapes[0], "4. 개선안 실시")
    for shape in shapes[1:]:
        set_tf(shape, action)

    # --- 8 실행 및 계획 개요 ---
    plan = (
        "1차(2026.11.12): Streamlit 검토 도구·리포트·헤더/샘플/화이트리스트\n"
        "보강(2026.11.16): Qwen3 추론모드 + Chroma/BGE-M3 벡터 RAG 완료\n"
        "문서: docs/ 에 6σ형 발표·개발내역·검증자료를 통합 보관"
    )
    shapes = list(text_shapes(s[7]))
    set_tf(shapes[0], "5. 실행 및 계획")
    for shape in shapes[1:]:
        set_tf(shape, plan)

    # --- 9 실행 제약/대상 ---
    shapes = list(text_shapes(s[8]))
    set_tf(shapes[0], "5. 실행 및 계획")
    set_tf(
        shapes[1],
        "환경 제약: 소스는 로컬만 · 원본 파일 미수정 · VRAM 11GB(1080 Ti)\n"
        "                - 임베딩은 CPU(BGE-M3), VRAM은 qwen3:14b에 양보\n"
        "                - FastAPI/외부 게이트웨이 미사용(Streamlit 단일 UI)\n"
        "                - VS 2008 레거시 대응: c++03, CP949/EUC-KR 로더",
    )
    table = first_table(s[8])
    if table is not None:
        set_table_cell(table, 0, 0, "개발 내역")
        set_table_cell(table, 0, 1, "상세 내용")
        set_table_cell(table, 1, 0, "로컬 검토 UI/엔진")
        set_table_cell(table, 1, 1, "Streamlit + Ollama, 함수 청크, JSON 리포트")
        set_table_cell(table, 2, 0, "벡터 RAG / 추론모드")
        set_table_cell(table, 2, 1, "Chroma 3컬렉션 + Qwen3 FAST/AUTO/DEEP")

    # --- 10 5.1 AI 역할 ---
    shapes = list(text_shapes(s[9]))
    set_tf(shapes[0], "5.1. AI 협업 역할 분담")
    # find by approximate content order - title already 0, then caption, ovals, box, note
    bodies = [sh for sh in shapes[1:]]
    # map by previous structure: caption, oval gpt, oval claude, rect deliverable, note
    if len(bodies) >= 1:
        set_tf(bodies[0], "요건·구현·검증·문서를 AI로 연결 (클라우드 소스 업로드 없음)")
    # ellipses and rectangles among all shapes
    for shape in s[9].shapes:
        if not shape.has_text_frame:
            continue
        t = shape.text_frame.text
        if "GPT" in t or "초안" in t:
            set_tf(shape, "기획/DOC : 문제·보완책·벡터DB 후보 정리")
        elif "클로드" in t:
            set_tf(shape, "설계 검토 : 로컬 전용·청크·JSON 강제 원칙 확정")
        elif "산출물" in t or "커서_" in t:
            set_tf(
                shape,
                "산출물 : docs/01~07, vector_store.py,\n"
                "app/reviewer/samples_db 연동",
            )
        elif "개발환경" in t or "요건서" in t:
            set_tf(
                shape,
                "개발·검증은 Cursor가 코드/문서 일괄 진행\n"
                "실행 엔진은 로컬 Ollama(qwen3:14b)\n"
                "개발환경 : Cursor + Ollama + Streamlit",
            )

    # --- 11 5.2 파이프라인 ---
    for shape in s[10].shapes:
        if not shape.has_text_frame:
            continue
        t = shape.text_frame.text
        if t.startswith("5.") or "데모 프로그램" in t or "SFTP" in t:
            if "5.2" in t or t.startswith("5.2"):
                set_tf(shape, "5.2. 검토 파이프라인 개발")
            elif "커서 개발" in t:
                set_tf(shape, "Cursor로 로컬 검토 파이프라인 구현")
            elif "산출물" in t:
                set_tf(
                    shape,
                    "산출물 :\n"
                    "1) Streamlit app.py / reviewer.py\n"
                    "2) chunks·suspects·symbol_index\n"
                    "3) vector_store(Chroma+BGE-M3)\n"
                    "4) docs/04~07, GitHub main",
                )
            elif "컴파일러" in t or "커서 :" in t:
                set_tf(shape, "Cursor : Python/Streamlit\nOllama : qwen3:14b")
            elif "요건" in t or "md" in t.lower():
                set_tf(
                    shape,
                    "DOC 기획 → docs 확정 문서\n"
                    "코드는 로컬 Git + GitHub private",
                )
            elif "프롬프트" in t:
                set_tf(shape, "순차 개발\n검증·문서화")
    # ensure title
    shapes = list(text_shapes(s[10]))
    set_tf(shapes[0], "5.2. 검토 파이프라인 개발")

    # --- 12 5.3 로컬 환경 ---
    shapes = list(text_shapes(s[11]))
    set_tf(shapes[0], "개선 컨셉")
    set_tf(shapes[1], "5.3. 로컬 실행·보안 원칙")
    for shape in shapes[2:]:
        t = shape.text_frame.text
        if "OpenSSH" in t or "설정" in t or "격리" in t or "★" in t or len(t) > 40:
            set_tf(
                shape,
                "★ 로컬 전용: 소스는 Ollama localhost만 호출, 외부 API 전송 없음\n"
                "★ 원본 보존: 임시 가공 후 리포트만 생성, 원본 .cpp/.h 미수정\n"
                "★ 함수 단위: 메모리 API·의심 구간만 청크로 전달해 속도·정확도 확보\n"
                "★ VRAM 보호: BGE-M3 임베딩 CPU, LLM만 GPU(qwen3:14b)\n"
                "★ 재현성: reports/*.md,*.csv + docs 체크리스트로 결과 고정",
            )
        elif "OpenSSH" in t or "경로" in t:
            set_tf(shape, "실행: START.bat → Streamlit / py -3 cli.py 파일.cpp")

    # --- 13 5.4 개발 내역 표 ---
    shapes = list(text_shapes(s[12]))
    set_tf(shapes[0], "5.4. Cursor 기반 개발 진행/내역")
    table = first_table(s[12])
    if table is not None:
        rows = [
            ("개발 내역", "상세 내용"),
            ("요건·원칙 확정", "로컬전용, 청크, JSON강제, cppcheck 우선 (DOC→docs)"),
            ("1차 엔진/UI", "검토·헤더인덱스·샘플·화이트리스트·GPU패널"),
            ("Qwen3 추론모드", "FAST(기본)/AUTO/DEEP, think 로그 분리"),
            ("벡터 RAG", "bug_samples·header_symbols·source_chunks"),
            ("문서·배포", "docs/01~07, 검증보고서, GitHub 동기화"),
        ]
        for r, (a, b) in enumerate(rows):
            set_table_cell(table, r, 0, a)
            set_table_cell(table, r, 1, b)

    # --- 14 5.5 구조 ---
    shapes = list(text_shapes(s[13]))
    set_tf(shapes[0], "5.5. 시스템 구조 (데이터·모듈)")
    for shape in s[13].shapes:
        if shape.has_text_frame and "Config" in shape.text_frame.text:
            set_tf(
                shape,
                "data/chroma/          bug_samples / header_symbols / source_chunks\n"
                "data/*.sqlite         헤더 심볼 인덱스\n"
                "bug_samples.json      few-shot 샘플\n"
                "config/index.yaml     헤더 루트·토큰 예산\n"
                "reports/              MD·CSV 검토 리포트\n"
                "docs/                 개발·검증·6σ 문서",
            )

    # --- 15 5.6 배포/패키지 → 벡터 구성 ---
    shapes = list(text_shapes(s[14]))
    set_tf(shapes[0], "5.6. 벡터 검색 구성 (Chroma + BGE-M3)")
    for shape in shapes[1:]:
        set_tf(
            shape,
            "샘플 few-shot: 벡터 0.7 + 키워드 0.3 하이브리드\n"
            "헤더: exact 후 BGE 재순위 + Chroma 심볼 보충\n"
            "소스 RAG: 프로젝트 함수 청크를 프롬프트에 첨부",
        )

    # --- 16 5.7 Qwen3 ---
    shapes = list(text_shapes(s[15]))
    set_tf(shapes[0], "5.7. Qwen3 추론 모드 (효과)")
    # pictures remain decorative; add meaning via any text boxes if present
    for shape in shapes[1:]:
        set_tf(
            shape,
            "FAST: think=false 고속 JSON (기본)\n"
            "AUTO: 의심 시 Thinking 승격\n"
            "DEEP: 심층 추론 + logs/think 보존",
        )

    # --- 17 5.8 기술 선정 ---
    shapes = list(text_shapes(s[16]))
    set_tf(shapes[0], "5.8. 기술 선정 이유")
    for shape in shapes[1:]:
        set_tf(
            shape,
            "* 검증된 오픈소스 조합\n"
            "Ollama + qwen3:14b / Streamlit / cppcheck\n"
            "chromadb + BAAI/bge-m3(CPU) — Docker·FAISS 제외",
        )

    # --- 18 5.9 검증 ---
    shapes = list(text_shapes(s[17]))
    set_tf(shapes[0], "5.9. 검증. 실행·UI 확인")
    boxes = [sh for sh in shapes if sh != shapes[0]]
    if len(boxes) >= 1:
        set_tf(
            boxes[0],
            "로컬 실행 검증\n"
            "1. Ollama: qwen3:14b pull · ollama ps GPU 확인\n"
            "2. pip install -r requirements.txt (chromadb, sentence-transformers)\n"
            "3. START.bat → 옵션: 벡터 ON, 추론 FAST\n"
            "4. 샘플 UAF/sizeof 검토 및 헤더·소스 인덱스 재구축",
        )
    if len(boxes) >= 2:
        set_tf(
            boxes[1],
            "검증 자료: docs/CPP_검증_2026-11-13/\n"
            "GitHub: tenard2-max/cpp-memory-bug-review",
        )
    if len(boxes) >= 3:
        set_tf(
            boxes[2],
            "[효과] 소스 외부 전송 0 · 함수 단위 리포트 재현\n"
            "[효과] few-shot/헤더/소스 RAG로 오탐·미탐 감소 기반 확보\n"
            "[효과] FAST 모드로 대량 창 고속 스캔, 필요 시만 DEEP",
        )

    # --- 19 5.9 로그성 슬라이드 → 효과 상세 ---
    shapes = list(text_shapes(s[18]))
    set_tf(shapes[0], "5.9. 검증. 목적 대비 효과")
    for shape in shapes[1:]:
        t = shape.text_frame.text
        if "핑거" in t:
            set_tf(shape, "로컬\n전용")
        else:
            set_tf(
                shape,
                "When: 2026.10~11 개발·검증 완료\n"
                "Why: 보안 제약 하에서 메모리 버그 검토 자동화 필요\n"
                "How: 정적힌트+청크+로컬LLM+벡터RAG+추론모드\n"
                "목적: 유출 없이 발견→근거→수정안까지 리포트\n"
                "효과1: 원본 보존·재현 가능한 MD/CSV\n"
                "효과2: 키워드 한계를 벡터 유사 검색으로 보완\n"
                "효과3: FAST/DEEP으로 속도와 심층 검증 선택\n"
                "효과4: docs/·GitHub로 인수인계·재실행 가능",
            )

    # --- 20 산출물 ---
    for shape in s[19].shapes:
        if not shape.has_text_frame:
            continue
        t = shape.text_frame.text
        if t.startswith("5.10") or "산출물" in t and t.startswith("5"):
            set_tf(shape, "5.10. 개발 완료 산출물")
        elif "고객 설명" in t:
            set_tf(shape, "* 6σ·개발 문서")
        elif "데모_SFTP" in t or "pptx" in t:
            set_tf(
                shape,
                "1) 본 AICA L4 6σ PPT\n"
                "2) docs/01~07 개발·벡터·Qwen3 문서",
            )
        elif "개발 프롬프트" in t or "요건" in t and "정의" in t:
            set_tf(shape, "* 요건·검증")
        elif "개발요건서" in t:
            set_tf(
                shape,
                "1) DOC/ 기획 원본\n"
                "2) docs/CPP_검증_2026-11-13",
            )
        elif "클라이언트 프로그램" in t:
            set_tf(shape, "* 실행 패키지(코드)")
        elif "Sftp.zip" in t or "Sftp" in t:
            set_tf(shape, "1) GitHub main\n2) START.bat / cli.py")
        elif "다운로드" in t or "Downfile" in t:
            set_tf(shape, "* 리포트 예시\n1) reports/*.md, *.csv")

    # --- 21 프로젝트 구조 ---
    shapes = list(text_shapes(s[20]))
    set_tf(shapes[0], "5.10. 개발 완료 산출물")
    for shape in shapes[1:]:
        if "구조" in shape.text_frame.text or "전체" in shape.text_frame.text:
            set_tf(shape, "전체 프로젝트 구조")
        else:
            set_tf(
                shape,
                "app.py / reviewer.py / chunks.py     UI·검토 엔진\n"
                "vector_store.py / samples_db.py     벡터·few-shot\n"
                "symbol_index.py / suspects.py       헤더·정적 의심\n"
                "docs/                              개발·6σ·검증 문서\n"
                "data/chroma/                       벡터 인덱스(로컬)",
            )

    # --- 22 소스 구조 ---
    shapes = list(text_shapes(s[21]))
    set_tf(shapes[0], "5.10. 개발 완료 산출물")
    for shape in shapes[1:]:
        if "구조" in shape.text_frame.text or "소스" in shape.text_frame.text:
            set_tf(shape, "핵심 모듈 (Python)")
        # picture left as-is (old screenshot) - caption already changed

    # --- 23 다운로드 → 문서맵 ---
    shapes = list(text_shapes(s[22]))
    set_tf(shapes[0], "5.10. 개발 완료 산출물")
    for shape in shapes[1:]:
        if "구조" in shape.text_frame.text or "다운로드" in shape.text_frame.text:
            set_tf(shape, "문서 맵 (docs/)")
        else:
            set_tf(
                shape,
                "01_개발내역 / 02_전체개발항목\n"
                "04~05_벡터검색 / 06_Qwen3 / 07_최종완료\n"
                "CPP_검증_2026-11-13 / 참고_DOC원본\n"
                "본 파일: AICA L4 6σ 양식 발표 자료",
            )

    # --- 24 후기 ---
    shapes = list(text_shapes(s[23]))
    set_tf(shapes[0], "* 개발 후기")
    set_tf(
        shapes[1],
        "언제: 2026.10~11, 로컬 GPU(1080 Ti) 환경에서 완료\n"
        "왜: 소스 유출 없이 레거시 C++ 메모리 버그를 실무 수준으로 검토해야 함\n"
        "어떻게: Cursor+Ollama로 정적힌트·청크·벡터RAG·추론모드를 일괄 구현\n"
        "목적/효과: 재현 가능한 로컬 검증 체계를 만들어 품질·속도·보안을 동시에 만족",
    )


def main() -> None:
    if not TEMPLATE.is_file():
        raise SystemExit(f"템플릿 없음: {TEMPLATE}")
    shutil.copy2(TEMPLATE, OUT_DOCS)
    prs = Presentation(str(OUT_DOCS))
    fill(prs)
    prs.save(str(OUT_DOCS))
    shutil.copy2(OUT_DOCS, OUT_AICA)
    print("saved", OUT_DOCS)
    print("saved", OUT_AICA)


if __name__ == "__main__":
    main()
