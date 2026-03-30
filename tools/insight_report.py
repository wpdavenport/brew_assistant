#!/usr/bin/env python3
"""Summarize captured durable insights."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTER_FILE = ROOT / "project_control" / "insight_register.json"


def load_register() -> dict:
    return json.loads(REGISTER_FILE.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize captured brewing insights")
    parser.add_argument("--status", default="", help="Optional status filter")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = load_register()
    entries = payload.get("entries", [])
    if args.status:
        entries = [entry for entry in entries if entry.get("status") == args.status]

    print("INSIGHT REPORT")
    print("=" * 80)
    print(f"count: {len(entries)}")
    if not entries:
        print("(no entries)")
        return 0

    tag_counts = Counter(tag for entry in entries for tag in entry.get("tags", []))
    print("tags:")
    for tag, count in sorted(tag_counts.items()):
        print(f"- {tag}: {count}")

    print("\nrecent:")
    for entry in entries[-10:]:
        print(f"- {entry.get('captured_on', '')} | {entry.get('status', '')} | {entry.get('id', '')}")
        print(f"  {entry.get('text', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
