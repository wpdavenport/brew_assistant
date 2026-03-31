#!/usr/bin/env python3
"""Render recipe markdown into a compact printable recipe sheet."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECIPES_DIR = ROOT / "recipes"
HTML_EXPORT_DIR = RECIPES_DIR / "html_exports"
TEMPLATE_FILE = ROOT / "libraries" / "templates" / "recipe_print_template.html"
EQUIPMENT_FILE = ROOT / "profiles" / "equipment.yaml"
BREW_HISTORY_FILE = ROOT / "libraries" / "inventory" / "brew_history.json"


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


def parse_markdown_sections(markdown_text: str) -> tuple[str, dict[str, list[str]]]:
    title = "Recipe"
    current = ""
    sections: dict[str, list[str]] = {}
    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("# "):
            title = line[2:].strip()
            current = ""
            continue
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return title, sections


def print_title(source_title: str, sections: dict[str, list[str]]) -> str:
    short_title = re.sub(r"\s*\(.*\)\s*$", "", source_title).strip()
    competition = (
        find_section(sections, "COMPETITION ENTRY")
        or find_section(sections, "COMPETITION TRACKING")
        or find_section(sections, "INTENT")
    )
    category = ""
    for raw in competition:
        stripped = raw.strip()
        if stripped.startswith("- ") and "BJCP Category:" in stripped:
            category = stripped.split("BJCP Category:", 1)[1].strip()
            break
    if category:
        return f"{short_title} - BJCP {category}"
    return short_title


def find_section(sections: dict[str, list[str]], prefix: str) -> list[str]:
    for key, value in sections.items():
        if key.upper().startswith(prefix.upper()):
            return value
    return []


def top_bullets(lines: list[str]) -> list[str]:
    bullets: list[str] = []
    seen_bullets = False
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            if seen_bullets:
                break
            continue
        if stripped.startswith("- "):
            seen_bullets = True
            bullets.append(stripped[2:].strip())
            continue
        if seen_bullets:
            break
    return bullets


def subsection_bullets(lines: list[str], allowed_titles: set[str]) -> list[str]:
    current = ""
    bullets: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("### "):
            current = stripped[4:].strip()
            continue
        if stripped.startswith("- ") and current in allowed_titles:
            bullets.append(stripped[2:].strip())
    return bullets


def subsection_items(lines: list[str], target_title: str) -> list[str]:
    current = ""
    items: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("### "):
            current = stripped[4:].strip()
            continue
        if stripped.startswith("- ") and current.lower() == target_title.lower():
            items.append(stripped[2:].strip())
    return items


def section_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def matching_items(lines: list[str], keywords: tuple[str, ...]) -> list[str]:
    items: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped.startswith("- "):
            continue
        item = stripped[2:].strip()
        lowered = item.lower()
        if any(keyword in lowered for keyword in keywords):
            items.append(item)
    return items


def process_schedule_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped.startswith("- "):
            continue
        item = stripped[2:].strip()
        lowered = item.lower()
        if (
            lowered.startswith("mash")
            or lowered.startswith("alpha rest")
            or lowered.startswith("rest")
            or lowered.startswith("total mash")
            or lowered.startswith("boil")
        ):
            items.append(item)
    return items


def filter_yeast_lines(lines: list[str]) -> list[str]:
    keep: list[str] = []
    disallowed_prefixes = (
        "target pitch",
        "pitch target",
        "track generation",
        "record repitch",
        "preferred plan",
        "if slurry age",
        "optional ",
        "direct pitch target",
        "vitality starter",
        "primary bos path",
        "fallback",
    )
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            lowered = item.lower()
            if lowered.startswith(disallowed_prefixes):
                continue
            keep.append(item)
    return keep[:3]


def mash_schedule(lines: list[str], fallback_lines: list[str]) -> list[str]:
    steps: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if re.match(r"^\d+\.\s+", stripped):
            item = re.sub(r"^\d+\.\s+", "", stripped)
            lowered = item.lower()
            if re.search(r"\b(mash out|mash|rest)\b", lowered) and re.search(r"\d", item):
                steps.append(item)
    if steps:
        return steps
    for raw in fallback_lines:
        stripped = raw.strip()
        if re.match(r"^\d+\.\s+", stripped):
            item = re.sub(r"^\d+\.\s+", "", stripped)
            lowered = item.lower()
            if (
                re.match(r"^(mash|mash out|rest)\b", lowered)
                and re.search(r"\d", item)
            ):
                steps.append(item)
    return steps


def fermentation_schedule(lines: list[str]) -> list[str]:
    steps: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if re.match(r"^\d+\.\s+", stripped):
            item = re.sub(r"^\d+\.\s+", "", stripped)
            lowered = item.lower()
            if "rouse" in lowered:
                continue
            if any(keyword in lowered for keyword in ["hold", "raise", "crash", "lager", "ramp", "chill", "pitch", "rise", "condition", "add"]):
                steps.append(item)
    return steps


def historical_numbered_steps(lines: list[str]) -> list[str]:
    steps: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if re.match(r"^\d+\.\s+", stripped):
            steps.append(re.sub(r"^\d+\.\s+", "", stripped))
    return steps


def target_parameters(lines: list[str]) -> list[str]:
    return [line.strip()[2:].strip() for line in lines if line.strip().startswith("- ")]


def read_fermentation_equipment() -> str:
    text = EQUIPMENT_FILE.read_text(encoding="utf-8")
    fermenter = re.search(r'^\s*fermenter:\s*"([^"]+)"', text, flags=re.MULTILINE)
    glycol = re.search(r'^\s*glycol_chiller:\s*"([^"]+)"', text, flags=re.MULTILINE)
    parts = []
    if fermenter:
        parts.append(fermenter.group(1))
    if glycol:
        parts.append(glycol.group(1))
    return "Fermentation Equipment: " + " + ".join(parts) if parts else "Fermentation Equipment: repo profile"


def brew_history_items(recipe_path: Path) -> list[str]:
    payload = json.loads(BREW_HISTORY_FILE.read_text(encoding="utf-8"))
    candidate_ids = {normalize_token(value) for value in recipe_stem_candidates(recipe_path.stem)}
    brews: dict[str, dict] = {}
    packages: dict[str, dict] = {}
    for event in payload.get("events", []):
        recipe_id = normalize_token(event.get("recipe_id", ""))
        recipe_name = normalize_token(event.get("recipe_name", ""))
        if recipe_id not in candidate_ids and recipe_name not in candidate_ids:
            continue
        brew_date = event.get("brew_date", "")
        if event.get("type") == "brew" and brew_date:
            brews[brew_date] = event
        elif event.get("type") == "package" and brew_date:
            packages[brew_date] = event
    rows: list[str] = []
    for brew_date in sorted(brews.keys(), reverse=True):
        package = packages.get(brew_date)
        if package:
            packaged_volume = package.get("packaged_volume")
            packaged_unit = package.get("packaged_volume_unit", "gal")
            package_date = package.get("package_date", "")
            fg = package.get("fg")
            detail = []
            if package_date:
                detail.append(f"packaged {package_date}")
            if packaged_volume not in {None, ""}:
                detail.append(f"{float(packaged_volume):.2f} {packaged_unit}")
            if fg not in {None, ""}:
                detail.append(f"FG {float(fg):.3f}")
            suffix = " | " + " | ".join(detail) if detail else ""
            rows.append(f"Brewed {brew_date}{suffix}")
        else:
            rows.append(f"Brewed {brew_date} | packaging not recorded")
    return rows[:5]


def brew_history_section(recipe_path: Path) -> str:
    items = brew_history_items(recipe_path)
    if not items:
        return ""
    return (
        '<div class="section full">\n'
        "  <h2>Brew History</h2>\n"
        f"  {as_list(items)}\n"
        "</div>"
    )


def as_list(items: list[str], ordered: bool = False) -> str:
    tag = "ol" if ordered else "ul"
    rendered = "\n".join(f"<li>{html.escape(item)}</li>" for item in items)
    return f"<{tag}>\n{rendered}\n</{tag}>"


def normalize_sub_kilogram_metric(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        value = float(match.group(1))
        if value >= 1.0:
            return match.group(0)
        grams = int(round(value * 1000))
        return f"({grams} g)"

    return re.sub(r"\(([0-9]+(?:\.[0-9]+)?)\s*kg\)", repl, text)


def targets_inline(items: list[str]) -> str:
    chunks = []
    for item in items:
        if ":" in item:
            left, right = item.split(":", 1)
            chunks.append(f"<span><strong>{html.escape(left.strip())}:</strong> {html.escape(right.strip())}</span>")
        else:
            chunks.append(f"<span>{html.escape(item)}</span>")
    return "\n".join(chunks)


def title_font_size(title: str) -> str:
    length = len(title)
    if length <= 40:
        return "23pt"
    if length <= 50:
        return "21pt"
    if length <= 60:
        return "19pt"
    if length <= 72:
        return "17pt"
    return "15pt"


def render_recipe(recipe_path: Path) -> str:
    title, sections = parse_markdown_sections(recipe_path.read_text(encoding="utf-8"))
    display_title = print_title(title, sections)
    title_size = title_font_size(display_title)
    targets = target_parameters(find_section(sections, "TARGET PARAMETERS")) or target_parameters(find_section(sections, "PROJECTED PARAMETERS")) or target_parameters(find_section(sections, "HISTORICAL BREW SETTINGS"))
    supplied = find_section(sections, "RECIPE AS SUPPLIED")
    grains = top_bullets(find_section(sections, "FERMENTABLES")) or subsection_items(supplied, "Fermentables")
    hop_lines = (
        subsection_bullets(find_section(sections, "HOPS"), {"Boil / Whirlpool", "Kettle Additions"})
        or section_items(find_section(sections, "HOPS"))
        or subsection_items(supplied, "Hops")
    )
    yeasts = filter_yeast_lines(find_section(sections, "YEAST"))
    if not yeasts:
        historical_yeast = subsection_items(supplied, "Yeast")
        yeasts = historical_yeast[:3]
    mash = mash_schedule(
        find_section(sections, "MASH SCHEDULE") or find_section(sections, "MASH PROGRAM"),
        find_section(sections, "BREW DAY PROCESS"),
    )
    if not mash:
        mash = (
            process_schedule_items(find_section(sections, "HISTORICAL MASH AND BOIL"))
            or process_schedule_items(find_section(sections, "MASH AND BOIL"))
            or process_schedule_items(find_section(sections, "HISTORICAL BREW SETTINGS"))
        )
    fermentation = fermentation_schedule(find_section(sections, "FERMENTATION SCHEDULE"))
    if not fermentation:
        fermentation = (
            historical_numbered_steps(find_section(sections, "HISTORICAL FERMENTATION SCHEDULE"))
            or subsection_items(supplied, "Fermentation")
        )
    if not grains:
        grains = ["No explicit grain bill captured in source."]
    if not yeasts:
        yeasts = ["No explicit yeast entry captured in source."]
    if not hop_lines:
        hop_lines = ["No explicit hop schedule captured in source."]
    if not mash:
        mash = ["No explicit mash schedule captured in source."]
    if not fermentation:
        fermentation = ["No explicit fermentation schedule captured in source."]
    grains = [normalize_sub_kilogram_metric(item) for item in grains]
    hop_lines = [normalize_sub_kilogram_metric(item) for item in hop_lines]
    yeasts = [normalize_sub_kilogram_metric(item) for item in yeasts]
    mash = [normalize_sub_kilogram_metric(item) for item in mash]
    fermentation = [normalize_sub_kilogram_metric(item) for item in fermentation]
    ferment_equipment = read_fermentation_equipment()

    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    replacements = {
        "{{TITLE}}": html.escape(display_title),
        "{{TITLE_FONT_SIZE}}": title_size,
        "{{TARGETS}}": targets_inline(targets),
        "{{GRAINS}}": as_list(grains),
        "{{HOPS}}": as_list(hop_lines),
        "{{YEAST}}": as_list(yeasts),
        "{{MASH}}": as_list(mash, ordered=True),
        "{{FERMENT_EQUIPMENT}}": html.escape(ferment_equipment),
        "{{FERMENTATION}}": as_list(fermentation, ordered=True),
        "{{BREW_HISTORY_SECTION}}": brew_history_section(recipe_path),
        "{{SOURCE}}": html.escape(recipe_path.relative_to(ROOT).as_posix()),
    }
    document = template
    for needle, value in replacements.items():
        document = document.replace(needle, value)
    return document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render recipe markdown to printable HTML")
    parser.add_argument("--recipe", help="Recipe path, file stem, or slug token")
    parser.add_argument("--all", action="store_true", help="Render all non-historical, non-locked, non-in-development recipe markdown files")
    parser.add_argument("--output", default="", help="Optional explicit output path")
    return parser


def render_one(recipe_path: Path, output_arg: str) -> Path:
    HTML_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = Path(output_arg).resolve() if output_arg else (HTML_EXPORT_DIR / f"{recipe_path.stem}.html")
    if not output_path.is_absolute():
        output_path = (ROOT / output_path).resolve()
    output_path.write_text(render_recipe(recipe_path), encoding="utf-8")
    return output_path


def renderable_recipes() -> list[Path]:
    return sorted(
        path.resolve()
        for path in RECIPES_DIR.rglob("*.md")
        if "historical" not in path.parts and "locked" not in path.parts and "in_development" not in path.parts
    )


def main() -> int:
    args = build_parser().parse_args()
    if args.all:
        if args.output:
            raise ValueError("--output cannot be used with --all")
        for recipe_path in renderable_recipes():
            output_path = render_one(recipe_path, "")
            print(f"RECIPE_HTML_OK {output_path.relative_to(ROOT).as_posix()}")
        return 0
    if not args.recipe:
        raise ValueError("Pass --recipe <slug> or use --all")
    recipe_path = resolve_recipe(args.recipe)
    output_path = render_one(recipe_path, args.output)
    print(f"RECIPE_HTML_OK {output_path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
