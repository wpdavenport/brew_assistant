#!/usr/bin/env python3
"""Validate recipe markdown against generated recipe HTML exports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from render_recipe_html import HTML_EXPORT_DIR, render_recipe, renderable_recipes


ROOT = Path(__file__).resolve().parents[1]


def expected_html_path(recipe_path: Path) -> Path:
    return HTML_EXPORT_DIR / f"{recipe_path.stem}.html"


def compare_recipe(recipe_path: Path, html_path: Path) -> list[str]:
    errors: list[str] = []
    if not html_path.exists():
        errors.append(f"Missing recipe HTML export: {html_path.relative_to(ROOT)}")
        return errors
    expected = render_recipe(recipe_path)
    actual = html_path.read_text(encoding="utf-8")
    if expected != actual:
        errors.append(
            f"Recipe HTML drift: regenerate {html_path.relative_to(ROOT)} from {recipe_path.relative_to(ROOT)}"
        )
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate recipe markdown against generated HTML exports")
    parser.add_argument("--recipe", help="Specific recipe markdown path or slug")
    parser.add_argument("--all", action="store_true", help="Validate all renderable recipes")
    return parser


def resolve_single(recipe_arg: str) -> Path:
    from render_recipe_html import resolve_recipe

    return resolve_recipe(recipe_arg)


def main() -> int:
    args = build_parser().parse_args()
    if not args.all and not args.recipe:
        print("Pass --recipe <slug> or --all", file=sys.stderr)
        return 2

    recipes = renderable_recipes() if args.all else [resolve_single(args.recipe)]
    if not recipes:
        print("No recipe/html pairs found.")
        return 0

    failures = 0
    checked = 0
    for recipe_path in recipes:
        html_path = expected_html_path(recipe_path)
        errors = compare_recipe(recipe_path, html_path)
        checked += 1
        if errors:
            failures += 1
            print(f"[FAIL] {recipe_path.relative_to(ROOT)}")
            for error in errors:
                print(f"  - {error}")

    if failures:
        print(f"RECIPE_HTML_SYNC_FAILED ({failures}/{checked} recipe(s) mismatched)")
        return 1

    print(f"RECIPE_HTML_SYNC_OK ({checked} recipe(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
