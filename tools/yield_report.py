#!/usr/bin/env python3
"""Report packaged yield by recipe from brew history."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BREW_HISTORY_FILE = ROOT / "libraries" / "inventory" / "brew_history.json"


def to_gallons(volume: float, unit: str) -> float:
    unit_n = unit.strip().lower()
    if unit_n in {"gal", "gallon", "gallons"}:
        return volume
    if unit_n in {"l", "liter", "liters", "litre", "litres"}:
        return volume / 3.785411784
    raise ValueError(f"Unsupported packaged volume unit: {unit}")


def normalize_recipe(recipe_id: str) -> str:
    return "".join(ch.lower() for ch in recipe_id if ch.isalnum())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report packaged yield from brew history")
    parser.add_argument("--recipe", default="", help="Optional recipe id/name filter")
    parser.add_argument("--target-gal", type=float, default=5.0, help="Reference packaged target in gallons")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    history = json.loads(BREW_HISTORY_FILE.read_text(encoding="utf-8"))
    recipe_filter = normalize_recipe(args.recipe) if args.recipe else ""
    package_events = [
        event
        for event in history.get("events", [])
        if event.get("type") == "package"
        and (not recipe_filter or recipe_filter in normalize_recipe(event.get("recipe_id", "")) or recipe_filter in normalize_recipe(event.get("recipe_name", "")))
    ]

    if not package_events:
        print("YIELD_REPORT_EMPTY")
        print("No package events found.")
        return 0

    grouped: dict[str, list[dict]] = defaultdict(list)
    for event in package_events:
        grouped[event["recipe_id"]].append(event)

    print("YIELD REPORT")
    print("=" * 80)
    for event in sorted(package_events, key=lambda row: (row.get("recipe_id", ""), row.get("brew_date", ""), row.get("package_date", ""))):
        packaged_gal = to_gallons(float(event["packaged_volume"]), event.get("packaged_volume_unit", "gal"))
        delta = packaged_gal - args.target_gal
        print(
            f"{event['recipe_name']} | brew {event.get('brew_date', '?')} | package {event.get('package_date', '?')} | "
            f"{packaged_gal:.2f} gal | delta {delta:+.2f} gal"
        )

    print("\nSUMMARY")
    print("=" * 80)
    for recipe_id, events in sorted(grouped.items()):
        gallons = [to_gallons(float(event["packaged_volume"]), event.get("packaged_volume_unit", "gal")) for event in events]
        avg_gal = sum(gallons) / len(gallons)
        avg_delta = avg_gal - args.target_gal
        print(f"{recipe_id}: n={len(events)} | avg {avg_gal:.2f} gal | avg delta {avg_delta:+.2f} gal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
