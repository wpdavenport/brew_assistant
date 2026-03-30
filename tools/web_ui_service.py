#!/usr/bin/env python3
"""Cross-platform service manager plumbing for the Brew Assistant web UI.

Current support:
- macOS: implemented via LaunchAgent
- Windows: planned
- Linux: planned
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


def backend_script() -> Path | None:
    key = platform_key()
    if key == "macos":
        return ROOT / "tools" / "install_web_ui_launch_agent.py"
    return None


def install_hint() -> str:
    key = platform_key()
    if key == "windows":
        return "Windows launcher backend is not implemented yet. Planned path: Task Scheduler or Startup-folder wrapper."
    if key == "linux":
        return "Linux launcher backend is not implemented yet. Planned path: systemd --user service."
    return f"Unsupported platform backend: {key}"


def run_backend(command: str) -> int:
    script = backend_script()
    if script is None:
        print(f"WEB_UI_SERVICE_PLATFORM {platform_key()}")
        print(f"WEB_UI_SERVICE_STUB {command}")
        print(install_hint())
        return 0
    proc = subprocess.run([sys.executable, str(script), command], cwd=ROOT)
    return proc.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the Brew Assistant web UI background service")
    parser.add_argument("command", choices=["install", "uninstall", "status", "platform"])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "platform":
        print(platform_key())
        return 0
    return run_backend(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
