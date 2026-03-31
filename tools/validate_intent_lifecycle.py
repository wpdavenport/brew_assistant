#!/usr/bin/env python3
"""Validate that shopping intent and actual batch lifecycle are not contradicting each other."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from batch_state_summary import build_intent_lifecycle_report


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_ARTIFACTS_FILE = ROOT / "project_control" / "ACTIVE_ARTIFACTS.json"
BREW_HISTORY_FILE = ROOT / "libraries" / "inventory" / "brew_history.json"
SHOPPING_INTENT_FILE = ROOT / "libraries" / "inventory" / "shopping_intent.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    active = load_json(ACTIVE_ARTIFACTS_FILE)
    history = load_json(BREW_HISTORY_FILE)
    shopping_intent = load_json(SHOPPING_INTENT_FILE) if SHOPPING_INTENT_FILE.exists() else {}

    brew_events: dict[tuple[str, str], dict] = {}
    package_events: dict[tuple[str, str], dict] = {}

    for event in history.get("events", []):
        recipe_id = event.get("recipe_id", "")
        brew_date = event.get("brew_date", "")
        if event.get("type") == "brew" and recipe_id and brew_date:
            brew_events[(recipe_id, brew_date)] = event
        elif event.get("type") == "package" and recipe_id and brew_date:
            package_events[(recipe_id, brew_date)] = event

    lines, failures = build_intent_lifecycle_report("", active, shopping_intent, brew_events, package_events)
    if failures:
        print("INTENT_LIFECYCLE_FAILED")
        for line in failures:
            print(f"- {line}")
        return 1

    print("INTENT_LIFECYCLE_OK")
    for line in lines:
        print(f"- {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
