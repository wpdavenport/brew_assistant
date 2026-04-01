#!/usr/bin/env python3
"""Summarize sensory-driven iteration learning from recipe files and their archives."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECIPES_DIR = ROOT / "recipes"
HISTORICAL_DIR = ROOT / "recipes" / "historical"


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


def extract_learning_from_lines(lines: list[str]) -> dict[str, list[str]]:
    strengths: list[str] = []
    misses: list[str] = []
    implications: list[str] = []
    scoring: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if re.fullmatch(r"-?\s*[A-Za-z /-]+:\s*", line):
            continue
        low = line.lower()
        if any(key in low for key in ("overall impression:", "overall:", "mouthfeel: close match", "mouthfeel: spot on", "carbonation: perfect")):
            strengths.append(line.lstrip("- ").strip())
        elif any(key in low for key in ("aroma:", "appearance:", "flavor:", "mouthfeel:")):
            strengths.append(line.lstrip("- ").strip())
        if any(key in low for key in ("clone miss:", "miss:", "too dark", "harsher", "lingering bitterness", "slightly intrusive", "lacked")):
            misses.append(line.lstrip("- ").strip())
        if any(key in low for key in ("iteration implication:", "adjustment plan", "ranked next-batch changes", "next-batch changes", "reduce ", "remove ", "rebalance ", "keep unchanged", "keep unchanged:")):
            implications.append(line.lstrip("- ").strip())
        if any(key in low for key in ("score", "/ 50", "38 / 50", "self-score")):
            scoring.append(line.lstrip("- ").strip())
    return {
        "strengths": strengths,
        "misses": misses,
        "implications": implications,
        "scoring": scoring,
    }


def collect_sources(recipe_path: Path) -> list[Path]:
    sources = [recipe_path]
    stem_candidates = {normalize_token(value) for value in recipe_stem_candidates(recipe_path.stem)}
    for path in sorted(HISTORICAL_DIR.glob("*.md")):
        if any(candidate in normalize_token(path.stem) for candidate in stem_candidates):
            sources.append(path.resolve())
    return sources


def build_learning(recipe_path: Path) -> dict:
    combined = {"strengths": [], "misses": [], "implications": [], "scoring": []}
    sources_out: list[dict] = []
    for source in collect_sources(recipe_path):
        title, sections = parse_markdown_sections(source.read_text(encoding="utf-8"))
        source_rows: list[str] = []
        for section_name, lines in sections.items():
            if any(key in section_name.lower() for key in ("sensory", "side-by-side", "scoring", "calibration", "adjustment plan", "next-batch changes")):
                source_rows.extend(lines)
        extracted = extract_learning_from_lines(source_rows)
        if any(extracted.values()):
            sources_out.append(
                {
                    "path": source.relative_to(ROOT).as_posix(),
                    "title": title,
                    **extracted,
                }
            )
            for key in combined:
                combined[key].extend(extracted[key])
    return {
        "title": parse_markdown_sections(recipe_path.read_text(encoding="utf-8"))[0],
        "recipe": recipe_path.relative_to(ROOT).as_posix(),
        "sources": sources_out,
        **combined,
    }


def render_text(payload: dict) -> str:
    lines = [
        "SENSORY LEARNING",
        "=" * 80,
        payload["title"],
        payload["recipe"],
    ]
    for heading, key in (
        ("Strengths", "strengths"),
        ("Misses", "misses"),
        ("Iteration Implications", "implications"),
        ("Scoring Notes", "scoring"),
    ):
        lines.extend(["", heading, "-" * 80])
        values = payload.get(key, [])
        if values:
            lines.extend(f"- {value}" for value in values)
        else:
            lines.append("(none)")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize sensory-driven iteration learning for a recipe")
    parser.add_argument("--recipe", required=True, help="Recipe path, file stem, or slug token")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    recipe_path = resolve_recipe(args.recipe)
    payload = build_learning(recipe_path)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
