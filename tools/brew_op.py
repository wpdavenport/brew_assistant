#!/usr/bin/env python3
"""Single operator entry point for brew lifecycle actions."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def parse_phrase(text: str) -> dict[str, str]:
    raw = text.strip()
    normalized = normalize(raw)

    if normalized in {"status", "batch status", "what next", "next action", "next actions"}:
        return {"action": "status"}

    m = re.fullmatch(r"(?:prepare|prep)\s+(.+?)(?:\s+on\s+(\d{4}-\d{2}-\d{2}))?", raw, flags=re.IGNORECASE)
    if m:
        return {"action": "prepare", "recipe": m.group(1).strip(), "date": m.group(2) or ""}

    m = re.fullmatch(r"(?:i brewed|brew)\s+(.+?)(?:\s+on\s+(\d{4}-\d{2}-\d{2}))?", raw, flags=re.IGNORECASE)
    if m:
        return {"action": "brew", "recipe": m.group(1).strip(), "date": m.group(2) or ""}

    m = re.fullmatch(
        r"(?:i packaged|package)\s+(.+?)\s+brewed\s+(\d{4}-\d{2}-\d{2})\s+on\s+(\d{4}-\d{2}-\d{2})\s+at\s+([0-9.]+)\s+(gal|l)\s+fg\s+([0-9.]+)(?:\s+harvested\s+(.+?)(?:\s+gen\s+(\d+))?)?",
        raw,
        flags=re.IGNORECASE,
    )
    if m:
        return {
            "action": "package",
            "recipe": m.group(1).strip(),
            "brew_date": m.group(2),
            "package_date": m.group(3),
            "packaged_volume": m.group(4),
            "packaged_volume_unit": m.group(5).lower(),
            "fg": m.group(6),
            "harvest_yeast": (m.group(7) or "").strip(),
            "harvest_generation": m.group(8) or "",
        }

    raise ValueError(
        'Phrase not recognized. Try "prepare old crown lazy lager on 2026-04-15", '
        '"brew davenport esb on 2026-03-28", '
        'or "package davenport esb brewed 2026-03-28 on 2026-04-10 at 4.55 gal fg 1.013".'
    )


def run(cmd: list[str], dry_run: bool) -> int:
    print("command:", " ".join(cmd))
    if dry_run:
        return 0
    return subprocess.run(cmd, cwd=ROOT).returncode


def refresh_recipe_html(recipe: str, dry_run: bool) -> int:
    cmd = [sys.executable, "tools/refresh_recipe_html.py", "--recipe", recipe]
    return run(cmd, dry_run)


def action_command(args: argparse.Namespace, phrase_data: dict[str, str] | None) -> list[str]:
    if phrase_data and phrase_data.get("action") == "status":
        return [sys.executable, "tools/batch_state_summary.py", "--with-next-actions"]

    action = (phrase_data or {}).get("action") or args.action
    recipe = (phrase_data or {}).get("recipe") or args.recipe
    date = (phrase_data or {}).get("date") or args.date

    if not recipe and action != "status":
        raise ValueError("A recipe is required unless asking for status.")

    if action == "prepare":
        cmd = [sys.executable, "tools/prepare_brew.py", "--recipe", recipe]
        if date:
            cmd.extend(["--date", date])
        if args.run_trust_check:
            cmd.append("--run-trust-check")
        if args.record_history:
            cmd.append("--record-history")
        return cmd

    if action == "brew":
        cmd = [sys.executable, "tools/register_brew.py", "--recipe", recipe]
        if date:
            cmd.extend(["--date", date])
        if args.include_optional:
            cmd.append("--include-optional")
        if args.note:
            cmd.extend(["--note", args.note])
        return cmd

    if action == "package":
        brew_date = (phrase_data or {}).get("brew_date") or args.brew_date or args.date
        package_date = (phrase_data or {}).get("package_date") or args.package_date
        packaged_volume = (phrase_data or {}).get("packaged_volume") or args.packaged_volume
        packaged_unit = (phrase_data or {}).get("packaged_volume_unit") or args.packaged_volume_unit
        fg = (phrase_data or {}).get("fg") or args.fg
        harvest_yeast = (phrase_data or {}).get("harvest_yeast") or args.harvest_yeast
        harvest_generation = (phrase_data or {}).get("harvest_generation") or (
            str(args.harvest_generation) if args.harvest_generation else ""
        )
        if not brew_date or not package_date or not packaged_volume or not fg:
            raise ValueError("Package action requires brew date, package date, packaged volume, and FG.")
        cmd = [
            sys.executable,
            "tools/register_package.py",
            "--recipe",
            recipe,
            "--brew-date",
            brew_date,
            "--package-date",
            package_date,
            "--packaged-volume",
            packaged_volume,
            "--packaged-volume-unit",
            packaged_unit,
            "--fg",
            fg,
        ]
        if args.co2_vols:
            cmd.extend(["--co2-vols", args.co2_vols])
        if harvest_yeast:
            cmd.extend(["--harvest-yeast", harvest_yeast])
            if harvest_generation:
                cmd.extend(["--harvest-generation", harvest_generation])
        if args.note:
            cmd.extend(["--note", args.note])
        return cmd

    if action == "status":
        return [sys.executable, "tools/batch_state_summary.py", "--with-next-actions"]

    if action == "auto":
        cmd = [sys.executable, "tools/batch_lifecycle.py", "--recipe", recipe]
        if date:
            cmd.extend(["--date", date])
        if args.run_trust_check:
            cmd.append("--run-trust-check")
        if args.record_history:
            cmd.append("--record-history")
        if args.include_optional:
            cmd.append("--include-optional")
        if args.note:
            cmd.extend(["--note", args.note])
        if args.brew_date:
            cmd.extend(["--date", args.brew_date])
        if args.package_date:
            cmd.extend(["--package-date", args.package_date])
        if args.fg:
            cmd.extend(["--fg", args.fg])
        if args.packaged_volume:
            cmd.extend(["--packaged-volume", args.packaged_volume])
            cmd.extend(["--packaged-volume-unit", args.packaged_volume_unit])
        if args.co2_vols:
            cmd.extend(["--co2-vols", args.co2_vols])
        if args.harvest_yeast:
            cmd.extend(["--harvest-yeast", args.harvest_yeast])
        if args.harvest_generation:
            cmd.extend(["--harvest-generation", str(args.harvest_generation)])
        return cmd

    raise ValueError(f"Unsupported action: {action}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Single operator entry point for brew lifecycle actions")
    parser.add_argument("--text", default="", help="Natural-language action phrase")
    parser.add_argument("--action", default="auto", choices=["auto", "prepare", "brew", "package", "status"], help="Explicit action")
    parser.add_argument("--recipe", default="", help="Recipe path, file stem, or slug token")
    parser.add_argument("--date", default="", help="Shared date hint, usually brew date")
    parser.add_argument("--brew-date", default="", help="Explicit brew date for package actions")
    parser.add_argument("--package-date", default="", help="Package date")
    parser.add_argument("--fg", default="", help="FG for package action")
    parser.add_argument("--packaged-volume", default="", help="Packaged volume for package action")
    parser.add_argument("--packaged-volume-unit", default="gal", help="Packaged volume unit")
    parser.add_argument("--co2-vols", default="", help="Optional carbonation level")
    parser.add_argument("--harvest-yeast", default="", help="Optional harvested yeast token")
    parser.add_argument("--harvest-generation", type=int, default=0, help="Optional harvested yeast generation")
    parser.add_argument("--include-optional", action="store_true", help="Include optional recipe items for brew registration")
    parser.add_argument("--record-history", action="store_true", help="Record prepare event in brew history")
    parser.add_argument("--run-trust-check", action="store_true", help="Run trust-check during prepare flow")
    parser.add_argument("--refresh-html", action="store_true", default=True, help="Refresh recipe HTML before acting")
    parser.add_argument("--no-refresh-html", action="store_false", dest="refresh_html", help="Disable automatic recipe HTML refresh")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without mutating state")
    parser.add_argument("--note", default="", help="Optional note")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    phrase_data = parse_phrase(args.text) if args.text else None
    recipe = (phrase_data or {}).get("recipe") or args.recipe
    if args.refresh_html and recipe:
        rc = refresh_recipe_html(recipe, args.dry_run)
        if rc != 0:
            return rc
    cmd = action_command(args, phrase_data)
    return run(cmd, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
