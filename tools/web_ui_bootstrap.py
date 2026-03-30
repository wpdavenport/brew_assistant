#!/usr/bin/env python3
"""Start the Brew Assistant web UI with soft bootstrap behavior.

- If the UI is already responding, do nothing.
- If a supported background service is installed, kick it.
- Otherwise start a session-local background server.
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / ".codex-tmp" / "logs"
STDOUT_LOG = LOG_DIR / "web_ui.bootstrap.stdout.log"
STDERR_LOG = LOG_DIR / "web_ui.bootstrap.stderr.log"


def ui_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def ui_responding(host: str, port: int) -> bool:
    try:
        with urllib.request.urlopen(ui_url(host, port), timeout=1.2) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


def platform_key() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    return system


def service_status_output() -> str:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "web_ui_service.py"), "status"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return (proc.stdout + proc.stderr).strip()


def service_installed() -> bool:
    output = service_status_output()
    if platform_key() == "macos":
        return "WEB_UI_AGENT_STATUS loaded" in output or "plist:" in output
    return "WEB_UI_SERVICE_STUB" in output


def service_running() -> bool:
    output = service_status_output()
    if platform_key() == "macos":
        return "WEB_UI_AGENT_STATUS loaded" in output and "state = running" in output
    return False


def kickstart_service() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "web_ui_service.py"), "install"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def start_session_server(host: str, port: int) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with STDOUT_LOG.open("ab") as stdout_fh, STDERR_LOG.open("ab") as stderr_fh:
        subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "tools" / "web_ui.py"),
                "--host",
                host,
                "--port",
                str(port),
                "--reload",
            ],
            cwd=ROOT,
            start_new_session=True,
            stdout=stdout_fh,
            stderr=stderr_fh,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap the Brew Assistant web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--wait-seconds", type=float, default=4.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if ui_responding(args.host, args.port):
        print(f"WEB_UI_BOOTSTRAP_OK already_running {ui_url(args.host, args.port)}")
        return 0

    if service_installed():
        kickstart_service()
        origin = "service"
    else:
        start_session_server(args.host, args.port)
        origin = "session"

    deadline = time.time() + args.wait_seconds
    while time.time() < deadline:
        if ui_responding(args.host, args.port):
            print(f"WEB_UI_BOOTSTRAP_OK {origin} {ui_url(args.host, args.port)}")
            if origin == "session":
                print("WEB_UI_BOOTSTRAP_NOTE launcher_not_installed")
            return 0
        time.sleep(0.25)

    if origin == "service" and service_running():
        print(f"WEB_UI_BOOTSTRAP_OK service_unverified {ui_url(args.host, args.port)}")
        return 0

    print(f"WEB_UI_BOOTSTRAP_FAILED {origin} {ui_url(args.host, args.port)}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
