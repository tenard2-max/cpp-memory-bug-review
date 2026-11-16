"""docs 폴더용 1차 개발완료 PPT 생성."""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt


OUT = Path(__file__).with_name("03_1차개발완료_발표.pptx")
DARK = RGBColor(0x1A, 0x1A, 0x1A)
ACCENT = RGBColor(0xE0, 0x87, 0x2F)
WHITE = RGBColor(0xF5, 0xF5, 0xF5)
MUTED = RGBColor(0xC8, 0xC8, 0xC8)


def _set_run(run, text: str, size: int, bold: bool = False, color=WHITE) -> None:
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = "Malgun Gothic"


def add_title_slide(prs: Presentation, title: str, subtitle: str) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    fill = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    fill.fill.solid()
    fill.fill.fore_color.rgb = DARK
    fill.line.fill.background()

    box = slide.shapes.add_textbox(Inches(0.7), Inches(2.2), Inches(8.5), Inches(1.2))
    tf = box.text_frame
    tf.clear()
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    _set_run(p.add_run(), title, 32, True, WHITE)

    sub = slide.shapes.add_textbox(Inches(0.7), Inches(3.5), Inches(8.5), Inches(1.8))
    tf = sub.text_frame
    tf.word_wrap = True
    for i, line in enumerate(subtitle.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        _set_run(p.add_run(), line, 16, False, MUTED)


def add_bullets(prs: Presentation, title: str, lines: list[str]) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = DARK
    bg.line.fill.background()

    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.0), Inches(0.0), prs.slide_width, Inches(0.15))
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()

    head = slide.shapes.add_textbox(Inches(0.6), Inches(0.4), Inches(9), Inches(0.7))
    p = head.text_frame.paragraphs[0]
    run = p.add_run()
    _set_run(run, title, 24, True, WHITE)

    body = slide.shapes.add_textbox(Inches(0.7), Inches(1.3), Inches(8.8), Inches(5.5))
    tf = body.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = 0
        p.space_after = Pt(10)
        run = p.add_run()
        _set_run(run, f"•  {line}", 16, False, MUTED)


def main() -> None:
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)

    add_title_slide(
        prs,
        "C++ 메모리·초기화 버그 검토",
        "1차 개발 완료 보고\n로컬 Ollama + Streamlit · 2026-11-12\nGitHub: tenard2-max/cpp-memory-bug-review",
    )

    add_bullets(
        prs,
        "1. 프로젝트 목적",
        [
            "레거시 C/C++(VS 2008) 메모리·초기화 버그를 로컬에서만 검토",
            "원본 소스는 수정하지 않고 수정 포인트 리포트만 산출",
            "클라우드 업로드 없이 Ollama(qwen2.5-coder:7b) 사용",
            "cppcheck/정규식 힌트 + LLM JSON 검증의 하이브리드 구조",
        ],
    )

    add_bullets(
        prs,
        "2. 파이프라인",
        [
            "인코딩 정규화: utf-8 → cp949 → euc-kr",
            "함수 단위 청크 + [L000n] 줄번호 주입",
            "cppcheck 경고 + suspects(memset/sizeof/sprintf)",
            "Ollama JSON 분석 → (옵션) 교차검증·문장정리",
            "화면 결과 + reports/*.md, *.csv 자동 저장",
        ],
    )

    add_bullets(
        prs,
        "3. 핵심 기능 (엔진)",
        [
            "메모리 누수, UAF, double-free, 버퍼 넘침",
            "미초기화 읽기, 구조체 부분 미초기화, 포인터 sizeof 오용",
            "초기화 화이트리스트·진입 함수 관리",
            "샘플 few-shot 동적 주입 / 오탐 예외 등록",
            "헤더 심볼 SQLite 인덱스 및 토큰 예산",
        ],
    )

    add_bullets(
        prs,
        "4. UI (1차 마무리)",
        [
            "블랙 헤더: 제목 + 탭 + 옵션 일체화",
            "안내 패널: CPP_MEMORY_BUG_REVIEW 커맨드센터",
            "상태 패널: Ollama 연결·CPU·주소",
            "검토 작업 캔버스: 다크 그레이 입력/버튼",
            "옵션: 하드웨어·공유메모리·모델·토큰·cppcheck 표준",
        ],
    )

    add_bullets(
        prs,
        "5. GPU·시스템 메트릭",
        [
            "전용 VRAM / 공유 GPU 메모리 (작업 관리자 계열 카운터)",
            "AMD ADL 온도, GPU 엔진 사용률",
            "공유 메모리 옵션 ON 시에만 VRAM 아래 표시",
            "옵션 닫기 시 dlg_* → 세션 커밋으로 선택 유지",
        ],
    )

    add_bullets(
        prs,
        "6. 전체 개발 항목 요약",
        [
            "A 실행환경·LLM: 완료",
            "B 전처리·정적분석: 완료",
            "C 화이트리스트·프롬프트: 완료",
            "D 샘플 학습: 완료",
            "E 리포트: 완료",
            "F UI·운영: 완료",
            "G 후속(자동패치/IDE플러그인/야간배치): 2차",
        ],
    )

    add_bullets(
        prs,
        "7. 산출물·저장소",
        [
            "docs/01_개발내역.md",
            "docs/02_전체개발항목.md",
            "docs/03_1차개발완료_발표.pptx (본 문서)",
            "코드: app/reviewer/suspects/symbol_index/gpu_meter 등",
            "GitHub: https://github.com/tenard2-max/cpp-memory-bug-review",
        ],
    )

    add_title_slide(
        prs,
        "1차 개발 완료",
        "로컬 검토 · 리포트 · 관리 UI · 실측 GPU 패널 · GitHub 반영 완료\n후속은 자동 패치·IDE 연동·대규모 배치로 분리",
    )

    prs.save(OUT)
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
