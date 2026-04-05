#!/usr/bin/env python3
"""Prepare a recipe for an actual brew date.

This is the first orchestration layer over the repo control plane.

Current responsibilities:
- resolve recipe + matching brew-day sheet
- rename an undated brew-day sheet to its dated canonical filename
- update ACTIVE_ARTIFACTS.json so validators treat the chosen artifacts as live
- optionally append a non-consumptive prepare event to brew_history.json
- optionally run `make trust-check`
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
BEERXML_DIR = RECIPES_DIR / "beer_xml_exports"
ACTIVE_ARTIFACTS_FILE = ROOT / "project_control" / "ACTIVE_ARTIFACTS.json"
BREW_HISTORY_FILE = ROOT / "libraries" / "inventory" / "brew_history.json"


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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


def derive_sheet_base(recipe_path: Path) -> str:
    stems = recipe_stem_candidates(recipe_path.stem)
    for stem in stems:
        undated = SHEETS_DIR / f"{stem}_brew_day_sheet.html"
        if undated.exists():
            return stem
        dated_matches = sorted(SHEETS_DIR.glob(f"{stem}_brew_day_sheet_*.html"))
        if dated_matches:
            return stem
    return stems[-1]


def resolve_brew_sheet(base: str, brew_date: str) -> tuple[Path | None, Path]:
    undated = SHEETS_DIR / f"{base}_brew_day_sheet.html"
    dated = SHEETS_DIR / f"{base}_brew_day_sheet_{brew_date}.html"
    if dated.exists():
        return None, dated
    if undated.exists():
        return undated, dated
    raise FileNotFoundError(
        f"No brew-day sheet found for base '{base}'. Expected {undated.name} or {dated.name}"
    )


def resolve_beerxml(recipe_path: Path) -> Path | None:
    candidate = BEERXML_DIR / f"{recipe_path.stem}.xml"
    return candidate if candidate.exists() else None


def update_active_artifacts(recipe_rel: str, sheet_rel: str, beerxml_rel: str | None) -> None:
    payload = load_json(ACTIVE_ARTIFACTS_FILE)
    pairs = payload.get("active_pairs", [])
    updated_pair = {"recipe": recipe_rel, "brew_sheet": sheet_rel}
    if beerxml_rel:
        updated_pair["beerxml"] = beerxml_rel

    replaced = False
    new_pairs = []
    for pair in pairs:
        if pair.get("recipe") == recipe_rel:
            new_pairs.append(updated_pair)
            replaced = True
        else:
            new_pairs.append(pair)
    if not replaced:
        new_pairs.append(updated_pair)
    payload["active_pairs"] = new_pairs

    active_files: list[str] = []
    for pair in new_pairs:
        for key in ("recipe", "brew_sheet", "beerxml"):
            value = pair.get(key)
            if value and value not in active_files:
                active_files.append(value)
    payload["hop_aa_active_files"] = active_files
    save_json(ACTIVE_ARTIFACTS_FILE, payload)


def append_prepare_event(recipe_path: Path, brew_sheet_path: Path, brew_date: str) -> None:
    payload = load_json(BREW_HISTORY_FILE)
    event = {
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "type": "prepare_brew",
        "recipe_id": recipe_path.stem,
        "recipe_file": recipe_path.relative_to(ROOT).as_posix(),
        "brew_date": brew_date,
        "brew_sheet": brew_sheet_path.relative_to(ROOT).as_posix(),
    }
    payload.setdefault("events", []).append(event)
    save_json(BREW_HISTORY_FILE, payload)


def validate_date(date_text: str) -> str:
    try:
        dt.date.fromisoformat(date_text)
    except ValueError as exc:
        raise ValueError(f"Invalid date '{date_text}'. Expected YYYY-MM-DD.") from exc
    return date_text


def refresh_embedded_schedule_dates(sheet_path: Path, brew_date: str) -> None:
    text = sheet_path.read_text(encoding="utf-8")
    brew_day = dt.date.fromisoformat(brew_date)

    anchor_pattern = re.compile(
        r'(<p class="small" style="margin-bottom:4px;"><strong>Schedule anchor:</strong> Brew day assumed <strong>)'
        r'(\d{4}-\d{2}-\d{2})'
        r'(</strong>\. Record actual pitch timestamp and adjust if brew day shifts\.</p>)'
    )
    text = anchor_pattern.sub(
        lambda m: f"{m.group(1)}{brew_date}{m.group(3)}",
        text,
    )

    row_pattern = re.compile(
        r'(<tr><td>)'
        r'(\d{4}-\d{2}-\d{2})'
        r'(<span class="blank-sm"></span> \([A-Za-z]{3}\)</td><td>)'
        r'(\d+)'
        r'(</td><td>)'
    )

    def replace_row(match: re.Match[str]) -> str:
        day_index = int(match.group(4))
        row_date = brew_day + dt.timedelta(days=day_index)
        weekday = row_date.strftime("%a")
        return f"{match.group(1)}{row_date.isoformat()} <span class=\"blank-sm\"></span> ({weekday}){match.group(3)}{match.group(4)}{match.group(5)}"

    text = row_pattern.sub(replace_row, text)
    sheet_path.write_text(text, encoding="utf-8")


def run_trust_check() -> int:
    proc = subprocess.run(["make", "trust-check"], cwd=ROOT)
    return proc.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare a recipe for a dated brew")
    parser.add_argument("--recipe", required=True, help="Recipe path, file stem, or slug token")
    parser.add_argument("--date", required=True, help="Brew date in YYYY-MM-DD")
    parser.add_argument("--run-trust-check", action="store_true", help="Run make trust-check after updating artifacts")
    parser.add_argument("--record-history", action="store_true", help="Append a non-consumptive prepare_brew event to brew_history.json")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without writing changes")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    brew_date = validate_date(args.date)
    recipe_path = resolve_recipe(args.recipe)
    base = derive_sheet_base(recipe_path)
    source_sheet, dated_sheet = resolve_brew_sheet(base, brew_date)
    beerxml_path = resolve_beerxml(recipe_path)

    recipe_rel = recipe_path.relative_to(ROOT).as_posix()
    dated_rel = dated_sheet.relative_to(ROOT).as_posix()
    beerxml_rel = beerxml_path.relative_to(ROOT).as_posix() if beerxml_path else None

    print("PREPARE BREW")
    print(f"recipe: {recipe_rel}")
    print(f"sheet base: {base}")
    if source_sheet:
        print(f"rename: {source_sheet.relative_to(ROOT).as_posix()} -> {dated_rel}")
    else:
        print(f"dated sheet: {dated_rel}")
    if beerxml_rel:
        print(f"beerxml: {beerxml_rel}")
    print("active artifacts: update")
    if args.record_history:
        print("brew_history: append prepare_brew event")

    if args.dry_run:
        return 0

    if source_sheet:
        source_sheet.rename(dated_sheet)

    refresh_embedded_schedule_dates(dated_sheet, brew_date)

    update_active_artifacts(recipe_rel, dated_rel, beerxml_rel)
    if args.record_history:
        append_prepare_event(recipe_path, dated_sheet, brew_date)

    if args.run_trust_check:
        return run_trust_check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
