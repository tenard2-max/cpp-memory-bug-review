"""검토 결과를 날짜가 찍힌 마크다운과 CSV로 저장한다."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

REPORT_DIR = Path(__file__).with_name("reports")
CONFIDENCE_LABELS = {"high": "High", "medium": "Medium", "low": "Low"}

COLUMNS = [
    "파일명",
    "줄 번호",
    "함수명",
    "버그 종류",
    "확신도",
    "현재 코드",
    "수정 제안",
    "근거",
]


def confidence_label(value: str) -> str:
    return CONFIDENCE_LABELS.get(value, value)


def finding_rows(findings: list[dict], bug_labels: dict[str, str]) -> list[dict]:
    rows = []
    for finding in findings:
        rows.append(
            {
                "파일명": finding.get("file", ""),
                "줄 번호": finding.get("line", ""),
                "함수명": finding.get("function_name", ""),
                "버그 종류": bug_labels.get(finding.get("bug_type", ""), finding.get("bug_type", "")),
                "확신도": confidence_label(str(finding.get("confidence", ""))),
                "현재 코드": finding.get("before_code", ""),
                "수정 제안": finding.get("after_code", ""),
                "근거": finding.get("summary", "") or finding.get("evidence", ""),
            }
        )
    return rows


def render_markdown(findings: list[dict], bug_labels: dict[str, str], stamp: datetime) -> str:
    rows = finding_rows(findings, bug_labels)
    lines = [
        f"# C++ 메모리·초기화 버그 리포트 {stamp.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"발견 {len(rows)}건",
        "",
    ]
    if not rows:
        lines.append("보고할 메모리 버그와 초기화 버그가 없습니다.")
        return "\n".join(lines) + "\n"
    for index, row in enumerate(rows, start=1):
        lines.extend(
            [
                f"## {index}. {row['파일명']}:{row['줄 번호']} {row['함수명']}",
                "",
                f"- 버그 종류: {row['버그 종류']}",
                f"- 확신도: {row['확신도']}",
                f"- 근거: {row['근거']}",
                "",
                "### 현재 코드 (Before)",
                "",
                "```cpp",
                row["현재 코드"],
                "```",
                "",
                "### 수정 방향 및 제안 코드 (After)",
                "",
                "```cpp",
                row["수정 제안"],
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def save_reports(findings: list[dict], bug_labels: dict[str, str]) -> tuple[Path, Path]:
    """reports 폴더에 같은 시각의 .md와 .csv를 만든다."""
    REPORT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now()
    stem = stamp.strftime("%Y%m%d_%H%M%S")
    markdown_path = REPORT_DIR / f"{stem}.md"
    csv_path = REPORT_DIR / f"{stem}.csv"
    markdown_path.write_text(render_markdown(findings, bug_labels, stamp), encoding="utf-8")
    rows = finding_rows(findings, bug_labels)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return markdown_path, csv_path
