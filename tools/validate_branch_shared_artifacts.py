#!/usr/bin/env python3
"""Validate that shared planning brew-sheet artifacts do not drift across branches."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import PurePosixPath


BREW_DAY_SHEETS_DIR = PurePosixPath("brewing/brew_day_sheets")
TOOLS_DIR = PurePosixPath("tools")


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def resolve_ref(name: str) -> str | None:
    candidates = [
        name,
        f"refs/heads/{name}",
        f"origin/{name}",
        f"refs/remotes/origin/{name}",
    ]
    for candidate in candidates:
        result = run_git("rev-parse", "--verify", candidate)
        if result.returncode == 0:
            return candidate
    return None


def tracked_files(ref: str) -> list[str]:
    result = run_git("ls-tree", "-r", "--name-only", ref, "--", "brewing/brew_day_sheets", "tools")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"failed to list files for {ref}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_shared_artifact(path_str: str) -> bool:
    path = PurePosixPath(path_str)
    if BREW_DAY_SHEETS_DIR in path.parents:
        if "archive" in path.parts:
            return False
        return path.name.endswith("_brew_day_sheet.html")
    if TOOLS_DIR in path.parents:
        return path.name.endswith("_brew_day_sheet.txt")
    return False


def shared_files(ref: str) -> list[str]:
    return sorted(path for path in tracked_files(ref) if is_shared_artifact(path))


def blob_id(ref: str, path: str) -> str | None:
    result = run_git("rev-parse", "--verify", f"{ref}:{path}")
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate shared planning brew-sheet parity between branches.")
    parser.add_argument("--left", default="main", help="Primary branch/ref to compare (default: main)")
    parser.add_argument("--right", default="personal", help="Secondary branch/ref to compare (default: personal)")
    args = parser.parse_args()

    left_ref = resolve_ref(args.left)
    right_ref = resolve_ref(args.right)
    if not left_ref or not right_ref:
        missing = []
        if not left_ref:
            missing.append(args.left)
        if not right_ref:
            missing.append(args.right)
        print(f"BRANCH_SHARED_ARTIFACTS_FAILED missing refs: {', '.join(missing)}", file=sys.stderr)
        return 1

    left_files = set(shared_files(left_ref))
    right_files = set(shared_files(right_ref))
    all_files = sorted(left_files | right_files)

    mismatches: list[str] = []
    for path in all_files:
        left_blob = blob_id(left_ref, path)
        right_blob = blob_id(right_ref, path)
        if left_blob != right_blob:
            left_state = left_blob or "MISSING"
            right_state = right_blob or "MISSING"
            mismatches.append(f"{path}: {args.left}={left_state} {args.right}={right_state}")

    if mismatches:
        print("BRANCH_SHARED_ARTIFACTS_FAILED")
        for line in mismatches:
            print(line)
        return 1

    print(f"BRANCH_SHARED_ARTIFACTS_OK {args.left}={left_ref} {args.right}={right_ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
