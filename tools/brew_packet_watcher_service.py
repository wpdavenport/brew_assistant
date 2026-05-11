#!/usr/bin/env python3
"""Manage the recipe-inbox watcher service.

Current support:
- macOS: LaunchAgent
- Windows/Linux: explicit stub with a manual watcher command
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def platform_key() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    return system


def run(command: str) -> int:
    if platform_key() == "macos":
        script = ROOT / "tools" / "install_brew_packet_watcher_launch_agent.py"
        return subprocess.run([sys.executable, str(script), command], cwd=ROOT).returncode
    print(f"BREW_PACKET_WATCHER_SERVICE_PLATFORM {platform_key()}")
    print(f"Persistent service backend is not implemented for this platform yet.")
    print("Manual watcher command:")
    print(f"{sys.executable} tools/brew_packet_watcher.py")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the recipe-inbox watcher background service")
    parser.add_argument("command", choices=["install", "uninstall", "status", "platform"])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "platform":
        print(platform_key())
        return 0
    return run(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
