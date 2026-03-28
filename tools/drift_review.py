#!/usr/bin/env python3
"""Executable drift review for the brewing assistant repo.

This tool is the first step from static control docs toward a change-aware repo
assistant. It maps changed files to drift-sensitive areas and prints the checks
that should run before the work is trusted.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IGNORED_CHANGED_FILES = {"brew.log"}


@dataclass(frozen=True)
class DriftArea:
    name: str
    patterns: tuple[str, ...]
    proposed_status: str
    required_checks: tuple[str, ...]
    note: str


AREAS: tuple[DriftArea, ...] = (
    DriftArea(
        name="Onboarding and session boot",
        patterns=("README.md", "system_prompt.md", "knowledge_index.md"),
        proposed_status="Watch",
        required_checks=(
            "verify README startup path still matches prompt/index contract",
        ),
        note="Fresh-chat reliability depends on README boot instructions matching the repo contract.",
    ),
    DriftArea(
        name="Core brewing context",
        patterns=(
            "profiles/equipment.yaml",
            "profiles/water_profiles.md",
            "libraries/yeast_library.md",
        ),
        proposed_status="Watch",
        required_checks=(
            "confirm core context files still exist and match prompt/index references",
        ),
        note="Core profile changes can silently invalidate repo-specific advice.",
    ),
    DriftArea(
        name="Knowledge retrieval map",
        patterns=("knowledge_index.md",),
        proposed_status="Watch",
        required_checks=(
            "verify every referenced path still exists",
        ),
        note="Retrieval map changes affect file selection and output locations.",
    ),
    DriftArea(
        name="Prompt contract",
        patterns=("system_prompt.md",),
        proposed_status="Watch",
        required_checks=(
            "python3 tools/prompt_harness.py eval-all",
        ),
        note="Prompt edits must be regression-checked, not trusted by inspection alone.",
    ),
    DriftArea(
        name="Repo control workflow",
        patterns=(
            "project_control/DRIFT_MATRIX.md",
            "project_control/REVIEW_RULES.md",
            "project_control/CHANGE_AWARE_PLAN.md",
            "tools/drift_review.py",
            "tools/prompt_harness.py",
            "tools/validate_hop_aa_sync.py",
            "Makefile",
        ),
        proposed_status="Watch",
        required_checks=(
            "python3 tools/drift_review.py",
        ),
        note="Control-plane changes should not leave trust workflow files unmapped.",
    ),
    DriftArea(
        name="Hop AA sync",
        patterns=(
            "libraries/inventory/stock.json",
            "recipes/",
            "brewing/brew_day_sheets/",
            "recipes/beer_xml_exports/",
        ),
        proposed_status="Guarded",
        required_checks=(
            "python3 tools/validate_hop_aa_sync.py",
        ),
        note="Any recipe, brew-sheet, export, or stock change can create AA drift.",
    ),
    DriftArea(
        name="Inventory truth",
        patterns=(
            "libraries/inventory/stock.json",
            "libraries/inventory/recipe_usage.json",
            "libraries/inventory/brew_history.json",
            "libraries/inventory/style_option_templates.json",
            "tools/inventory_cli.py",
        ),
        proposed_status="Watch",
        required_checks=(
            "confirm inventory schema still matches CLI expectations",
        ),
        note="Inventory changes affect shopping, feasibility, and brew registration logic.",
    ),
    DriftArea(
        name="Recipe lifecycle",
        patterns=(
            "recipes/in_development/",
            "recipes/locked/",
            "recipes/",
        ),
        proposed_status="Watch",
        required_checks=(
            "confirm the intended canonical recipe is still obvious",
        ),
        note="Recipe edits should not silently break which artifact is authoritative.",
    ),
    DriftArea(
        name="Brew-day execution artifacts",
        patterns=(
            "brewing/brew_day_sheets/",
            "libraries/yeast_library.md",
            "profiles/equipment.yaml",
            "libraries/inventory/stock.json",
            "recipes/",
        ),
        proposed_status="Watch",
        required_checks=(
            "confirm yeast source, generation, starter method, and dated schedule are explicit",
        ),
        note="Brew sheets are operational artifacts and should be trusted only when inventory-backed.",
    ),
    DriftArea(
        name="BJCP study isolation",
        patterns=("libraries/bjcp_study/",),
        proposed_status="Watch",
        required_checks=(
            "verify BJCP mode remains explicit opt-in",
        ),
        note="Study-mode files should not leak into normal brewing behavior.",
    ),
)


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def get_changed_files() -> list[str]:
    cmd = ["git", "status", "--short"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)
    changed: list[str] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        payload = line[3:]
        if " -> " in payload:
            _src, dst = payload.split(" -> ", 1)
            candidate = dst.strip()
        else:
            candidate = payload.strip()
        if candidate.endswith("/"):
            continue
        if candidate in IGNORED_CHANGED_FILES:
            continue
        changed.append(candidate)
    return changed


def matches(path: str, pattern: str) -> bool:
    return path == pattern or path.startswith(pattern)


def affected_areas(changed_files: list[str]) -> list[tuple[DriftArea, list[str]]]:
    matched: list[tuple[DriftArea, list[str]]] = []
    for area in AREAS:
        hits = [
            path
            for path in changed_files
            if any(matches(path, pattern) for pattern in area.patterns)
        ]
        if hits:
            matched.append((area, sorted(set(hits))))
    return matched


def render_report(changed_files: list[str], passed_checks: set[str]) -> str:
    lines: list[str] = []
    lines.append("DRIFT REVIEW")
    lines.append("")

    if not changed_files:
        lines.append("Changed files: none")
        lines.append("")
        lines.append("No affected drift rows.")
        return "\n".join(lines)

    lines.append("Changed files:")
    for path in changed_files:
        lines.append(f"- {path}")
    lines.append("")

    affected = affected_areas(changed_files)
    if not affected:
        lines.append("Affected rows: none mapped")
        lines.append("Missing control: add a drift row or extend tools/drift_review.py mapping.")
        return "\n".join(lines)

    lines.append("Affected rows:")
    for area, hits in affected:
        lines.append(f"- {area.name}")
        lines.append(f"  Proposed status: {area.proposed_status}")
        lines.append(f"  Triggered by: {', '.join(hits)}")
        lines.append(f"  Note: {area.note}")
    lines.append("")

    required_ordered: list[str] = []
    for area, _hits in affected:
        for check in area.required_checks:
            if check not in required_ordered:
                required_ordered.append(check)

    lines.append("Required checks:")
    for check in required_ordered:
        marker = "x" if check in passed_checks else " "
        lines.append(f"- [{marker}] {check}")
    lines.append("")

    missing = [check for check in required_ordered if check not in passed_checks]
    lines.append("Missing checks:")
    if missing:
        for check in missing:
            lines.append(f"- {check}")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("Suggested matrix/note updates:")
    for area, _hits in affected:
        lines.append(f"- Review `{area.name}` in `project_control/DRIFT_MATRIX.md` and refresh Last Reviewed / Notes if trust changed.")

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Executable drift review")
    parser.add_argument(
        "files",
        nargs="*",
        help="Explicit repo-relative files to review. If omitted, uses current git status.",
    )
    parser.add_argument(
        "--passed-check",
        action="append",
        default=[],
        help="Mark a required check as already completed. Repeat as needed.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.files:
        changed_files = [path.strip() for path in args.files if path.strip()]
    else:
        changed_files = get_changed_files()

    passed_checks = {check.strip() for check in args.passed_check if check.strip()}
    print(render_report(changed_files, passed_checks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
