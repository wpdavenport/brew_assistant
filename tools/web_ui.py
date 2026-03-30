#!/usr/bin/env python3
"""Simple local web UI for browsing brew-assistant artifacts."""

from __future__ import annotations

import argparse
import html
import json
import mimetypes
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ALLOWED_ROOTS = [
    ROOT / "recipes" / "html_exports",
    ROOT / "brewing" / "brew_day_sheets",
    ROOT / "libraries" / "inventory",
    ROOT / "profiles",
    ROOT / "libraries" / "beer_research",
]

SECTION_CONFIG = {
    "Recipe Prints": ROOT / "recipes" / "html_exports",
    "Brew Day Sheets": ROOT / "brewing" / "brew_day_sheets",
}

CURATED_SECTIONS = {
    "Inventory": [
        ROOT / "libraries" / "inventory" / "stock.json",
        ROOT / "libraries" / "inventory" / "brew_history.json",
        ROOT / "libraries" / "inventory" / "recipe_usage.json",
        ROOT / "libraries" / "inventory" / "README.md",
    ],
    "Profiles": [
        ROOT / "profiles" / "equipment.yaml",
        ROOT / "profiles" / "water_profiles.md",
        ROOT / "libraries" / "yeast_library.md",
    ],
    "Research": [
        ROOT / "libraries" / "beer_research" / "_index.md",
        ROOT / "libraries" / "beer_research" / "11C_strong_bitter.md",
        ROOT / "libraries" / "beer_research" / "22A_double_ipa.md",
        ROOT / "libraries" / "beer_research" / "3C_czech_premium_pale_lager.md",
        ROOT / "libraries" / "beer_research" / "34B_mixed_style_beer.md",
        ROOT / "libraries" / "beer_research" / "9C_baltic_porter.md",
    ],
}

DEFAULT_FILE = ROOT / "recipes" / "html_exports" / "davenport_esb_11C.html"


def dashboard_item(label: str, mode: str) -> dict[str, str]:
    return {
        "label": label,
        "view": f"/dashboard?mode={urllib.parse.quote(mode)}",
        "raw": f"/dashboard?mode={urllib.parse.quote(mode)}&raw=1",
        "current": f"dashboard:{mode}",
    }


def ensure_allowed(path: Path) -> Path:
    resolved = path.resolve()
    for allowed in ALLOWED_ROOTS:
        try:
            resolved.relative_to(allowed.resolve())
            return resolved
        except ValueError:
            continue
    raise ValueError(f"Path outside allowed roots: {path}")


def file_label(path: Path) -> str:
    name = path.stem.replace("_", " ")
    if path.suffix == ".json":
        return path.name
    return name.title()


def collect_section_entries() -> dict[str, list[dict[str, str]]]:
    sections: dict[str, list[dict[str, str]]] = {
        "Operations": [
            dashboard_item("Batch State", "state"),
            dashboard_item("Next Actions", "next"),
        ]
    }
    for label, folder in SECTION_CONFIG.items():
        entries: list[dict[str, str]] = []
        for path in sorted(folder.glob("*.html")):
            if path.is_dir():
                continue
            rel = path.relative_to(ROOT).as_posix()
            entries.append(
                {
                    "label": file_label(path),
                    "view": viewer_url(path),
                    "raw": raw_url(path),
                    "current": rel,
                }
            )
        sections[label] = entries
    for label, entries in CURATED_SECTIONS.items():
        section_entries: list[dict[str, str]] = []
        for path in entries:
            if not path.exists():
                continue
            rel = path.relative_to(ROOT).as_posix()
            section_entries.append(
                {
                    "label": file_label(path),
                    "view": viewer_url(path),
                    "raw": raw_url(path),
                    "current": rel,
                }
            )
        sections[label] = section_entries
    return sections


