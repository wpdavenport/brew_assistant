#!/usr/bin/env python3
"""Assess whether a brewed beer is ready to package."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECIPES_DIR = ROOT / "recipes"


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


def find_section(sections: dict[str, list[str]], prefix: str) -> list[str]:
    for key, value in sections.items():
        if key.upper().startswith(prefix.upper()):
            return value
    return []


def parse_target_fg(recipe_text: str) -> float | None:
    match = re.search(r"- FG:\s*([0-9.]+(?:-[0-9.]+)?)", recipe_text)
    if not match:
        return None
    token = match.group(1)
    if "-" in token:
        start, end = token.split("-", 1)
        return float(end)
    return float(token)


def packaging_gate_lines(sections: dict[str, list[str]]) -> list[str]:
    lines: list[str] = []
    for prefix in ("PACKAGING", "FERMENTATION SCHEDULE"):
        for raw in find_section(sections, prefix):
            stripped = raw.strip()
            low = stripped.lower()
            if any(key in low for key in ("package", "packaging", "stable", "vdk", "crash", "terminal gravity")):
                lines.append(stripped)
    return lines


def assess(
    recipe_path: Path,
    current_fg: float | None,
    stable_48h: bool,
    vdk_clean: bool,
    still_bubbling: bool,
) -> dict:
    text = recipe_path.read_text(encoding="utf-8")
    title, sections = parse_markdown_sections(text)
    target_fg = parse_target_fg(text)
    gates = packaging_gate_lines(sections)

    blockers: list[str] = []
    cautions: list[str] = []
    confirmations: list[str] = []

    if current_fg is None:
        blockers.append("Current FG not provided.")
    else:
        confirmations.append(f"Current FG: {current_fg:.3f}")
        if target_fg is not None:
            confirmations.append(f"Recipe target FG: {target_fg:.3f}")
            if current_fg > target_fg + 0.003:
                blockers.append(f"Current FG {current_fg:.3f} is still materially above target {target_fg:.3f}.")
            elif current_fg > target_fg + 0.001:
                cautions.append(f"Current FG {current_fg:.3f} is slightly above target {target_fg:.3f}; confirm stability before packaging.")

    if stable_48h:
        confirmations.append("Gravity has been stable for 48 hours.")
    else:
        blockers.append("Gravity has not been confirmed stable for 48 hours.")

    if vdk_clean:
        confirmations.append("VDK check is clean.")
    else:
        blockers.append("VDK cleanup has not been confirmed clean.")

    if still_bubbling:
        cautions.append("Beer is still visibly bubbling. That alone is not disqualifying, but it raises the bar for a clean stable-FG check.")

    if blockers:
        status = "blocked"
        next_step = "Wait, keep the beer on yeast, and verify stable gravity plus clean VDK before packaging."
    elif cautions:
        status = "caution"
        next_step = "You are close. Reconfirm gravity stability and sample quality before packaging."
    else:
        status = "ready"
        next_step = "Packaging gate passed. Proceed with closed transfer when convenient."

    return {
        "title": title,
        "recipe": recipe_path.relative_to(ROOT).as_posix(),
        "target_fg": target_fg,
        "status": status,
        "next_step": next_step,
        "confirmations": confirmations,
        "cautions": cautions,
        "blockers": blockers,
        "packaging_gates": gates,
    }


def render_text(payload: dict) -> str:
    lines = [
        "PACKAGE READINESS",
        "=" * 80,
        payload["title"],
        payload["recipe"],
        "",
        f"Status: {payload['status']}",
        f"Next: {payload['next_step']}",
    ]
    for heading, key in (
        ("Confirmations", "confirmations"),
        ("Cautions", "cautions"),
        ("Blockers", "blockers"),
        ("Recipe Packaging Gates", "packaging_gates"),
    ):
        lines.extend(["", heading, "-" * 80])
        values = payload.get(key, [])
        if values:
            lines.extend(f"- {value}" for value in values)
        else:
            lines.append("(none)")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Assess package readiness for a brewed batch")
    parser.add_argument("--recipe", required=True, help="Recipe path, file stem, or slug token")
    parser.add_argument("--current-fg", type=float, default=None, help="Observed current FG")
    parser.add_argument("--stable-48h", action="store_true", help="Gravity has been stable for 48 hours")
    parser.add_argument("--vdk-clean", action="store_true", help="Warm sample / VDK check is clean")
    parser.add_argument("--still-bubbling", action="store_true", help="Still visibly bubbling or pushing gas")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    recipe_path = resolve_recipe(args.recipe)
    payload = assess(recipe_path, args.current_fg, args.stable_48h, args.vdk_clean, args.still_bubbling)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(render_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
