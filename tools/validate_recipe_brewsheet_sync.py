#!/usr/bin/env python3
"""Validate recipe markdown against brew-day-sheet HTML.

Initial scope:
- target OG / FG alignment
- fermentable line-item alignment
- hop-schedule line-item alignment
- grouped addition detection in boil-execution log
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECIPES_DIR = ROOT / "recipes"
SHEETS_DIR = ROOT / "brewing" / "brew_day_sheets"
ACTIVE_ARTIFACTS_FILE = ROOT / "project_control" / "ACTIVE_ARTIFACTS.json"
EXCLUDED_RECIPE_PARTS = {"historical", "beer_xml_exports", "beer_xml_imports"}
BREWSHEET_OPTIONAL_RECIPES = {
    "house_starter_wort_concentrate",
    "manhattan_belgian_dark_strong_ale",
    "tempest_34B",
}

RE_OG = re.compile(r"- OG:\s*([0-9.\-]+)")
RE_FG = re.compile(r"- FG:\s*([0-9.\-]+)")
RE_FERM_LINE = re.compile(r"^- ([0-9.]+) lb \(([0-9.]+) kg\) (.+)$")
RE_HOP_LINE = re.compile(r"^- ([0-9.]+) oz \(([0-9.]+) g\) (.+?) - (.+)$")

RE_HTML_TARGET_ROW = re.compile(
    r"<td class=\"bold\">(OG|FG)</td><td>([0-9.\-]+)</td>", re.IGNORECASE
)
RE_HTML_GRAIN_ROW = re.compile(
    r"<tr(?: class=\"highlight-row\")?><td(?: class=\"bold\")?>([^<]+)</td><td class=\"right(?: bold)?\">[^<]*\(([0-9.]+)\s*(kg|g)\)</td><td>[^<]*</td><td class=\"center\">",
    re.IGNORECASE,
)
RE_HTML_HOP_ROW = re.compile(
    r"<tr(?: class=\"highlight-row\")?><td>([^<]+)</td><td(?: class=\"bold\")?>([^<]+)</td><td class=\"right(?: bold)?\">[^<]*\(([0-9.]+) g\)</td><td>[^<]+</td><td>[^<]*</td><td class=\"center\">",
    re.IGNORECASE,
)
RE_EXECUTION_SECTION = re.compile(
    r"<h2>3\. Boil Hop Additions \(\d+ Minutes\)</h2>\s*<table>(.*?)</table>",
    re.IGNORECASE | re.DOTALL,
)
RE_EXECUTION_ACTION_CELL = re.compile(r"<tr><td[^>]*>[^<]*</td><td>([^<]+)</td>", re.IGNORECASE)


def normalize_name(text: str) -> str:
    text = text.lower()
    text = text.replace("&amp;", "and")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


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


def brew_sheet_match_tokens(stem: str) -> list[str]:
    base = re.sub(r"_brew_day_sheet(?:_\d{4}-\d{2}-\d{2})?$", "", stem)
    tokens = [base]
    if base.endswith("_esb"):
        tokens.append(base[: -len("_esb")])
    out: list[str] = []
    for value in tokens:
        norm = normalize_token(value)
        if norm and norm not in out:
            out.append(norm)
    return out


def amount_close(a: float, b: float, tol: float = 0.02) -> bool:
    return abs(a - b) <= tol


def name_matches(a: str, b: str) -> bool:
    na = normalize_name(a)
    nb = normalize_name(b)
    if na == nb or na in nb or nb in na:
        return True
    ta = set(na.split())
    tb = set(nb.split())
    return ta == tb or ta.issubset(tb) or tb.issubset(ta)


def clean_recipe_hop_name(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", text).strip()


def normalize_timing(text: str) -> str:
    t = normalize_name(text)
    if t == "mash hop" or t.startswith("mash hop "):
        return "mash"
    if t == "mash":
        return "mash"
    if t == "fwh":
        return "first wort"
    if t.startswith("first wort"):
        return "first wort"
    if t.startswith("hop stand"):
        return "0 min"
    if t == "flameout" or t.startswith("flameout "):
        return "0 min"
    if t.startswith("0 min"):
        return "0 min"
    return t


def parse_recipe(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    data: dict[str, object] = {"og": None, "fg": None, "fermentables": [], "hops": []}
    section = ""
    subsection = ""

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            section = line[3:].strip().lower()
            subsection = ""
        elif line.startswith("### "):
            subsection = line[4:].strip().lower()

        if data["og"] is None:
            m = RE_OG.match(line)
            if m:
                data["og"] = m.group(1)
        if data["fg"] is None:
            m = RE_FG.match(line)
            if m:
                data["fg"] = m.group(1)

        if section == "fermentables":
            m = RE_FERM_LINE.match(line)
            if m:
                data["fermentables"].append(
                    {"kg": float(m.group(2)), "name": m.group(3).strip()}
                )
        elif section.startswith("hops"):
            if "boil / whirlpool" in subsection:
                m = RE_HOP_LINE.match(line)
                if m:
                    data["hops"].append(
                        {
                            "g": float(m.group(2)),
                            "name": clean_recipe_hop_name(m.group(3).strip()),
                            "timing": normalize_timing(m.group(4).strip()),
                        }
                    )
    return data


def parse_sheet(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    data: dict[str, object] = {"og": None, "fg": None, "fermentables": [], "hops": [], "grouped_actions": []}

    for key, value in RE_HTML_TARGET_ROW.findall(text):
        if key.upper() == "OG":
            data["og"] = value
        elif key.upper() == "FG":
            data["fg"] = value

    for name, amount, unit in RE_HTML_GRAIN_ROW.findall(text):
        kg = float(amount) if unit.lower() == "kg" else float(amount) / 1000.0
        data["fermentables"].append({"kg": kg, "name": name.strip()})

    for timing, name, grams in RE_HTML_HOP_ROW.findall(text):
        hop_name = name.strip()
        timing_norm = normalize_timing(timing.strip())
        name_norm = normalize_name(hop_name)
        if "whirlfloc" in name_norm or "corn sugar" in name_norm or timing_norm == "dry hop":
            continue
        data["hops"].append(
            {"g": float(grams), "name": hop_name, "timing": timing_norm}
        )

    section = RE_EXECUTION_SECTION.search(text)
    if section:
        for action in RE_EXECUTION_ACTION_CELL.findall(section.group(1)):
            if "+" in action:
                data["grouped_actions"].append(action.strip())

    return data


def find_sheet_for_recipe(recipe_path: Path) -> Path:
    stem = recipe_path.stem
    candidates = [normalize_token(value) for value in recipe_stem_candidates(stem)]
    matched: list[Path] = []
    for path in sorted(SHEETS_DIR.rglob("*.html"), key=lambda p: p.name, reverse=True):
        sheet_tokens = brew_sheet_match_tokens(path.stem)
        if any(
            candidate in sheet_token or sheet_token in candidate
            for candidate in candidates
            for sheet_token in sheet_tokens
        ):
            matched.append(path)
    if not matched:
        raise FileNotFoundError(f"No brew-day sheet found for recipe: {recipe_path}")
    dated = [path for path in matched if re.search(r"_\d{4}-\d{2}-\d{2}\.html$", path.name)]
    return dated[-1] if dated else matched[-1]


def find_recipe_files() -> list[Path]:
    out: list[Path] = []
    for path in RECIPES_DIR.rglob("*.md"):
        if any(part in EXCLUDED_RECIPE_PARTS for part in path.parts):
            continue
        out.append(path)
    return sorted(out)


def load_active_pairs() -> list[tuple[Path, Path]] | None:
    if not ACTIVE_ARTIFACTS_FILE.exists():
        return None
    payload = json.loads(ACTIVE_ARTIFACTS_FILE.read_text(encoding="utf-8"))
    out: list[tuple[Path, Path]] = []
    for pair in payload.get("active_pairs", []):
        recipe = ROOT / pair["recipe"]
        sheet = pair.get("brew_sheet")
        if not sheet:
            continue
        sheet_path = ROOT / sheet
        if recipe.exists() and sheet_path.exists():
            out.append((recipe, sheet_path))
    return out


def compare(recipe: dict, sheet: dict, recipe_path: Path, sheet_path: Path) -> list[str]:
    errors: list[str] = []
    if recipe["og"] != sheet["og"]:
        errors.append(f"OG mismatch: recipe {recipe['og']} vs sheet {sheet['og']}")
    if recipe["fg"] != sheet["fg"]:
        errors.append(f"FG mismatch: recipe {recipe['fg']} vs sheet {sheet['fg']}")

    recipe_ferms = recipe["fermentables"]
    sheet_ferms = sheet["fermentables"]
    if len(recipe_ferms) != len(sheet_ferms):
        errors.append(f"fermentable count mismatch: recipe {len(recipe_ferms)} vs sheet {len(sheet_ferms)}")
    for rf in recipe_ferms:
        matched = any(name_matches(rf["name"], sf["name"]) and amount_close(rf["kg"], sf["kg"]) for sf in sheet_ferms)
        if not matched:
            errors.append(f"fermentable missing/mismatched on sheet: {rf['name']} ({rf['kg']:.2f} kg)")

    recipe_hops = recipe["hops"]
    sheet_hops = sheet["hops"]
    if len(recipe_hops) != len(sheet_hops):
        errors.append(f"hop count mismatch: recipe {len(recipe_hops)} vs sheet {len(sheet_hops)}")
    for rh in recipe_hops:
        matched = any(
            name_matches(rh["name"], sh["name"])
            and amount_close(rh["g"], sh["g"], tol=0.6)
            and normalize_timing(rh["timing"]) == normalize_timing(sh["timing"])
            for sh in sheet_hops
        )
        if not matched:
            errors.append(f"hop missing/mismatched on sheet: {rh['name']} ({rh['g']:.0f} g @ {rh['timing']})")

    for action in sheet["grouped_actions"]:
        errors.append(f"grouped boil action found in sheet execution log: {action}")

    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate recipe markdown against brew-day sheet HTML")
    parser.add_argument("recipe", nargs="?", help="Recipe markdown path, absolute or repo-relative")
    parser.add_argument(
        "--sheet",
        help="Explicit brew-day sheet path. If omitted, the tool finds the latest matching sheet by slug.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all recipes that have matching brew-day sheets.",
    )
    return parser


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return ROOT / path


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.all:
        overall_ok = True
        checked = 0
        pairs = load_active_pairs()
        if pairs is None:
            pairs = []
            for recipe_path in find_recipe_files():
                try:
                    sheet_path = find_sheet_for_recipe(recipe_path)
                except FileNotFoundError:
                    if recipe_path.stem in BREWSHEET_OPTIONAL_RECIPES:
                        continue
                    overall_ok = False
                    print("RECIPE_BREWSHEET_SYNC_FAILED")
                    print(f"Recipe: {recipe_path.relative_to(ROOT)}")
                    print("- missing brew-day sheet")
                    print("")
                    continue
                pairs.append((recipe_path, sheet_path))
        for recipe_path, sheet_path in pairs:
            checked += 1
            recipe = parse_recipe(recipe_path)
            sheet = parse_sheet(sheet_path)
            errors = compare(recipe, sheet, recipe_path, sheet_path)
            if errors:
                overall_ok = False
                print("RECIPE_BREWSHEET_SYNC_FAILED")
                print(f"Recipe: {recipe_path.relative_to(ROOT)}")
                print(f"Sheet:  {sheet_path.relative_to(ROOT)}")
                for error in errors:
                    print(f"- {error}")
                print("")
        if not checked:
            print("RECIPE_BREWSHEET_SYNC_FAILED")
            print("No recipe/brew-sheet pairs found.")
            return 1
        if overall_ok:
            print(f"RECIPE_BREWSHEET_SYNC_OK ({checked} pair(s))")
            return 0
        return 1

    if not args.recipe:
        parser.error("recipe is required unless --all is used")

    recipe_path = resolve_path(args.recipe)
    sheet_path = resolve_path(args.sheet) if args.sheet else find_sheet_for_recipe(recipe_path)

    recipe = parse_recipe(recipe_path)
    sheet = parse_sheet(sheet_path)
    errors = compare(recipe, sheet, recipe_path, sheet_path)

    if errors:
        print("RECIPE_BREWSHEET_SYNC_FAILED")
        print(f"Recipe: {recipe_path.relative_to(ROOT)}")
        print(f"Sheet:  {sheet_path.relative_to(ROOT)}")
        for error in errors:
            print(f"- {error}")
        return 1

    print("RECIPE_BREWSHEET_SYNC_OK")
    print(f"Recipe: {recipe_path.relative_to(ROOT)}")
    print(f"Sheet:  {sheet_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
