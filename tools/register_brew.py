#!/usr/bin/env python3
"""Register a completed brew against inventory and brew history.

This is the post-brew companion to prepare_brew.py.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECIPES_DIR = ROOT / "recipes"
SHEETS_DIR = ROOT / "brewing" / "brew_day_sheets"
RECIPE_USAGE_FILE = ROOT / "libraries" / "inventory" / "recipe_usage.json"


def normalize_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def recipe_stem_candidates(stem: str) -> list[str]:
    candidates = [stem]
    candidates.append(re.sub(r"_clone_\d{1,2}[A-Z]$", "", stem))
    candidates.append(re.sub(r"_\d{1,2}[A-Z]$", "", stem))
    out: list[str] = []
    for value in candidates:
        if value and value not in out:
            out.append(value)
    return out


def resolve_recipe(token: str) -> Path:
    explicit = ROOT / token
    if explicit.exists() and explicit.suffix == ".md":
        return explicit.resolve()

    candidates = [
        path
        for path in RECIPES_DIR.rglob("*.md")
        if "historical" not in path.parts and "locked" not in path.parts and "in_development" not in path.parts
    ]
    token_n = normalize_token(token)
    exact = [path for path in candidates if normalize_token(path.stem) == token_n]
    if len(exact) == 1:
        return exact[0].resolve()

    stem_matches = []
    for path in candidates:
        for candidate in recipe_stem_candidates(path.stem):
            if normalize_token(candidate) == token_n:
                stem_matches.append(path)
                break
    stem_matches = sorted(set(stem_matches))
    if len(stem_matches) == 1:
        return stem_matches[0].resolve()
    raise ValueError(f"Could not resolve recipe from token: {token}")


def derive_base(recipe_path: Path) -> str:
    stems = recipe_stem_candidates(recipe_path.stem)
    for stem in stems:
        if (SHEETS_DIR / f"{stem}_brew_day_sheet.html").exists():
            return stem
        if sorted(SHEETS_DIR.glob(f"{stem}_brew_day_sheet_*.html")):
            return stem
    return stems[-1]


def resolve_dated_sheet(base: str, brew_date: str | None) -> tuple[Path, str]:
    if brew_date:
        candidate = SHEETS_DIR / f"{base}_brew_day_sheet_{brew_date}.html"
        if not candidate.exists():
            raise FileNotFoundError(f"Expected dated brew-day sheet not found: {candidate.relative_to(ROOT)}")
        return candidate.resolve(), brew_date

    matches = sorted(SHEETS_DIR.glob(f"{base}_brew_day_sheet_*.html"))
    if len(matches) == 1:
        match = matches[0]
        m = re.search(r"_(\d{4}-\d{2}-\d{2})\.html$", match.name)
        if not m:
            raise ValueError(f"Could not extract brew date from sheet: {match.name}")
        return match.resolve(), m.group(1)
    if not matches:
        raise FileNotFoundError(
            f"No dated brew-day sheet found for '{base}'. Register-brew requires a dated canonical sheet."
        )
    raise ValueError(f"Multiple dated brew-day sheets found for '{base}'. Pass --date explicitly.")


def recipe_usage_id(recipe_path: Path) -> str:
    payload = json.loads(RECIPE_USAGE_FILE.read_text(encoding="utf-8"))
    candidates = recipe_stem_candidates(recipe_path.stem)
    normalized_candidates = {normalize_token(value) for value in candidates}
    for recipe in payload.get("recipes", []):
        if normalize_token(recipe["id"]) in normalized_candidates:
            return recipe["id"]
        display = recipe.get("display_name", "")
        if normalize_token(display) in normalized_candidates:
            return recipe["id"]
        for alias in recipe.get("aliases", []):
            if normalize_token(alias) in normalized_candidates:
                return recipe["id"]
    raise ValueError(f"No recipe_usage.json entry found for recipe: {recipe_path.relative_to(ROOT).as_posix()}")


def valid_date(date_text: str) -> str:
    dt.date.fromisoformat(date_text)
    return date_text


def run_inventory_brew(recipe_id: str, brew_date: str, brew_sheet_rel: str, include_optional: bool, note: str) -> int:
    cmd = [
        sys.executable,
        "tools/inventory_cli.py",
        "brew",
        "--recipe",
        recipe_id,
        "--brew-date",
        brew_date,
        "--brew-sheet",
        brew_sheet_rel,
    ]
    if include_optional:
        cmd.append("--include-optional")
    if note:
        cmd.extend(["--note", note])
    proc = subprocess.run(cmd, cwd=ROOT)
    return proc.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Register a brewed batch against inventory/history")
    parser.add_argument("--recipe", required=True, help="Recipe path, file stem, or slug token")
    parser.add_argument("--date", default="", help="Brew date in YYYY-MM-DD; omit only if exactly one dated sheet exists")
    parser.add_argument("--include-optional", action="store_true", help="Include optional recipe_usage items")
    parser.add_argument("--note", default="", help="Optional note stored on the brew event")
    parser.add_argument("--dry-run", action="store_true", help="Resolve and print actions without mutating inventory")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    recipe_path = resolve_recipe(args.recipe)
    base = derive_base(recipe_path)
    brew_date = valid_date(args.date) if args.date else None
    brew_sheet_path, resolved_date = resolve_dated_sheet(base, brew_date)
    recipe_id = recipe_usage_id(recipe_path)
    brew_sheet_rel = brew_sheet_path.relative_to(ROOT).as_posix()
    recipe_rel = recipe_path.relative_to(ROOT).as_posix()

    print("REGISTER BREW")
    print(f"recipe: {recipe_rel}")
    print(f"recipe_usage id: {recipe_id}")
    print(f"brew date: {resolved_date}")
    print(f"dated sheet: {brew_sheet_rel}")
    print(f"include optional: {bool(args.include_optional)}")
    if args.note:
        print(f"note: {args.note}")

    if args.dry_run:
        return 0

    return run_inventory_brew(recipe_id, resolved_date, brew_sheet_rel, bool(args.include_optional), args.note)


if __name__ == "__main__":
    raise SystemExit(main())
