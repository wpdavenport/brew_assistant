#!/usr/bin/env python3
"""Summarize current batch lifecycle state and packaged-yield trends."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_ARTIFACTS_FILE = ROOT / "project_control" / "ACTIVE_ARTIFACTS.json"
BREW_HISTORY_FILE = ROOT / "libraries" / "inventory" / "brew_history.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_recipe(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


def extract_date_from_sheet(path_text: str) -> str:
    match = re.search(r"_(\d{4}-\d{2}-\d{2})\.html$", path_text)
    return match.group(1) if match else ""


def to_gallons(volume: float, unit: str) -> float:
    unit_n = unit.strip().lower()
    if unit_n in {"gal", "gallon", "gallons"}:
        return volume
    if unit_n in {"l", "liter", "liters", "litre", "litres"}:
        return volume / 3.785411784
    raise ValueError(f"Unsupported packaged volume unit: {unit}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize current batch lifecycle state")
    parser.add_argument("--recipe", default="", help="Optional recipe id/name filter")
    parser.add_argument("--target-gal", type=float, default=5.0, help="Packaged yield target in gallons")
    return parser


def recipe_matches(filter_text: str, *values: str) -> bool:
    if not filter_text:
        return True
    needle = normalize_recipe(filter_text)
    return any(needle in normalize_recipe(value) for value in values if value)


def main() -> int:
    args = build_parser().parse_args()
    active = load_json(ACTIVE_ARTIFACTS_FILE)
    history = load_json(BREW_HISTORY_FILE)

    brew_events: dict[tuple[str, str], dict] = {}
    package_events: dict[tuple[str, str], dict] = {}
    package_by_recipe: dict[str, list[dict]] = defaultdict(list)

    for event in history.get("events", []):
        recipe_id = event.get("recipe_id", "")
        recipe_name = event.get("recipe_name", "")
        brew_date = event.get("brew_date", "")
        if not recipe_matches(args.recipe, recipe_id, recipe_name):
            continue
        if event.get("type") == "brew" and brew_date:
            brew_events[(recipe_id, brew_date)] = event
        elif event.get("type") == "package" and brew_date:
            package_events[(recipe_id, brew_date)] = event
            package_by_recipe[recipe_id].append(event)

    prepared_not_brewed: list[str] = []
    brewed_not_packaged: list[str] = []
    brewed_not_packaged_sheets: set[str] = set()

    for pair in active.get("active_pairs", []):
        recipe_rel = pair.get("recipe", "")
        brew_sheet = pair.get("brew_sheet", "")
        brew_date = extract_date_from_sheet(brew_sheet)
        recipe_id = Path(recipe_rel).stem
        recipe_label = Path(recipe_rel).name
        if not recipe_matches(args.recipe, recipe_id, recipe_label, recipe_rel):
            continue
        brewed = any(event.get("brew_sheet") == brew_sheet for event in brew_events.values())
        packaged = any(event.get("brew_sheet") == brew_sheet for event in package_events.values())
        if brew_date and not brewed:
            prepared_not_brewed.append(f"{recipe_label} | brew date {brew_date} | sheet {brew_sheet}")
        elif brew_date and brewed and not packaged:
            brewed_not_packaged_sheets.add(brew_sheet)
            brewed_not_packaged.append(f"{recipe_label} | brew date {brew_date} | sheet {brew_sheet}")

    for (recipe_id, brew_date), event in sorted(brew_events.items()):
        if (recipe_id, brew_date) in package_events:
            continue
        if event.get("brew_sheet", "") in brewed_not_packaged_sheets:
            continue
        recipe_name = event.get("recipe_name", recipe_id)
        line = f"{recipe_name} | brew date {brew_date} | sheet {event.get('brew_sheet', '')}"
        if line not in brewed_not_packaged:
            brewed_not_packaged.append(line)

    print("BATCH STATE SUMMARY")
    print("=" * 80)

    print("Prepared, Not Brewed")
    print("-" * 80)
    if prepared_not_brewed:
        for line in prepared_not_brewed:
            print(line)
    else:
        print("(none)")

    print("\nBrewed, Not Packaged")
    print("-" * 80)
    if brewed_not_packaged:
        for line in brewed_not_packaged:
            print(line)
    else:
        print("(none)")

    print("\nPackaged Yield Trend")
    print("-" * 80)
    if not package_by_recipe:
        print("(no package events)")
        return 0

    for recipe_id, events in sorted(package_by_recipe.items()):
        gallons = [to_gallons(float(event["packaged_volume"]), event.get("packaged_volume_unit", "gal")) for event in events]
        avg_gal = sum(gallons) / len(gallons)
        avg_delta = avg_gal - args.target_gal
        latest = max(events, key=lambda row: row.get("package_date", ""))
        latest_gal = to_gallons(float(latest["packaged_volume"]), latest.get("packaged_volume_unit", "gal"))
        latest_delta = latest_gal - args.target_gal
        print(
            f"{recipe_id}: n={len(events)} | latest {latest_gal:.2f} gal ({latest_delta:+.2f}) | "
            f"avg {avg_gal:.2f} gal ({avg_delta:+.2f})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
