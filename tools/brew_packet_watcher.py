#!/usr/bin/env python3
"""Watch recipe_inbox/ and create brew packets when files are dropped in.

This is intentionally dependency-free. It polls for stable files, runs the
existing brew-packet workflow, and writes an HTML status page for non-terminal
operators to open.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INBOX_DIR = ROOT / "recipe_inbox"
PACKETS_DIR = ROOT / "brew_packets"
SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt"}


@dataclass(frozen=True)
class FileStamp:
    mtime_ns: int
    size: int


def slugify(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return value or "recipe"


def file_stamp(path: Path) -> FileStamp:
    stat = path.stat()
    return FileStamp(mtime_ns=stat.st_mtime_ns, size=stat.st_size)


def extract_brew_date(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    patterns = (
        r"^\s*brew\s*date\s*:\s*(\d{4}-\d{2}-\d{2})\s*$",
        r"^\s*date\s*:\s*(\d{4}-\d{2}-\d{2})\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1)
    return ""


def packet_dir_for(path: Path) -> Path:
    return PACKETS_DIR / slugify(path.stem)


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def href(from_dir: Path, target_text: str) -> str:
    target = ROOT / target_text
    if not target.exists():
        return html.escape(target_text)
    return html.escape(os.path.relpath(target, from_dir))


def parse_output_links(output: str) -> dict[str, str]:
    links: dict[str, str] = {}
    for raw in output.splitlines():
        line = raw.strip()
        if line.startswith("Recipe print:"):
            links["Recipe print"] = line.split(":", 1)[1].strip()
        elif line.startswith("Brew sheet:"):
            links["Brew sheet"] = line.split(":", 1)[1].strip()
        elif line.startswith("BeerXML:"):
            links["BeerXML"] = line.split(":", 1)[1].strip()
    return links


def write_report(path: Path, source: Path, rc: int, output: str, brew_date: str) -> Path:
    packet_dir = packet_dir_for(source)
    packet_dir.mkdir(parents=True, exist_ok=True)
    status = "READY" if rc == 0 and "BREW_PACKET_READY" in output else "NEEDS ATTENTION"
    links = parse_output_links(output)
    link_items = "\n".join(
        f'<li><a href="{href(packet_dir, target)}">{html.escape(label)}</a></li>'
        for label, target in links.items()
    ) or "<li>No packet links found. Review output below.</li>"
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Brew Packet - {html.escape(source.stem)}</title>
  <style>
    body {{ font-family: Helvetica, Arial, sans-serif; margin: 2rem; line-height: 1.45; color: #1a1a1a; }}
    .status {{ display: inline-block; padding: 0.35rem 0.55rem; border: 2px solid #333; font-weight: 700; }}
    .ready {{ border-color: #207227; color: #207227; }}
    .attention {{ border-color: #a33321; color: #a33321; }}
    pre {{ white-space: pre-wrap; background: #f3f3f3; padding: 1rem; border: 1px solid #ccc; }}
  </style>
</head>
<body>
  <h1>{html.escape(source.stem)}</h1>
  <p class="status {'ready' if status == 'READY' else 'attention'}">{status}</p>
  <p><strong>Source:</strong> {html.escape(rel(source))}</p>
  <p><strong>Brew date:</strong> {html.escape(brew_date or 'not provided')}</p>
  <h2>Packet Files</h2>
  <ul>
    {link_items}
  </ul>
  <h2>Output</h2>
  <pre>{html.escape(output)}</pre>
</body>
</html>
"""
    report = packet_dir / "index.html"
    report.write_text(page, encoding="utf-8")
    return report


def run_brew_packet(source: Path) -> tuple[int, str, str]:
    brew_date = extract_brew_date(source)
    cmd = [sys.executable, "tools/brew_packet.py", "--recipe", rel(source)]
    if brew_date:
        cmd.extend(["--date", brew_date])
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip(), brew_date


def candidate_files(inbox: Path) -> list[Path]:
    if not inbox.exists():
        return []
    return sorted(
        path
        for path in inbox.iterdir()
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_SUFFIXES
        and not path.name.startswith(".")
        and path.name.lower() != "readme.md"
    )


def process_file(path: Path, seen: dict[Path, FileStamp], quiet: bool) -> None:
    stamp = file_stamp(path)
    rc, output, brew_date = run_brew_packet(path)
    report = write_report(path, path, rc, output, brew_date)
    seen[path] = stamp
    if not quiet:
        status = "READY" if rc == 0 else "NEEDS ATTENTION"
        print(f"{status}: {rel(path)} -> {rel(report)}")


def run_once(inbox: Path, quiet: bool) -> int:
    seen: dict[Path, FileStamp] = {}
    rc = 0
    for path in candidate_files(inbox):
        try:
            process_file(path, seen, quiet)
        except Exception as exc:
            rc = 1
            output = f"BREW_PACKET_FAILED\n- {exc}"
            report = write_report(path, path, 1, output, extract_brew_date(path) if path.exists() else "")
            if not quiet:
                print(f"NEEDS ATTENTION: {rel(path)} -> {rel(report)}")
    return rc


def watch(inbox: Path, interval: float, quiet: bool) -> int:
    inbox.mkdir(parents=True, exist_ok=True)
    PACKETS_DIR.mkdir(parents=True, exist_ok=True)
    seen: dict[Path, FileStamp] = {}
    pending: dict[Path, tuple[FileStamp, float]] = {}
    if not quiet:
        print(f"WATCHING {rel(inbox)}")
        print(f"REPORTS  {rel(PACKETS_DIR)}")
    while True:
        now = time.monotonic()
        current_files = candidate_files(inbox)
        for path in current_files:
            stamp = file_stamp(path)
            if seen.get(path) == stamp:
                continue
            pending_stamp, first_seen = pending.get(path, (stamp, now))
            if pending_stamp != stamp:
                pending[path] = (stamp, now)
                continue
            if now - first_seen < max(interval, 1.0):
                pending[path] = (stamp, first_seen)
                continue
            try:
                process_file(path, seen, quiet)
            except Exception as exc:
                output = f"BREW_PACKET_FAILED\n- {exc}"
                report = write_report(path, path, 1, output, extract_brew_date(path) if path.exists() else "")
                seen[path] = stamp
                if not quiet:
                    print(f"NEEDS ATTENTION: {rel(path)} -> {rel(report)}")
            pending.pop(path, None)
        for path in list(pending):
            if path not in current_files:
                pending.pop(path, None)
        time.sleep(interval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Watch recipe_inbox and generate brew packets")
    parser.add_argument("--inbox", default=INBOX_DIR.as_posix(), help="Folder to watch")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")
    parser.add_argument("--once", action="store_true", help="Process current inbox files once and exit")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    inbox = Path(args.inbox)
    if not inbox.is_absolute():
        inbox = ROOT / inbox
    if args.once:
        return run_once(inbox, args.quiet)
    return watch(inbox, args.interval, args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
