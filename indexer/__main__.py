"""헤더 심볼 인덱스를 만들거나 상태를 본다."""

from __future__ import annotations

import argparse

from symbol_index import build_index, index_status


def main() -> int:
    parser = argparse.ArgumentParser(description="헤더 심볼 SQLite 인덱스를 다룹니다.")
    parser.add_argument("command", choices=["build", "update", "status"])
    args = parser.parse_args()
    if args.command == "status":
        status = index_status()
    else:
        status = build_index(full=args.command == "build")
    print(f"파일 {status['files']}개, 심볼 {status['symbols']}개")
    if "updated" in status:
        print(f"갱신 {status['updated']}개, 그대로 {status['unchanged']}개")
    for item in status["skipped"]:
        print(f"경고 {item['path']}: {item['message']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
