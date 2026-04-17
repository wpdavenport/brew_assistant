#!/usr/bin/env python3
"""Validate printable HTML artifacts for basic readability expectations."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECIPE_HTML_DIR = ROOT / "recipes" / "html_exports"
BREW_SHEETS_DIR = ROOT / "brewing" / "brew_day_sheets"

RECIPE_REQUIRED_HEADINGS = (
    "<h2>Grains</h2>",
    "<h2>Hops</h2>",
    "<h2>Yeast</h2>",
    "<h2>Mash Schedule</h2>",
    "<h2>Fermentation Schedule</h2>",
)

BREW_SHEET_GRAIN_MARKERS = (
    "Grain Bill",
    "Grains",
)

BREW_SHEET_MASH_OR_WATER_MARKERS = (
    "Water Chemistry",
    "Mash Program",
    "Historical Mash And Boil",
    "Mash In",
)

BREW_SHEET_FERMENTATION_MARKERS = (
    "Fermentation",
    "Yeast And Fermentation",
    "Fermentation Skeleton",
    "Fermentation gates",
)


def check_recipe_html(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    failures: list[str] = []
    for heading in RECIPE_REQUIRED_HEADINGS:
        if heading not in text:
            failures.append(f"missing heading {heading}")
    if re.search(r"\(0\.\d+\s*kg\)", text):
        failures.append("contains sub-1kg metric display; expected grams")
    return failures


def check_brew_sheet(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    failures: list[str] = []
    is_tips_sheet = "tips" in path.name.lower()
    if not is_tips_sheet and not any(marker in text for marker in BREW_SHEET_GRAIN_MARKERS):
        failures.append("missing grain section marker")
    if not any(marker in text for marker in BREW_SHEET_MASH_OR_WATER_MARKERS):
        failures.append("missing mash/water section marker")
    if not any(marker in text for marker in BREW_SHEET_FERMENTATION_MARKERS):
        failures.append("missing fermentation section marker")
    if re.search(r"\(0\.\d+\s*kg\)", text):
        failures.append("contains sub-1kg metric display; expected grams")
    return failures


def main() -> int:
    failures: list[str] = []

    for path in sorted(RECIPE_HTML_DIR.glob("*.html")):
        for problem in check_recipe_html(path):
            failures.append(f"{path.relative_to(ROOT)}: {problem}")

    for path in sorted(BREW_SHEETS_DIR.rglob("*.html")):
        for problem in check_brew_sheet(path):
            failures.append(f"{path.relative_to(ROOT)}: {problem}")

    if failures:
        print("PRINT_READABILITY_FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PRINT_READABILITY_OK")
    print(f"recipe_html: {len(list(RECIPE_HTML_DIR.glob('*.html')))}")
    print(f"brew_sheets: {len(list(BREW_SHEETS_DIR.rglob('*.html')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
