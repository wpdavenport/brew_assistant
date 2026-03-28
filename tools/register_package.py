#!/usr/bin/env python3
"""Register packaging for a brewed batch and optional harvested yeast."""

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
        if sorted(SHEETS_DIR.glob(f"{stem}_brew_day_sheet_*.html")):
            return stem
    return stems[-1]


def resolve_dated_sheet(base: str, brew_date: str) -> Path:
    candidate = SHEETS_DIR / f"{base}_brew_day_sheet_{brew_date}.html"
    if not candidate.exists():
        raise FileNotFoundError(f"Expected dated brew-day sheet not found: {candidate.relative_to(ROOT)}")
    return candidate.resolve()


def recipe_usage_entry(recipe_path: Path) -> dict:
    payload = json.loads(RECIPE_USAGE_FILE.read_text(encoding="utf-8"))
    candidates = recipe_stem_candidates(recipe_path.stem)
    normalized_candidates = {normalize_token(value) for value in candidates}
    for recipe in payload.get("recipes", []):
        if normalize_token(recipe["id"]) in normalized_candidates:
            return recipe
        if normalize_token(recipe.get("display_name", "")) in normalized_candidates:
            return recipe
        for alias in recipe.get("aliases", []):
            if normalize_token(alias) in normalized_candidates:
                return recipe
    raise ValueError(f"No recipe_usage.json entry found for recipe: {recipe_path.relative_to(ROOT).as_posix()}")


def valid_date(date_text: str) -> str:
    dt.date.fromisoformat(date_text)
    return date_text


def run_inventory_package(entry: dict, brew_date: str, package_date: str, brew_sheet_rel: str, fg: float, packaged_volume: float, packaged_volume_unit: str, co2_vols: str, harvest_item: str, harvest_amount: float, harvest_unit: str, note: str) -> int:
    cmd = [
        sys.executable,
        "tools/inventory_cli.py",
        "package",
        "--recipe-id",
        entry["id"],
        "--recipe-name",
        entry["display_name"],
        "--brew-date",
        brew_date,
        "--package-date",
        package_date,
        "--brew-sheet",
        brew_sheet_rel,
        "--fg",
        str(fg),
        "--packaged-volume",
        str(packaged_volume),
        "--packaged-volume-unit",
        packaged_volume_unit,
    ]
    if co2_vols:
        cmd.extend(["--co2-vols", co2_vols])
    if harvest_item and harvest_amount > 0 and harvest_unit:
        cmd.extend(["--harvest-item", harvest_item, "--harvest-amount", str(harvest_amount), "--harvest-unit", harvest_unit])
    if note:
        cmd.extend(["--note", note])
    proc = subprocess.run(cmd, cwd=ROOT)
    return proc.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Register packaging and optional harvested yeast")
    parser.add_argument("--recipe", required=True, help="Recipe path, file stem, or slug token")
    parser.add_argument("--brew-date", required=True, help="Brew date in YYYY-MM-DD")
    parser.add_argument("--package-date", default=dt.date.today().isoformat(), help="Package date in YYYY-MM-DD")
    parser.add_argument("--fg", required=True, type=float, help="FG at packaging, e.g. 1.013")
    parser.add_argument("--packaged-volume", required=True, type=float, help="Packaged volume")
    parser.add_argument("--packaged-volume-unit", default="gal", help="Unit for packaged volume")
    parser.add_argument("--co2-vols", default="", help="Optional carbonation level in vols CO2")
    parser.add_argument("--harvest-item", default="", help="Optional inventory item id to add after packaging")
    parser.add_argument("--harvest-amount", type=float, default=0.0, help="Amount of harvested item to add")
    parser.add_argument("--harvest-unit", default="", help="Unit for harvested item amount")
    parser.add_argument("--note", default="", help="Optional note stored on the package event")
    parser.add_argument("--dry-run", action="store_true", help="Resolve and print actions without mutating inventory")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    recipe_path = resolve_recipe(args.recipe)
    brew_date = valid_date(args.brew_date)
    package_date = valid_date(args.package_date)
    base = derive_base(recipe_path)
    brew_sheet_path = resolve_dated_sheet(base, brew_date)
    entry = recipe_usage_entry(recipe_path)
    recipe_rel = recipe_path.relative_to(ROOT).as_posix()
    brew_sheet_rel = brew_sheet_path.relative_to(ROOT).as_posix()

    print("REGISTER PACKAGE")
    print(f"recipe: {recipe_rel}")
    print(f"recipe_usage id: {entry['id']}")
    print(f"brew date: {brew_date}")
    print(f"package date: {package_date}")
    print(f"dated sheet: {brew_sheet_rel}")
    print(f"fg: {args.fg:.3f}")
    print(f"packaged volume: {args.packaged_volume:.2f} {args.packaged_volume_unit}")
    if args.co2_vols:
        print(f"co2 vols: {args.co2_vols}")
    if args.harvest_item and args.harvest_amount > 0 and args.harvest_unit:
        print(f"harvest: {args.harvest_item} +{args.harvest_amount} {args.harvest_unit}")
    if args.note:
        print(f"note: {args.note}")

    if args.dry_run:
        return 0

    return run_inventory_package(
        entry,
        brew_date,
        package_date,
        brew_sheet_rel,
        args.fg,
        args.packaged_volume,
        args.packaged_volume_unit,
        args.co2_vols,
        args.harvest_item,
        args.harvest_amount,
        args.harvest_unit,
        args.note,
    )


if __name__ == "__main__":
    raise SystemExit(main())