def viewer_url(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    return "/view?path=" + urllib.parse.quote(rel)


def raw_url(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    return "/raw?path=" + urllib.parse.quote(rel)


def render_nav(current: str) -> str:
    sections = collect_section_entries()
    blocks = []
    for label, entries in sections.items():
        links = []
        for entry in entries:
            active = ' class="active"' if entry["current"] == current else ""
            links.append(
                f'<a{active} data-current="{html.escape(entry["current"])}" data-raw="{html.escape(entry["raw"])}" href="{html.escape(entry["view"])}" target="content">{html.escape(entry["label"])}</a>'
            )
        if not links:
            links.append('<span class="empty">No files yet</span>')
        blocks.append(
            f"<section><h2>{html.escape(label)}</h2><div class=\"nav-group\">{''.join(links)}</div></section>"
        )
    return "\n".join(blocks)


def render_index(default_path: str) -> bytes:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Brew Assistant Viewer</title>
  <style>
    :root {{
      --bg: #f2ede4;
      --paper: #fffdf8;
      --ink: #1d1a18;
      --muted: #6a635d;
      --rule: #d6cab8;
      --accent: #8a4b24;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background: var(--bg);
    }}
    .app {{
      display: grid;
      grid-template-columns: 300px 1fr;
      min-height: 100vh;
    }}
    aside {{
      border-right: 1px solid var(--rule);
      background: #f7f2e9;
      padding: 18px 16px 20px;
      overflow-y: auto;
    }}
    main {{
      background: var(--paper);
      min-width: 0;
    }}
    h1 {{
      margin: 0 0 6px;
      color: var(--accent);
      font-size: 22px;
      line-height: 1.1;
    }}
    .sub {{
      margin: 0 0 18px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.3;
    }}
    section {{
      margin-bottom: 18px;
    }}
    h2 {{
      margin: 0 0 8px;
      padding-bottom: 4px;
      border-bottom: 1px solid var(--rule);
      font-size: 13px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .nav-group {{
      display: grid;
      gap: 4px;
    }}
    a {{
      color: var(--ink);
      text-decoration: none;
    }}
    .nav-group a {{
      display: block;
      padding: 6px 8px;
      border-radius: 6px;
      font-size: 14px;
      line-height: 1.25;
    }}
    .nav-group a:hover {{
      background: #efe5d6;
    }}
    .nav-group a.active {{
      background: #e6d4bc;
      color: #4d2a13;
      font-weight: 700;
    }}
    .empty {{
      color: var(--muted);
      font-size: 13px;
      padding: 4px 2px;
    }}
    .toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      padding: 10px 14px;
      border-bottom: 1px solid var(--rule);
      background: #fcf8f1;
      font-size: 14px;
    }}
    .toolbar .hint {{
      color: var(--muted);
    }}
    .toolbar a {{
      color: var(--accent);
      font-weight: 700;
    }}
    iframe {{
      width: 100%;
      height: calc(100vh - 49px);
      border: 0;
      display: block;
      background: white;
    }}
    @media (max-width: 900px) {{
      .app {{
        grid-template-columns: 1fr;
      }}
      aside {{
        border-right: 0;
        border-bottom: 1px solid var(--rule);
      }}
      iframe {{
        height: 75vh;
      }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <h1>Brew Assistant Viewer</h1>
      <p class="sub">Central browser for recipe prints, brew sheets, inventory, profiles, and research.</p>
      {render_nav(default_path)}
    </aside>
    <main>
      <div class="toolbar">
        <span class="hint">Local viewer. Print from the content pane when needed.</span>
        <a id="raw-link" href="{html.escape('/raw?path=' + urllib.parse.quote(default_path))}" target="content">Open Raw</a>
      </div>
      <iframe id="content-frame" name="content" src="{html.escape('/view?path=' + urllib.parse.quote(default_path))}"></iframe>
    </main>
  </div>
  <script>
    const links = Array.from(document.querySelectorAll('.nav-group a[data-current]'));
    const rawLink = document.getElementById('raw-link');
    const frame = document.getElementById('content-frame');

    function setActive(current, rawHref) {{
      for (const link of links) {{
        link.classList.toggle('active', link.dataset.current === current);
      }}
      rawLink.href = rawHref;
    }}

    for (const link of links) {{
      link.addEventListener('click', () => {{
        setActive(link.dataset.current, link.dataset.raw);
      }});
    }}

    setActive({json.dumps(default_path)}, {json.dumps('/raw?path=' + urllib.parse.quote(default_path))});
  </script>
</body>
</html>
""".encode("utf-8")


def render_text_page(path: Path, body: str) -> bytes:
    title = html.escape(path.relative_to(ROOT).as_posix())
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{
      margin: 0;
      background: #f5efe5;
      color: #1d1a18;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    .wrap {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 18px 22px 28px;
    }}
    .top {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 12px;
      font-family: Georgia, "Times New Roman", serif;
    }}
    h1 {{
      margin: 0;
      font-size: 22px;
      color: #8a4b24;
      line-height: 1.1;
    }}
    a {{
      color: #8a4b24;
      text-decoration: none;
      font-weight: 700;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      background: #fffdf8;
      border: 1px solid #d6cab8;
      border-radius: 8px;
      padding: 14px 16px;
      font-size: 13px;
      line-height: 1.45;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <h1>{title}</h1>
      <a href="{html.escape(raw_url(path))}">Raw file</a>
    </div>
    <pre>{html.escape(body)}</pre>
  </div>
</body>
</html>
""".encode("utf-8")


def render_dashboard_page(title: str, body: str) -> bytes:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{
      margin: 0;
      background: #f5efe5;
      color: #1d1a18;
      font-family: Georgia, "Times New Roman", serif;
    }}
    .wrap {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 18px 22px 28px;
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: 28px;
      color: #8a4b24;
      line-height: 1.1;
    }}
    .sub {{
      margin: 0 0 16px;
      color: #6a635d;
      font-size: 15px;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      background: #fffdf8;
      border: 1px solid #d6cab8;
      border-radius: 8px;
      padding: 14px 16px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 13px;
      line-height: 1.45;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <p class="sub">Live operational view generated from current repo state.</p>
    <pre>{html.escape(body)}</pre>
  </div>
</body>
</html>
""".encode("utf-8")


def dashboard_output(mode: str) -> str:
    cmd = ["python3", "tools/batch_state_summary.py"]
    if mode == "next":
        cmd.append("--with-next-actions")
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)
    return proc.stdout


class BrewUIHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/":
            default_rel = DEFAULT_FILE.relative_to(ROOT).as_posix()
            self.respond_bytes(200, "text/html; charset=utf-8", render_index(default_rel))
            return

        if parsed.path == "/dashboard":
            mode = params.get("mode", ["state"])[0]
            if mode not in {"state", "next"}:
                self.respond_text(400, "Unsupported dashboard mode.")
                return
            payload = dashboard_output(mode)
            if params.get("raw", ["0"])[0] == "1":
                self.respond_bytes(200, "text/plain; charset=utf-8", payload.encode("utf-8"))
                return
            title = "Batch State" if mode == "state" else "Next Actions"
            self.respond_bytes(200, "text/html; charset=utf-8", render_dashboard_page(title, payload))
            return

        if parsed.path in {"/view", "/raw"}:
            rel = params.get("path", [""])[0]
            if not rel:
                self.respond_text(400, "Missing path parameter.")
                return
            try:
                path = ensure_allowed(ROOT / rel)
            except ValueError:
                self.respond_text(403, "Path not allowed.")
                return
            if not path.exists() or not path.is_file():
                self.respond_text(404, "File not found.")
                return

            if parsed.path == "/raw":
                self.serve_raw(path)
                return

            if path.suffix == ".html":
                self.serve_raw(path)
                return

            body = path.read_text(encoding="utf-8")
            if path.suffix == ".json":
                body = json.dumps(json.loads(body), indent=2)
            self.respond_bytes(200, "text/html; charset=utf-8", render_text_page(path, body))
            return

        self.respond_text(404, "Not found.")

    def serve_raw(self, path: Path) -> None:
        mime, _ = mimetypes.guess_type(path.name)
        if not mime:
            mime = "text/plain; charset=utf-8"
        if path.suffix in {".md", ".yaml", ".yml", ".json", ".txt"}:
            self.respond_bytes(200, "text/plain; charset=utf-8", path.read_text(encoding="utf-8").encode("utf-8"))
        else:
            self.respond_bytes(200, mime, path.read_bytes())

    def respond_text(self, code: int, message: str) -> None:
        self.respond_bytes(code, "text/plain; charset=utf-8", message.encode("utf-8"))

    def respond_bytes(self, code: int, content_type: str, payload: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local Brew Assistant web viewer")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765)")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), BrewUIHandler)
    print(f"BREW_UI_OK http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
