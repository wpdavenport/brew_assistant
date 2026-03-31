#!/usr/bin/env python3
"""Summarize BJCP question-bank coverage."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUESTION_BANK = ROOT / "libraries" / "bjcp_study" / "question_bank.json"


def main() -> int:
    payload = json.loads(QUESTION_BANK.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])
    by_topic = Counter()
    by_section = Counter()

    for question in questions:
        by_topic[str(question.get("topic", "unknown"))] += 1
        source = question.get("source", {})
        section = str(source.get("section", "unknown")).strip() or "unknown"
        subsection = str(source.get("subsection", "")).strip()
        label = f"{section} :: {subsection}" if subsection else section
        by_section[label] += 1

    print("BJCP_QUESTION_REPORT")
    print(f"questions: {len(questions)}")

    print("\nby_topic:")
    for topic, count in sorted(by_topic.items()):
        print(f"- {topic}: {count}")

    print("\nby_source_section:")
    for section, count in sorted(by_section.items()):
        print(f"- {section}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
