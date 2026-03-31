#!/usr/bin/env python3
"""Validate that BJCP study questions are source-backed."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUESTION_BANK = ROOT / "libraries" / "bjcp_study" / "question_bank.json"


def main() -> int:
    payload = json.loads(QUESTION_BANK.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])
    failures: list[str] = []

    for question in questions:
        qid = question.get("id", "<missing-id>")
        source = question.get("source")
        if not isinstance(source, dict):
            failures.append(f"{qid}: missing source object")
            continue
        for field in ("pdf", "section", "subsection", "basis"):
            if not str(source.get(field, "")).strip():
                failures.append(f"{qid}: missing source.{field}")
        pdf_rel = source.get("pdf", "")
        if pdf_rel:
            pdf_path = ROOT / pdf_rel
            if not pdf_path.exists():
                failures.append(f"{qid}: source pdf not found: {pdf_rel}")

    if failures:
        print("BJCP_QUESTION_SOURCE_FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("BJCP_QUESTION_SOURCE_OK")
    print(f"questions: {len(questions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
