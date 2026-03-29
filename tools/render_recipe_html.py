#!/usr/bin/env python3
"""Render recipe markdown into a compact printable recipe sheet."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECIPES_DIR = ROOT / "recipes"
HTML_EXPORT_DIR = RECIPES_DIR / "html_exports"
TEMPLATE_FILE = ROOT / "libraries" / "templates" / "recipe_print_template.html"
EQUIPMENT_FILE = ROOT / "profiles" / "equipment.yaml"


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
    competition = find_section(sections, "COMPETITION ENTRY")
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
            if any(keyword in lowered for keyword in ["hold", "raise", "crash", "lager", "ramp", "chill"]):
                steps.append(item)
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


def as_list(items: list[str], ordered: bool = False) -> str:
    tag = "ol" if ordered else "ul"
    rendered = "\n".join(f"<li>{html.escape(item)}</li>" for item in items)
    return f"<{tag}>\n{rendered}\n</{tag}>"


def targets_inline(items: list[str]) -> str:
    chunks = []
    for item in items:
        if ":" in item:
            left, right = item.split(":", 1)
            chunks.append(f"<span><strong>{html.escape(left.strip())}:</strong> {html.escape(right.strip())}</span>")
        else:
            chunks.append(f"<span>{html.escape(item)}</span>")
    return "\n".join(chunks)


def render_recipe(recipe_path: Path) -> str:
    title, sections = parse_markdown_sections(recipe_path.read_text(encoding="utf-8"))
    display_title = print_title(title, sections)
    targets = target_parameters(find_section(sections, "TARGET PARAMETERS"))
    grains = top_bullets(find_section(sections, "FERMENTABLES"))
    hop_lines = subsection_bullets(find_section(sections, "HOPS"), {"Boil / Whirlpool", "Kettle Additions"})
    yeasts = filter_yeast_lines(find_section(sections, "YEAST"))
    mash = mash_schedule(find_section(sections, "MASH SCHEDULE") or find_section(sections, "MASH PROGRAM"), find_section(sections, "BREW DAY PROCESS"))
    fermentation = fermentation_schedule(find_section(sections, "FERMENTATION SCHEDULE"))
    ferment_equipment = read_fermentation_equipment()

    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    replacements = {
        "{{TITLE}}": html.escape(display_title),
        "{{TARGETS}}": targets_inline(targets),
        "{{GRAINS}}": as_list(grains),
        "{{HOPS}}": as_list(hop_lines),
        "{{YEAST}}": as_list(yeasts),
        "{{MASH}}": as_list(mash, ordered=True),
        "{{FERMENT_EQUIPMENT}}": html.escape(ferment_equipment),
        "{{FERMENTATION}}": as_list(fermentation, ordered=True),
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
