#!/usr/bin/env python3
"""Install or remove a LaunchAgent for the Brew Assistant web UI."""

from __future__ import annotations

import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LABEL = "com.serenity.brewassistant.webui"
AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_DIR = ROOT / ".codex-tmp" / "logs"
STDOUT_LOG = LOG_DIR / "web_ui.stdout.log"
STDERR_LOG = LOG_DIR / "web_ui.stderr.log"


def ensure_dirs() -> None:
    AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def plist_payload() -> dict:
    return {
        "Label": LABEL,
        "ProgramArguments": [
            sys.executable,
            str(ROOT / "tools" / "web_ui.py"),
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
            "--reload",
        ],
        "WorkingDirectory": str(ROOT),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(STDOUT_LOG),
        "StandardErrorPath": str(STDERR_LOG),
        "ProcessType": "Background",
    }


def run_launchctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["/bin/launchctl", *args], capture_output=True, text=True)


def bootstrap_target() -> str:
    return f"gui/{os.getuid()}"


def install() -> int:
    ensure_dirs()
    with AGENT_PATH.open("wb") as fh:
        plistlib.dump(plist_payload(), fh)
    run_launchctl("bootout", bootstrap_target(), str(AGENT_PATH))
    proc = run_launchctl("bootstrap", bootstrap_target(), str(AGENT_PATH))
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return proc.returncode
    run_launchctl("kickstart", "-k", f"{bootstrap_target()}/{LABEL}")
    print(f"WEB_UI_AGENT_INSTALLED {AGENT_PATH}")
    return 0


def uninstall() -> int:
    run_launchctl("bootout", bootstrap_target(), str(AGENT_PATH))
    if AGENT_PATH.exists():
        AGENT_PATH.unlink()
    print(f"WEB_UI_AGENT_REMOVED {AGENT_PATH}")
    return 0


def status() -> int:
    proc = run_launchctl("print", f"{bootstrap_target()}/{LABEL}")
    if proc.returncode == 0:
        print("WEB_UI_AGENT_STATUS loaded")
        print(proc.stdout)
        return 0
    print("WEB_UI_AGENT_STATUS not_loaded")
    if AGENT_PATH.exists():
        print(f"plist: {AGENT_PATH}")
    if proc.stderr:
        print(proc.stderr.strip())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the Brew Assistant web UI LaunchAgent")
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
