#!/usr/bin/env python3
"""Capture a durable brewing insight and route it to the right repo surfaces."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTER_FILE = ROOT / "project_control" / "insight_register.json"


ROUTING_RULES = {
    "inventory": {
        "keywords": ("inventory", "stock", "on hand", "restock", "shopping", "buy", "purchase"),
        "files": [
            "libraries/inventory/stock.json",
            "libraries/inventory/shopping_intent.json",
            "knowledge_index.md",
            "system_prompt.md",
        ],
        "checks": [
            "confirm inventory schema still matches CLI expectations",
        ],
    },
    "recipe": {
        "keywords": ("recipe", "clone", "iteration", "version", "lock", "style"),
        "files": [
            "recipes/",
            "recipes/html_exports/",
            "system_prompt.md",
        ],
        "checks": [
            "confirm the intended canonical recipe is still obvious",
        ],
    },
    "brew_sheet": {
        "keywords": ("brew sheet", "brew-day", "printable", "header", "timed addition", "log row"),
        "files": [
            "brewing/brew_day_sheets/",
            "system_prompt.md",
        ],
        "checks": [
            "confirm yeast source, generation, starter method, and dated schedule are explicit",
        ],
    },
    "measurement": {
        "keywords": ("ph", "meter", "gravity", "refractometer", "hydrometer", "measurement"),
        "files": [
            "system_prompt.md",
            "knowledge_index.md",
        ],
        "checks": [
            "python3 tools/prompt_harness.py eval-all",
        ],
    },
    "ui": {
        "keywords": ("ui", "viewer", "web", "button", "banner", "sticky", "form", "nav"),
        "files": [
            "tools/web_ui.py",
            "README.md",
        ],
        "checks": [
            "python3 tools/drift_review.py",
        ],
    },
    "service": {
        "keywords": ("launch", "launcher", "launchagent", "service", "bootstrap", "background", "windows", "linux", "mac"),
        "files": [
            "tools/web_ui_service.py",
            "tools/web_ui_bootstrap.py",
            "README.md",
        ],
        "checks": [
            "python3 tools/drift_review.py",
        ],
    },
    "prompt": {
        "keywords": ("guardrail", "prompt", "system", "rule", "preference", "default"),
        "files": [
            "system_prompt.md",
            "knowledge_index.md",
            "project_control/DRIFT_MATRIX.md",
        ],
        "checks": [
            "python3 tools/prompt_harness.py eval-all",
        ],
    },
}


def load_register() -> dict:
    return json.loads(REGISTER_FILE.read_text(encoding="utf-8"))


def save_register(payload: dict) -> None:
    REGISTER_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "insight"


def detect_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags: list[str] = []
    for tag, rule in ROUTING_RULES.items():
        if any(keyword in lowered for keyword in rule["keywords"]):
            tags.append(tag)
    if not tags:
        tags.append("prompt")
    return tags


def recommended_files(tags: list[str]) -> list[str]:
    out: list[str] = []
    for tag in tags:
        for path in ROUTING_RULES[tag]["files"]:
            if path not in out:
                out.append(path)
    return out


def recommended_checks(tags: list[str]) -> list[str]:
    out: list[str] = []
    for tag in tags:
        for check in ROUTING_RULES[tag]["checks"]:
            if check not in out:
                out.append(check)
    return out


def build_entry(text: str, source: str, status: str) -> dict:
    today = dt.date.today().isoformat()
    tags = detect_tags(text)
    return {
        "id": f"{today}-{slugify(text)}",
        "captured_on": today,
        "source": source,
        "status": status,
        "text": text.strip(),
        "tags": tags,
        "recommended_files": recommended_files(tags),
        "recommended_checks": recommended_checks(tags),
        "integration_note": "Capture into repo state, not just chat memory.",
    }


def render_entry(entry: dict) -> str:
    lines = [
        "INSIGHT INTAKE",
        f"id: {entry['id']}",
        f"captured_on: {entry['captured_on']}",
        f"source: {entry['source']}",
        f"status: {entry['status']}",
        f"text: {entry['text']}",
        "tags: " + ", ".join(entry["tags"]),
        "recommended files:",
    ]
    lines.extend(f"- {path}" for path in entry["recommended_files"])
    lines.append("recommended checks:")
    lines.extend(f"- {check}" for check in entry["recommended_checks"])
    lines.append(f"note: {entry['integration_note']}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture a durable brewing insight")
    parser.add_argument("--text", required=True, help="Insight text to capture")
    parser.add_argument("--source", default="chat", help="Where the insight came from")
    parser.add_argument("--status", default="captured", choices=["captured", "integrating", "integrated"], help="Initial integration status")
    parser.add_argument("--record", action="store_true", help="Append the insight to project_control/insight_register.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    entry = build_entry(args.text, args.source, args.status)
    print(render_entry(entry))
    if not args.record:
        return 0
    payload = load_register()
    payload.setdefault("entries", []).append(entry)
    save_register(payload)
    print(f"INSIGHT_REGISTERED {REGISTER_FILE.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
