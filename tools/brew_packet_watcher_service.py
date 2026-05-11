#!/usr/bin/env python3
"""Manage the recipe-inbox watcher service.

Persistent service support:
- macOS: LaunchAgent
- Windows: Startup-folder command file
- Linux: systemd --user unit when systemd is available
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WINDOWS_STARTUP_NAME = "Brew Assistant Packet Watcher.cmd"
LINUX_UNIT_NAME = "brew-assistant-packet-watcher.service"


def platform_key() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    return system


def manual_command() -> str:
    return f"{sys.executable} tools/brew_packet_watcher.py"


def run_proc(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def print_proc_failure(header: str, proc: subprocess.CompletedProcess[str]) -> int:
    print(header)
    output = (proc.stdout + proc.stderr).strip()
    if output:
        print(output)
    return proc.returncode


def run_macos(command: str) -> int:
    script = ROOT / "tools" / "install_brew_packet_watcher_launch_agent.py"
    return subprocess.run([sys.executable, str(script), command], cwd=ROOT).returncode


def windows_startup_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA is not set; cannot find Windows Startup folder.")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def windows_startup_file() -> Path:
    return windows_startup_dir() / WINDOWS_STARTUP_NAME


def windows_script_text() -> str:
    log_dir = ROOT / "brew_packets"
    return "\r\n".join(
        [
            "@echo off",
            f'cd /d "{ROOT}"',
            f'if not exist "{log_dir}" mkdir "{log_dir}"',
            f'"{sys.executable}" "{ROOT / "tools" / "brew_packet_watcher.py"}" --quiet >> "{log_dir / "watcher.out.log"}" 2>> "{log_dir / "watcher.err.log"}"',
            "",
        ]
    )


def run_windows(command: str) -> int:
    startup_file = windows_startup_file()
    if command == "install":
        startup_file.parent.mkdir(parents=True, exist_ok=True)
        (ROOT / "brew_packets").mkdir(parents=True, exist_ok=True)
        startup_file.write_text(windows_script_text(), encoding="utf-8", newline="")
        print("BREW_PACKET_WATCHER_INSTALLED")
        print("Platform: Windows Startup folder")
        print(f"Startup file: {startup_file}")
        print(f"Recipe inbox: {ROOT / 'recipe_inbox'}")
        print(f"Packet reports: {ROOT / 'brew_packets'}")
        print("The watcher starts at the next login. To run it now, open the startup file or run the manual watcher command.")
        return 0
    if command == "uninstall":
        if startup_file.exists():
            startup_file.unlink()
            print("BREW_PACKET_WATCHER_UNINSTALLED")
        else:
            print("BREW_PACKET_WATCHER_NOT_INSTALLED")
        return 0
    print("BREW_PACKET_WATCHER_STATUS")
    print("platform: windows")
    print(f"installed: {'yes' if startup_file.exists() else 'no'}")
    print(f"startup_file: {startup_file}")
    print(f"recipe_inbox: {ROOT / 'recipe_inbox'}")
    print(f"brew_packets: {ROOT / 'brew_packets'}")
    return 0


@dataclass(frozen=True)
class LinuxPaths:
    unit_dir: Path
    unit_file: Path


def linux_paths() -> LinuxPaths:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    unit_dir = config_home / "systemd" / "user"
    return LinuxPaths(unit_dir=unit_dir, unit_file=unit_dir / LINUX_UNIT_NAME)


def linux_unit_text() -> str:
    return f"""[Unit]
Description=Brew Assistant recipe inbox watcher

[Service]
Type=simple
WorkingDirectory={ROOT}
ExecStart={sys.executable} {ROOT / "tools" / "brew_packet_watcher.py"} --quiet
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
"""


def systemctl_user_available() -> bool:
    return shutil.which("systemctl") is not None


def run_linux(command: str) -> int:
    paths = linux_paths()
    if command == "install":
        if not systemctl_user_available():
            print("BREW_PACKET_WATCHER_SERVICE_PLATFORM linux")
            print("systemctl is not available. Manual watcher command:")
            print(manual_command())
            return 0
        paths.unit_dir.mkdir(parents=True, exist_ok=True)
        (ROOT / "brew_packets").mkdir(parents=True, exist_ok=True)
        paths.unit_file.write_text(linux_unit_text(), encoding="utf-8")
        for cmd in (
            ["systemctl", "--user", "daemon-reload"],
            ["systemctl", "--user", "enable", "--now", LINUX_UNIT_NAME],
        ):
            proc = run_proc(cmd)
            if proc.returncode != 0:
                return print_proc_failure("BREW_PACKET_WATCHER_INSTALL_FAILED", proc)
        print("BREW_PACKET_WATCHER_INSTALLED")
        print("Platform: Linux systemd --user")
        print(f"Unit file: {paths.unit_file}")
        print(f"Recipe inbox: {ROOT / 'recipe_inbox'}")
        print(f"Packet reports: {ROOT / 'brew_packets'}")
        return 0
    if command == "uninstall":
        if systemctl_user_available():
            run_proc(["systemctl", "--user", "disable", "--now", LINUX_UNIT_NAME])
            run_proc(["systemctl", "--user", "daemon-reload"])
        if paths.unit_file.exists():
            paths.unit_file.unlink()
            print("BREW_PACKET_WATCHER_UNINSTALLED")
        else:
            print("BREW_PACKET_WATCHER_NOT_INSTALLED")
        return 0
    active = "unknown"
    enabled = "unknown"
    if systemctl_user_available():
        active_proc = run_proc(["systemctl", "--user", "is-active", LINUX_UNIT_NAME])
        enabled_proc = run_proc(["systemctl", "--user", "is-enabled", LINUX_UNIT_NAME])
        active = "yes" if active_proc.returncode == 0 else "no"
        enabled = "yes" if enabled_proc.returncode == 0 else "no"
    print("BREW_PACKET_WATCHER_STATUS")
    print("platform: linux")
    print(f"installed: {'yes' if paths.unit_file.exists() else 'no'}")
    print(f"enabled: {enabled}")
    print(f"running: {active}")
    print(f"unit_file: {paths.unit_file}")
    print(f"recipe_inbox: {ROOT / 'recipe_inbox'}")
    print(f"brew_packets: {ROOT / 'brew_packets'}")
    return 0


def run(command: str) -> int:
    key = platform_key()
    if key == "macos":
        return run_macos(command)
    if key == "windows":
        return run_windows(command)
    if key == "linux":
        return run_linux(command)
    print(f"BREW_PACKET_WATCHER_SERVICE_PLATFORM {platform_key()}")
    print(f"Persistent service backend is not implemented for this platform yet.")
    print("Manual watcher command:")
    print(manual_command())
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
