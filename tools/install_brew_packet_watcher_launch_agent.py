#!/usr/bin/env python3
"""Install a macOS LaunchAgent for the recipe inbox watcher."""

from __future__ import annotations

import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LABEL = "com.brewassistant.packetwatcher"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def plist_payload() -> dict:
    log_dir = ROOT / "brew_packets"
    log_dir.mkdir(parents=True, exist_ok=True)
    return {
        "Label": LABEL,
        "ProgramArguments": [
            sys.executable,
            str(ROOT / "tools" / "brew_packet_watcher.py"),
            "--quiet",
        ],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(log_dir / "watcher.out.log"),
        "StandardErrorPath": str(log_dir / "watcher.err.log"),
        "EnvironmentVariables": {
            "PATH": os.environ.get("PATH", ""),
        },
    }


def launchctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def install() -> int:
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    if PLIST_PATH.exists():
        uninstall()
    with PLIST_PATH.open("wb") as handle:
        plistlib.dump(plist_payload(), handle)
    proc = launchctl("load", str(PLIST_PATH))
    if proc.returncode != 0:
        print("BREW_PACKET_WATCHER_INSTALL_FAILED")
        print((proc.stdout + proc.stderr).strip())
        return proc.returncode
    print("BREW_PACKET_WATCHER_INSTALLED")
    print(f"Recipe inbox: {ROOT / 'recipe_inbox'}")
    print(f"Packet reports: {ROOT / 'brew_packets'}")
    return 0


def uninstall() -> int:
    if PLIST_PATH.exists():
        launchctl("unload", str(PLIST_PATH))
        PLIST_PATH.unlink()
        print("BREW_PACKET_WATCHER_UNINSTALLED")
    else:
        print("BREW_PACKET_WATCHER_NOT_INSTALLED")
    return 0


def status() -> int:
    proc = launchctl("list", LABEL)
    installed = PLIST_PATH.exists()
    running = proc.returncode == 0
    print("BREW_PACKET_WATCHER_STATUS")
    print(f"installed: {'yes' if installed else 'no'}")
    print(f"running: {'yes' if running else 'no'}")
    print(f"plist: {PLIST_PATH}")
    print(f"recipe_inbox: {ROOT / 'recipe_inbox'}")
    print(f"brew_packets: {ROOT / 'brew_packets'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the macOS recipe-inbox watcher LaunchAgent")
    parser.add_argument("command", choices=["install", "uninstall", "status"])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "install":
        return install()
    if args.command == "uninstall":
        return uninstall()
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
