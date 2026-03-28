#!/usr/bin/env python3
"""High-level brew lifecycle orchestration.

Decides whether a recipe should be prepared, brew-registered, or package-registered
based on current repo state and the arguments provided.
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
ACTIVE_ARTIFACTS_FILE = ROOT / "project_control" / "ACTIVE_ARTIFACTS.json"
BREW_HISTORY_FILE = ROOT / "libraries" / "inventory" / "brew_history.json"
RECIPE_USAGE_FILE = ROOT / "libraries" / "inventory" / "recipe_usage.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def recipe_usage_id(recipe_path: Path) -> str | None:
    payload = load_json(RECIPE_USAGE_FILE)
    candidates = recipe_stem_candidates(recipe_path.stem)
    normalized_candidates = {normalize_token(value) for value in candidates}
    for recipe in payload.get("recipes", []):
        if normalize_token(recipe["id"]) in normalized_candidates:
            return recipe["id"]
        if normalize_token(recipe.get("display_name", "")) in normalized_candidates:
            return recipe["id"]
        for alias in recipe.get("aliases", []):
            if normalize_token(alias) in normalized_candidates:
                return recipe["id"]
    return None


def extract_date_from_sheet(path_text: str) -> str:
    match = re.search(r"_(\d{4}-\d{2}-\d{2})\.html$", path_text)
    if not match:
        raise ValueError(f"Could not extract brew date from sheet path: {path_text}")
    return match.group(1)


def active_brew_date(recipe_path: Path) -> str | None:
    payload = load_json(ACTIVE_ARTIFACTS_FILE)
    recipe_rel = recipe_path.relative_to(ROOT).as_posix()
    for pair in payload.get("active_pairs", []):
        if pair.get("recipe") == recipe_rel:
            brew_sheet = pair.get("brew_sheet", "")
            if re.search(r"_\d{4}-\d{2}-\d{2}\.html$", brew_sheet):
                return extract_date_from_sheet(brew_sheet)
    return None


def dated_sheet_dates(base: str) -> list[str]:
    dates: list[str] = []
    for path in sorted(SHEETS_DIR.glob(f"{base}_brew_day_sheet_*.html")):
        dates.append(extract_date_from_sheet(path.name))
    return dates


def choose_brew_date(recipe_path: Path, explicit_date: str) -> str:
    if explicit_date:
        dt.date.fromisoformat(explicit_date)
        return explicit_date
    active_date = active_brew_date(recipe_path)
    if active_date:
        return active_date
    base = derive_base(recipe_path)
    dates = dated_sheet_dates(base)
    if len(dates) == 1:
        return dates[0]
    return dt.date.today().isoformat()


def brew_exists(recipe_id: str, brew_date: str) -> bool:
    payload = load_json(BREW_HISTORY_FILE)
    for event in payload.get("events", []):
        if event.get("type") == "brew" and event.get("recipe_id") == recipe_id and event.get("brew_date") == brew_date:
            return True
    return False


def package_exists(recipe_id: str, brew_date: str) -> bool:
    payload = load_json(BREW_HISTORY_FILE)
    for event in payload.get("events", []):
        if event.get("type") == "package" and event.get("recipe_id") == recipe_id and event.get("brew_date") == brew_date:
            return True
    return False


def dated_sheet_exists(base: str, brew_date: str) -> bool:
    return (SHEETS_DIR / f"{base}_brew_day_sheet_{brew_date}.html").exists()


def undated_sheet_exists(base: str) -> bool:
    return (SHEETS_DIR / f"{base}_brew_day_sheet.html").exists()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="High-level brew lifecycle action runner")
    parser.add_argument("--recipe", required=True, help="Recipe path, file stem, or slug token")
    parser.add_argument("--date", default="", help="Brew date in YYYY-MM-DD; defaults from active sheet or today")
    parser.add_argument("--run-trust-check", action="store_true", help="Run trust-check if action resolves to prepare-brew")
    parser.add_argument("--record-history", action="store_true", help="Record prepare_brew event if action resolves to prepare-brew")
    parser.add_argument("--include-optional", action="store_true", help="Include optional recipe items if action resolves to register-brew")
    parser.add_argument("--note", default="", help="Optional note forwarded to brew/package registration")
    parser.add_argument("--package-date", default="", help="Package date for package registration")
    parser.add_argument("--fg", default="", help="FG for package registration")
    parser.add_argument("--packaged-volume", default="", help="Packaged volume for package registration")
    parser.add_argument("--packaged-volume-unit", default="gal", help="Packaged volume unit")
    parser.add_argument("--co2-vols", default="", help="Optional carbonation level")
    parser.add_argument("--harvest-yeast", default="", help="Harvested yeast token for package registration")
    parser.add_argument("--harvest-generation", type=int, default=0, help="Harvested yeast generation")
    parser.add_argument("--harvest-count", type=float, default=1.0, help="Harvested slurry amount")
    parser.add_argument("--dry-run", action="store_true", help="Show the chosen action without mutating state")
    return parser


def run_command(cmd: list[str], dry_run: bool) -> int:
    print("command:", " ".join(cmd))
    if dry_run:
        return 0
    return subprocess.run(cmd, cwd=ROOT).returncode


def main() -> int:
    args = build_parser().parse_args()
    recipe_path = resolve_recipe(args.recipe)
    recipe_id = recipe_usage_id(recipe_path)
    base = derive_base(recipe_path)
    brew_date = choose_brew_date(recipe_path, args.date)

    wants_package = bool(args.fg or args.packaged_volume or args.package_date or args.harvest_yeast or args.co2_vols)
    has_dated_sheet = dated_sheet_exists(base, brew_date)
    has_undated_sheet = undated_sheet_exists(base)
    has_brew = bool(recipe_id) and brew_exists(recipe_id, brew_date)
    has_package = bool(recipe_id) and package_exists(recipe_id, brew_date)

    if wants_package:
        if not recipe_id:
            raise ValueError(f"Package registration requires a recipe_usage.json entry for {recipe_path.relative_to(ROOT).as_posix()}")
        if has_package:
            raise ValueError(f"Batch already packaged for {recipe_id} on brew date {brew_date}")
        if not args.fg or not args.packaged_volume:
            raise ValueError("Package registration requires both --fg and --packaged-volume")
        action = "register-package"
        cmd = [
            sys.executable,
            "tools/register_package.py",
            "--recipe",
            args.recipe,
            "--brew-date",
            brew_date,
            "--package-date",
            args.package_date or dt.date.today().isoformat(),
            "--fg",
            args.fg,
            "--packaged-volume",
            args.packaged_volume,
            "--packaged-volume-unit",
            args.packaged_volume_unit,
        ]
        if args.co2_vols:
            cmd.extend(["--co2-vols", args.co2_vols])
        if args.harvest_yeast:
            cmd.extend(["--harvest-yeast", args.harvest_yeast])
            if args.harvest_generation:
                cmd.extend(["--harvest-generation", str(args.harvest_generation)])
            if args.harvest_count != 1.0:
                cmd.extend(["--harvest-count", str(args.harvest_count)])
        if args.note:
            cmd.extend(["--note", args.note])
    elif has_dated_sheet and not has_brew:
        if not recipe_id:
            raise ValueError(f"Brew registration requires a recipe_usage.json entry for {recipe_path.relative_to(ROOT).as_posix()}")
        action = "register-brew"
        cmd = [
            sys.executable,
            "tools/register_brew.py",
            "--recipe",
            args.recipe,
            "--date",
            brew_date,
        ]
        if args.include_optional:
            cmd.append("--include-optional")
        if args.note:
            cmd.extend(["--note", args.note])
    elif has_brew and not has_package:
        raise ValueError(
            f"Brew already registered for {recipe_id} on {brew_date}. "
            "Provide --fg and --packaged-volume to advance to package registration."
        )
    else:
        action = "prepare-brew"
        cmd = [
            sys.executable,
            "tools/prepare_brew.py",
            "--recipe",
            args.recipe,
            "--date",
            brew_date,
        ]
        if args.run_trust_check:
            cmd.append("--run-trust-check")
        if args.record_history:
            cmd.append("--record-history")

    if args.dry_run:
        cmd.append("--dry-run")

    print("BATCH LIFECYCLE")
    print(f"recipe: {recipe_path.relative_to(ROOT).as_posix()}")
    print(f"recipe_usage id: {recipe_id or '(none)'}")
    print(f"brew date: {brew_date}")
    print(f"dated sheet exists: {has_dated_sheet}")
    print(f"undated sheet exists: {has_undated_sheet}")
    print(f"brew event exists: {has_brew}")
    print(f"package event exists: {has_package}")
    print(f"chosen action: {action}")
    return run_command(cmd, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
