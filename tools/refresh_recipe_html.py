#!/usr/bin/env python3
"""Refresh recipe HTML exports from source markdown.

Supports:
- all renderable recipes
- a specific recipe
- only changed recipes based on git status
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from render_recipe_html import ROOT, RECIPES_DIR, render_one, renderable_recipes, resolve_recipe


TEMPLATE_FILE = ROOT / "libraries" / "templates" / "recipe_print_template.html"
RENDER_SCRIPT = ROOT / "tools" / "render_recipe_html.py"


def changed_paths() -> list[Path]:
    proc = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    out: list[Path] = []
    for raw in proc.stdout.splitlines():
        if not raw.strip():
            continue
        path_text = raw[3:].strip()
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        out.append((ROOT / path_text).resolve())
    return out


def changed_recipe_paths() -> list[Path]:
    paths = changed_paths()
    if any(path == TEMPLATE_FILE.resolve() or path == RENDER_SCRIPT.resolve() for path in paths):
        return renderable_recipes()
    out: list[Path] = []
    for path in paths:
        if path.suffix != ".md":
            continue
        try:
            rel = path.relative_to(RECIPES_DIR.resolve())
        except ValueError:
            continue
        if "historical" in rel.parts or "locked" in rel.parts or "in_development" in rel.parts:
            continue
        out.append(path)
    unique: list[Path] = []
    seen = set()
    for path in out:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Refresh recipe HTML exports")
    parser.add_argument("--recipe", default="", help="Specific recipe markdown path or slug")
    parser.add_argument("--all", action="store_true", help="Refresh all renderable recipes")
    parser.add_argument("--changed", action="store_true", help="Refresh only changed renderable recipes")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if sum(bool(x) for x in [args.recipe, args.all, args.changed]) != 1:
        print("Pass exactly one of --recipe, --all, or --changed", file=sys.stderr)
        return 2

    if args.recipe:
        recipes = [resolve_recipe(args.recipe)]
    elif args.all:
        recipes = renderable_recipes()
    else:
        recipes = changed_recipe_paths()

    if not recipes:
        print("RECIPE_HTML_REFRESH_NOOP")
        return 0

    for recipe_path in recipes:
        output_path = render_one(recipe_path, "")
        print(f"RECIPE_HTML_REFRESH_OK {output_path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
