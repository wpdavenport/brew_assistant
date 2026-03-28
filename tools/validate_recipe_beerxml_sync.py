#!/usr/bin/env python3
"""Validate recipe markdown against BeerXML export.

Initial scope:
- target OG / FG alignment
- fermentable line-item alignment
- hop line-item alignment
- fermentation stage presence
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECIPES_DIR = ROOT / "recipes"
EXPORTS_DIR = ROOT / "recipes" / "beer_xml_exports"
ACTIVE_ARTIFACTS_FILE = ROOT / "project_control" / "ACTIVE_ARTIFACTS.json"
EXCLUDED_RECIPE_PARTS = {"historical", "beer_xml_exports", "beer_xml_imports"}

RE_OG = re.compile(r"- OG:\s*([0-9.\-]+)")
RE_FG = re.compile(r"- FG:\s*([0-9.\-]+)")
RE_FERM_LINE = re.compile(r"^- ([0-9.]+) lb \(([0-9.]+) kg\) (.+)$")
RE_HOP_LINE = re.compile(r"^- ([0-9.]+) oz \(([0-9.]+) g\) (.+?) - (.+)$")


def normalize_name(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


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
    if t == "flameout" or t.startswith("flameout ") or t.startswith("0 min"):
        return "flameout 10 min steep"
    if t.endswith("min"):
        return t
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
            if subsection == "boil / whirlpool":
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


def parse_xml(path: Path) -> dict:
    tree = ET.parse(path)
    root = tree.getroot()
    recipe_node = root.find("RECIPE")
    if recipe_node is None:
        raise ValueError(f"No RECIPE node in {path}")

    def text(name: str) -> str | None:
        node = recipe_node.find(name)
        return node.text.strip() if node is not None and node.text else None

    data: dict[str, object] = {
        "og": text("EST_OG"),
        "fg": text("EST_FG"),
        "fermentables": [],
        "hops": [],
        "fermentation_stages": text("FERMENTATION_STAGES"),
    }

    ferments = recipe_node.find("FERMENTABLES")
    if ferments is not None:
        for node in ferments.findall("FERMENTABLE"):
            name = text_from(node, "NAME")
            amount = text_from(node, "AMOUNT")
            if name and amount:
                data["fermentables"].append({"kg": float(amount), "name": name})

    hops = recipe_node.find("HOPS")
    if hops is not None:
        for node in hops.findall("HOP"):
            name = text_from(node, "NAME")
            amount = text_from(node, "AMOUNT")
            use = text_from(node, "USE")
            time = text_from(node, "TIME")
            if name and amount and use and time:
                use_lower = use.lower()
                if use_lower == "boil":
                    timing = f"{time} min"
                elif use_lower == "aroma":
                    timing = "flameout 10 min steep"
                else:
                    timing = f"{use_lower} {time}"
                data["hops"].append(
                    {"g": float(amount) * 1000.0, "name": name, "timing": normalize_timing(timing)}
                )

    return data


def text_from(node: ET.Element, name: str) -> str | None:
    child = node.find(name)
    return child.text.strip() if child is not None and child.text else None


def find_export_for_recipe(recipe_path: Path) -> Path:
    return EXPORTS_DIR / f"{recipe_path.stem}.xml"


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
        xml_rel = pair.get("beerxml")
        if not xml_rel:
            continue
        xml_path = ROOT / xml_rel
        if recipe.exists() and xml_path.exists():
            out.append((recipe, xml_path))
    return out


def compare(recipe: dict, export: dict) -> list[str]:
    errors: list[str] = []
    if recipe["og"] != export["og"]:
        errors.append(f"OG mismatch: recipe {recipe['og']} vs xml {export['og']}")
    if recipe["fg"] != export["fg"]:
        errors.append(f"FG mismatch: recipe {recipe['fg']} vs xml {export['fg']}")
    if export["fermentation_stages"] is None:
        errors.append("BeerXML missing FERMENTATION_STAGES")

    recipe_ferms = recipe["fermentables"]
    xml_ferms = export["fermentables"]
    if len(recipe_ferms) != len(xml_ferms):
        errors.append(f"fermentable count mismatch: recipe {len(recipe_ferms)} vs xml {len(xml_ferms)}")
    for rf in recipe_ferms:
        matched = any(name_matches(rf["name"], xf["name"]) and amount_close(rf["kg"], xf["kg"]) for xf in xml_ferms)
        if not matched:
            errors.append(f"fermentable missing/mismatched in xml: {rf['name']} ({rf['kg']:.2f} kg)")

    recipe_hops = recipe["hops"]
    xml_hops = export["hops"]
    if len(recipe_hops) != len(xml_hops):
        errors.append(f"hop count mismatch: recipe {len(recipe_hops)} vs xml {len(xml_hops)}")
    for rh in recipe_hops:
        matched = any(
            name_matches(rh["name"], xh["name"])
            and amount_close(rh["g"], xh["g"], tol=0.2)
            and normalize_timing(rh["timing"]) == normalize_timing(xh["timing"])
            for xh in xml_hops
        )
        if not matched:
            errors.append(f"hop missing/mismatched in xml: {rh['name']} ({rh['g']:.0f} g @ {rh['timing']})")

    return errors


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else ROOT / path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate recipe markdown against BeerXML export")
    parser.add_argument("recipe", nargs="?", help="Recipe markdown path, absolute or repo-relative")
    parser.add_argument("--xml", help="Explicit BeerXML path. If omitted, uses recipes/beer_xml_exports/<stem>.xml")
    parser.add_argument("--all", action="store_true", help="Validate all recipes that have matching BeerXML exports.")
    return parser


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
                xml_path = find_export_for_recipe(recipe_path)
                if not xml_path.exists():
                    continue
                pairs.append((recipe_path, xml_path))
        for recipe_path, xml_path in pairs:
            checked += 1
            recipe = parse_recipe(recipe_path)
            export = parse_xml(xml_path)
            errors = compare(recipe, export)
            if errors:
                overall_ok = False
                print("RECIPE_BEERXML_SYNC_FAILED")
                print(f"Recipe: {recipe_path.relative_to(ROOT)}")
                print(f"XML:    {xml_path.relative_to(ROOT)}")
                for error in errors:
                    print(f"- {error}")
                print("")
        if not checked:
            print("RECIPE_BEERXML_SYNC_FAILED")
            print("No recipe/BeerXML pairs found.")
            return 1
        if overall_ok:
            print(f"RECIPE_BEERXML_SYNC_OK ({checked} pair(s))")
            return 0
        return 1

    if not args.recipe:
        parser.error("recipe is required unless --all is used")

    recipe_path = resolve_path(args.recipe)
    xml_path = resolve_path(args.xml) if args.xml else find_export_for_recipe(recipe_path)
    if not xml_path.exists():
        print("RECIPE_BEERXML_SYNC_FAILED")
        print(f"Missing BeerXML export: {xml_path.relative_to(ROOT)}")
        return 1

    recipe = parse_recipe(recipe_path)
    export = parse_xml(xml_path)
    errors = compare(recipe, export)

    if errors:
        print("RECIPE_BEERXML_SYNC_FAILED")
        print(f"Recipe: {recipe_path.relative_to(ROOT)}")
        print(f"XML:    {xml_path.relative_to(ROOT)}")
        for error in errors:
            print(f"- {error}")
        return 1

    print("RECIPE_BEERXML_SYNC_OK")
    print(f"Recipe: {recipe_path.relative_to(ROOT)}")
    print(f"XML:    {xml_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
