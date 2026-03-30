#!/usr/bin/env python3
"""Simple local web UI for browsing brew-assistant artifacts."""

from __future__ import annotations

import argparse
import html
import json
import math
import mimetypes
import os
import platform
import re
import subprocess
import sys
import threading
import time
import urllib.parse
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ALLOWED_ROOTS = [
    ROOT,
    ROOT / "recipes" / "html_exports",
    ROOT / "brewing" / "brew_day_sheets",
    ROOT / "libraries" / "inventory",
    ROOT / "libraries",
    ROOT / "profiles",
    ROOT / "libraries" / "beer_research",
]

CURATED_SECTIONS = {
    "Inventory": [
        ROOT / "libraries" / "inventory" / "stock.json",
        ROOT / "libraries" / "inventory" / "shopping_intent.json",
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

DEFAULT_FILE = ROOT / "README.md"
BEER_RESEARCH_DIR = ROOT / "libraries" / "beer_research"
BJCP_OVERLAYS_DIR = ROOT / "libraries" / "bjcp_overlays"
STOCK_FILE = ROOT / "libraries" / "inventory" / "stock.json"
RECIPE_USAGE_FILE = ROOT / "libraries" / "inventory" / "recipe_usage.json"
ACTIVE_ARTIFACTS_FILE = ROOT / "project_control" / "ACTIVE_ARTIFACTS.json"
SHOPPING_INTENT_FILE = ROOT / "libraries" / "inventory" / "shopping_intent.json"
WEB_UI_SOURCE = Path(__file__).resolve()
LAUNCH_AGENT_LABEL = "com.serenity.brewassistant.webui"
LAUNCH_AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def normalize_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def resolve_recipe_markdown(token: str) -> Path | None:
    explicit = ROOT / token
    if explicit.exists() and explicit.suffix == ".md":
        return explicit.resolve()
    candidates = [
        path
        for path in (ROOT / "recipes").rglob("*.md")
        if "historical" not in path.parts and "locked" not in path.parts
    ]
    token_n = normalize_token(token)
    for path in candidates:
        for candidate in recipe_stem_candidates(path.stem):
            if normalize_token(candidate) == token_n:
                return path.resolve()
    return None


def recipe_stem_candidates(stem: str) -> list[str]:
    candidates = [stem]
    candidates.append(re.sub(r"_clone_\d{1,2}[A-Z]$", "", stem))
    candidates.append(re.sub(r"_\d{1,2}[A-Z]$", "", stem))
    out: list[str] = []
    for value in candidates:
        if value and value not in out:
            out.append(value)
    return out


def dashboard_item(label: str, mode: str) -> dict[str, str]:
    return {
        "label": label,
        "view": f"/dashboard?mode={urllib.parse.quote(mode)}",
        "raw": f"/dashboard?mode={urllib.parse.quote(mode)}&raw=1",
        "current": f"dashboard:{mode}",
    }


def shopping_item(label: str, recipe: str = "") -> dict[str, str]:
    if recipe:
        view = f"/shopping?recipe={urllib.parse.quote(recipe)}"
        raw = view + "&raw=1"
        current = f"shopping:{recipe}"
    else:
        view = "/shopping"
        raw = "/shopping?raw=1"
        current = "shopping:active"
    return {
        "label": label,
        "view": view,
        "raw": raw,
        "current": current,
    }


def operator_url(action: str, recipe: str = "", **params: str) -> str:
    query: dict[str, str] = {"action": action}
    if recipe:
        query["recipe"] = recipe
    for key, value in params.items():
        if value:
            query[key] = value
    return "/operate?" + urllib.parse.urlencode(query)


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


def markdown_to_html(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    out: list[str] = []
    in_list = False
    in_code = False
    code_lines: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            out.append(f"<p>{html.escape(' '.join(paragraph).strip())}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            close_list()
            if in_code:
                out.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            flush_paragraph()
            close_list()
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            close_list()
            out.append(f"<h1>{html.escape(stripped[2:].strip())}</h1>")
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            close_list()
            out.append(f"<h2>{html.escape(stripped[3:].strip())}</h2>")
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            close_list()
            out.append(f"<h3>{html.escape(stripped[4:].strip())}</h3>")
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{html.escape(stripped[2:].strip())}</li>")
            continue
        paragraph.append(stripped)

    flush_paragraph()
    close_list()
    if in_code:
        out.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
    return "\n".join(out)


def recipe_category(recipe_path: Path) -> str:
    text = recipe_path.read_text(encoding="utf-8")
    match = re.search(r"BJCP Category:\s*([0-9]{1,2}[A-Z])", text, flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def collect_section_entries() -> dict[str, list[dict[str, str]]]:
    sections: dict[str, list[dict[str, str]]] = {
        "Operations": [
            {
                "label": "Home",
                "view": viewer_url(DEFAULT_FILE),
                "raw": raw_url(DEFAULT_FILE),
                "current": DEFAULT_FILE.relative_to(ROOT).as_posix(),
            },
            dashboard_item("Batch State", "state"),
            dashboard_item("Next Actions", "next"),
            shopping_item("Shopping"),
        ]
    }
    beer_groups: dict[str, dict[str, object]] = {}
    for path in sorted((ROOT / "recipes" / "html_exports").glob("*.html")):
        if path.is_dir():
            continue
        stem = path.stem
        candidates = recipe_stem_candidates(stem)
        group_key = candidates[-1]
        beer_groups[group_key] = {
            "label": file_label(path),
            "primary": {
                "label": "Recipe Print",
                "view": viewer_url(path),
                "raw": raw_url(path),
                "current": path.relative_to(ROOT).as_posix(),
            },
            "items": [],
            "candidates": {normalize_token(value) for value in candidates},
        }

    recipe_candidates = [
        path
        for path in (ROOT / "recipes").rglob("*.md")
        if "historical" not in path.parts and "locked" not in path.parts
    ]
    for path in recipe_candidates:
        norm_stems = {normalize_token(value) for value in recipe_stem_candidates(path.stem)}
        for group in beer_groups.values():
            if norm_stems & group["candidates"]:
                category = recipe_category(path)
                group["items"].append(
                    {
                        "label": "Recipe Source",
                        "view": viewer_url(path),
                        "raw": raw_url(path),
                        "current": path.relative_to(ROOT).as_posix(),
                    }
                )
                group["items"].append(shopping_item("Shopping", path.relative_to(ROOT).as_posix()))
                if category:
                    research = sorted(BEER_RESEARCH_DIR.glob(f"{category}_*.md"))
                    overlays = sorted(BJCP_OVERLAYS_DIR.glob(f"bjcp_{category}_*_overlay.md"))
                    if research:
                        research_path = research[0]
                        group["items"].append(
                            {
                                "label": f"Style Research: {research_path.name}",
                                "view": viewer_url(research_path),
                                "raw": raw_url(research_path),
                                "current": research_path.relative_to(ROOT).as_posix(),
                            }
                        )
                    if overlays:
                        overlay_path = overlays[0]
                        group["items"].append(
                            {
                                "label": f"BJCP Overlay: {overlay_path.name}",
                                "view": viewer_url(overlay_path),
                                "raw": raw_url(overlay_path),
                                "current": overlay_path.relative_to(ROOT).as_posix(),
                            }
                        )
                break

    for path in sorted((ROOT / "brewing" / "brew_day_sheets").glob("*.html"), key=lambda p: p.name, reverse=True):
        norm_name = normalize_token(path.stem)
        for group in beer_groups.values():
            if any(candidate in norm_name for candidate in group["candidates"]):
                date_match = re.search(r"_(\d{4}-\d{2}-\d{2})\.html$", path.name)
                label = f"Brew Sheet: {date_match.group(1)}" if date_match else f"Brew Sheet: {file_label(path)}"
                group["items"].append(
                    {
                        "label": label,
                        "view": viewer_url(path),
                        "raw": raw_url(path),
                        "current": path.relative_to(ROOT).as_posix(),
                    }
                )
                break

    for path in sorted((ROOT / "recipes" / "beer_xml_exports").glob("*.xml")):
        norm_name = normalize_token(path.stem)
        for group in beer_groups.values():
            if any(candidate in norm_name for candidate in group["candidates"]):
                group["items"].append(
                    {
                        "label": f"BeerXML: {path.name}",
                        "view": viewer_url(path),
                        "raw": raw_url(path),
                        "current": path.relative_to(ROOT).as_posix(),
                    }
                )
                break

    beer_entries: list[dict[str, str]] = []
    for group_key, group in sorted(beer_groups.items(), key=lambda row: str(row[1]["label"]).lower()):
        brew_sheets = [item for item in group["items"] if item["label"].startswith("Brew Sheet:")]
        other_items = [item for item in group["items"] if not item["label"].startswith("Brew Sheet:")]
        items = [group["primary"], *brew_sheets, *sorted(other_items, key=lambda row: row["label"].lower())]
        beer_entries.append(
            {
                "label": str(group["label"]),
                "view": group["primary"]["view"],
                "raw": group["primary"]["raw"],
                "current": str(group["primary"]["current"]),
                "child_currents": [item["current"] for item in items],
                "children_html": "".join(
                    f'<a class="child-link" data-current="{html.escape(item["current"])}" data-raw="{html.escape(item["raw"])}" href="{html.escape(item["view"])}" target="content">{html.escape(item["label"])}</a>'
                    for item in items
                ),
                "group_id": group_key,
            }
        )
    sections["Beers"] = beer_entries

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
            if label == "Beers":
                active = entry["current"] == current
                active_attr = ' class="active"' if active else ""
                open_attr = " open" if current in entry.get("child_currents", []) else ""
                links.append(
                    f'<details class="beer-group"{open_attr}>'
                    f'<summary><a{active_attr} data-current="{html.escape(entry["current"])}" data-raw="{html.escape(entry["raw"])}" href="{html.escape(entry["view"])}" target="content">{html.escape(entry["label"])}</a></summary>'
                    f'<div class="child-links">{entry.get("children_html", "")}</div>'
                    '</details>'
                )
            else:
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


def service_platform_key() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    return system


def background_service_available() -> bool:
    return service_platform_key() == "macos"


def launch_agent_installed() -> bool:
    if service_platform_key() == "macos":
        return LAUNCH_AGENT_PATH.exists()
    return False


def render_index(default_path: str, notice_text: str = "") -> bytes:
    install_banner = ""
    if background_service_available() and not launch_agent_installed():
        install_banner = (
            '<div class="launcher-banner">'
            '<strong>Background launcher not installed.</strong> '
            'The viewer can run for this session, but installing the launcher makes it automatic next time. '
            f'<a href="{html.escape(operator_url("install-launcher"))}" target="content">Install Background Launcher</a>'
            '</div>'
        )
    elif not background_service_available():
        install_banner = (
            '<div class="launcher-banner">'
            f'<strong>Background launcher backend not implemented for {html.escape(service_platform_key())}.</strong> '
            'The service interface is in place, but this platform still uses session-local startup for now.'
            '</div>'
        )
    notice_html = f'<div class="launcher-success">{html.escape(notice_text)}</div>' if notice_text else ""
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
    .beer-group {{
      border: 1px solid #e6dbc8;
      border-radius: 6px;
      background: #fbf7f0;
      padding: 2px 0;
    }}
    .beer-group summary {{
      list-style: none;
      cursor: pointer;
      padding: 0;
    }}
    .beer-group summary::-webkit-details-marker {{
      display: none;
    }}
    .child-links {{
      display: grid;
      gap: 2px;
      padding: 0 0 6px 12px;
    }}
    .child-link {{
      font-size: 13px;
      color: var(--muted);
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
    .launcher-banner {{
      margin: 0 0 14px;
      padding: 10px 12px;
      border: 1px solid #d6cab8;
      border-radius: 8px;
      background: #fbf6ee;
      color: #4d2a13;
      font-size: 14px;
      line-height: 1.4;
    }}
    .launcher-banner a {{
      color: var(--accent);
      font-weight: 700;
    }}
    .launcher-success {{
      margin: 0 0 14px;
      padding: 10px 12px;
      border: 1px solid #b9d9b9;
      border-radius: 8px;
      background: #edf8ed;
      color: #245224;
      font-size: 14px;
      line-height: 1.4;
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
      <h1><a data-current="{html.escape(default_path)}" data-raw="{html.escape('/raw?path=' + urllib.parse.quote(default_path))}" href="{html.escape('/view?path=' + urllib.parse.quote(default_path))}" target="content">Brew Assistant Viewer</a></h1>
      <p class="sub">Central browser for recipe prints, brew sheets, inventory, profiles, and research.</p>
      {notice_html}
      {install_banner}
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
    const links = Array.from(document.querySelectorAll('aside a[data-current]'));
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
        const group = link.closest('details.beer-group');
        if (group) {{
          const summaryLink = group.querySelector('summary a');
          if (summaryLink === link) {{
            group.open = !group.open;
          }} else {{
            group.open = true;
          }}
        }}
        setActive(link.dataset.current, link.dataset.raw);
      }});
    }}

    setActive({json.dumps(default_path)}, {json.dumps('/raw?path=' + urllib.parse.quote(default_path))});
  </script>
</body>
</html>
""".encode("utf-8")


def render_action_panel(action_html: str) -> str:
    if not action_html:
        return ""
    return f'<div class="action-panel">{action_html}</div>'


def render_notice(notice_text: str) -> str:
    if not notice_text:
        return ""
    return f'<div class="notice-banner">{html.escape(notice_text)}</div>'


def render_text_page(path: Path, body: str, action_html: str = "", notice_text: str = "") -> bytes:
    title = html.escape(path.relative_to(ROOT).as_posix())
    content = f"<pre>{html.escape(body)}</pre>"
    if path.suffix == ".md":
        content = f'<div class="markdown-body">{markdown_to_html(body)}</div>'
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
    .markdown-body {{
      background: #fffdf8;
      border: 1px solid #d6cab8;
      border-radius: 8px;
      padding: 14px 16px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 15px;
      line-height: 1.45;
    }}
    .markdown-body h1, .markdown-body h2, .markdown-body h3 {{
      color: #8a4b24;
      margin: 0.7em 0 0.3em;
      line-height: 1.15;
    }}
    .markdown-body h1:first-child {{
      margin-top: 0;
    }}
    .markdown-body p {{
      margin: 0.45em 0;
    }}
    .markdown-body ul {{
      margin: 0.35em 0 0.45em 1.2em;
      padding: 0;
    }}
    .markdown-body li {{
      margin: 0.18em 0;
    }}
    .markdown-body pre {{
      margin-top: 0.5em;
    }}
    .action-panel {{
      margin: 0 0 16px;
      padding: 12px 14px;
      border: 1px solid #d6cab8;
      border-radius: 8px;
      background: #fcf8f1;
      font-family: Georgia, "Times New Roman", serif;
      position: sticky;
      top: 0;
      z-index: 20;
    }}
    .action-panel h2 {{
      margin: 0 0 8px;
      font-size: 16px;
      color: #8a4b24;
    }}
    .action-panel p {{
      margin: 0 0 10px;
      color: #6a635d;
      font-size: 14px;
      line-height: 1.4;
    }}
    .action-links {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .action-links a {{
      display: inline-block;
      padding: 7px 10px;
      border-radius: 6px;
      border: 1px solid #d6cab8;
      background: #fffdf8;
      color: #4d2a13;
      font-weight: 700;
      font-family: Georgia, "Times New Roman", serif;
    }}
    .notice-banner {{
      margin: 0 0 16px;
      padding: 10px 12px;
      border: 1px solid #b9d9b9;
      border-radius: 8px;
      background: #edf8ed;
      color: #245224;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 15px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <h1>{title}</h1>
      <a href="{html.escape(raw_url(path))}">Raw file</a>
    </div>
    {render_notice(notice_text)}
    {render_action_panel(action_html)}
    {content}
  </div>
</body>
</html>
""".encode("utf-8")


def render_dashboard_page(title: str, body: str, action_html: str = "") -> bytes:
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
    .action-panel {{
      margin: 0 0 16px;
      padding: 12px 14px;
      border: 1px solid #d6cab8;
      border-radius: 8px;
      background: #fcf8f1;
      position: sticky;
      top: 0;
      z-index: 20;
    }}
    .action-panel h2 {{
      margin: 0 0 8px;
      font-size: 16px;
      color: #8a4b24;
    }}
    .action-panel p {{
      margin: 0 0 10px;
      color: #6a635d;
      font-size: 14px;
      line-height: 1.4;
    }}
    .action-links {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .action-links a {{
      display: inline-block;
      padding: 7px 10px;
      border-radius: 6px;
      border: 1px solid #d6cab8;
      background: #fffdf8;
      color: #4d2a13;
      font-weight: 700;
      text-decoration: none;
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
    {render_action_panel(action_html)}
    <pre>{html.escape(body)}</pre>
  </div>
</body>
</html>
""".encode("utf-8")


def render_structured_page(title: str, notes: str, body_html: str, raw_href: str, action_html: str = "", notice_text: str = "") -> bytes:
    notes_html = f'<p class="notes">{html.escape(notes)}</p>' if notes else ""
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
      max-width: 1200px;
      margin: 0 auto;
      padding: 18px 22px 28px;
    }}
    .top {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 12px;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      color: #8a4b24;
    }}
    h2 {{
      margin: 22px 0 8px;
      color: #8a4b24;
      font-size: 18px;
    }}
    .notes {{
      margin: 0 0 16px;
      color: #6a635d;
      font-size: 14px;
      line-height: 1.4;
    }}
    .action-panel {{
      margin: 0 0 16px;
      padding: 12px 14px;
      border: 1px solid #d6cab8;
      border-radius: 8px;
      background: #fcf8f1;
      position: sticky;
      top: 0;
      z-index: 20;
    }}
    .action-panel h2 {{
      margin: 0 0 8px;
      font-size: 16px;
      color: #8a4b24;
    }}
    .action-panel p {{
      margin: 0 0 10px;
      color: #6a635d;
      font-size: 14px;
      line-height: 1.4;
    }}
    .action-links {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .action-links a {{
      display: inline-block;
      padding: 7px 10px;
      border-radius: 6px;
      border: 1px solid #d6cab8;
      background: #fffdf8;
      color: #4d2a13;
      font-weight: 700;
      text-decoration: none;
    }}
    .notice-banner {{
      margin: 0 0 16px;
      padding: 10px 12px;
      border: 1px solid #b9d9b9;
      border-radius: 8px;
      background: #edf8ed;
      color: #245224;
      font-size: 15px;
    }}
    a {{
      color: #8a4b24;
      text-decoration: none;
      font-weight: 700;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #fffdf8;
      border: 1px solid #d6cab8;
      border-radius: 8px;
      overflow: hidden;
      margin-bottom: 14px;
    }}
    th, td {{
      padding: 8px 10px;
      border-bottom: 1px solid #e7dccb;
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      background: #f8f1e5;
    }}
    tbody tr:last-child td {{
      border-bottom: 0;
    }}
    .kv {{
      background: #fffdf8;
      border: 1px solid #d6cab8;
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 12px;
    }}
    .kv-row {{
      display: grid;
      grid-template-columns: 220px 1fr;
      gap: 10px;
      padding: 6px 0;
      border-bottom: 1px solid #eee3d4;
      font-size: 14px;
    }}
    .kv-row:last-child {{
      border-bottom: 0;
    }}
    .kv-key {{
      color: #6a635d;
      font-weight: 700;
    }}
    .muted {{
      color: #6a635d;
    }}
    .yaml-block {{
      background: #fffdf8;
      border: 1px solid #d6cab8;
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 12px;
    }}
    .yaml-line {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 13px;
      line-height: 1.45;
      white-space: pre-wrap;
    }}
    .yaml-comment {{
      color: #8c7b6b;
      font-style: italic;
    }}
    .yaml-key {{
      color: #8a4b24;
      font-weight: 700;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <h1>{html.escape(title)}</h1>
      <a href="{html.escape(raw_href)}">Raw file</a>
    </div>
    {render_notice(notice_text)}
    {render_action_panel(action_html)}
    {notes_html}
    {body_html}
  </div>
</body>
</html>
""".encode("utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_markdown_sections(markdown_text: str) -> tuple[str, dict[str, list[str]]]:
    title = "Recipe"
    current = ""
    sections: dict[str, list[str]] = {}
    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("# "):
            title = line[2:].strip()
            current = ""
            continue
        if line.startswith("## "):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return title, sections


def find_section(sections: dict[str, list[str]], prefix: str) -> list[str]:
    for key, value in sections.items():
        if key.upper().startswith(prefix.upper()):
            return value
    return []


def recipe_usage_for_token(token: str) -> dict | None:
    payload = load_json(RECIPE_USAGE_FILE)
    token_n = normalize_token(token)
    for recipe in payload.get("recipes", []):
        if normalize_token(recipe.get("id", "")) == token_n:
            return recipe
        if normalize_token(recipe.get("display_name", "")) == token_n:
            return recipe
        for alias in recipe.get("aliases", []):
            if normalize_token(alias) == token_n:
                return recipe
    return None


def recipe_usage_for_path(recipe_path: Path) -> dict | None:
    candidates = {normalize_token(value) for value in recipe_stem_candidates(recipe_path.stem)}
    payload = load_json(RECIPE_USAGE_FILE)
    for recipe in payload.get("recipes", []):
        if normalize_token(recipe.get("id", "")) in candidates:
            return recipe
        if normalize_token(recipe.get("display_name", "")) in candidates:
            return recipe
        for alias in recipe.get("aliases", []):
            if normalize_token(alias) in candidates:
                return recipe
    return None


def convert_to_imperial(amount: float, unit: str) -> tuple[float, str]:
    unit_n = unit.lower()
    if unit_n == "g":
        oz = amount / 28.349523125
        if oz >= 16:
            return amount / 453.59237, "lb"
        return oz, "oz"
    if unit_n == "ml":
        return amount / 29.5735295625, "fl oz"
    return amount, unit


def shopping_amount_text(item: dict, shortage: float) -> str:
    category = item.get("category", "")
    unit = item.get("unit", "")
    if unit == "count":
        return f"{math.ceil(shortage)} count"
    if category == "hop" and unit == "g":
        oz = shortage / 28.349523125
        return f"{max(1, math.ceil(oz))} oz"
    value, imperial_unit = convert_to_imperial(shortage, unit)
    if imperial_unit in {"lb", "oz", "fl oz"}:
        return f"{value:.2f} {imperial_unit}"
    return f"{value:.2f} {imperial_unit}"


def recipe_title_for_display(recipe_path: Path) -> str:
    title, sections = parse_markdown_sections(recipe_path.read_text(encoding="utf-8"))
    competition = (
        find_section(sections, "COMPETITION ENTRY")
        or find_section(sections, "COMPETITION TRACKING")
        or find_section(sections, "INTENT")
    )
    for raw in competition:
        stripped = raw.strip()
        if stripped.startswith("- ") and "BJCP Category:" in stripped:
            category = stripped.split("BJCP Category:", 1)[1].strip()
            return f"{re.sub(r'\\s*\\(.*\\)\\s*$', '', title).strip()} - BJCP {category}"
    return re.sub(r"\s*\(.*\)\s*$", "", title).strip()


def parse_weight_to_grams(text: str) -> float | None:
    kg_match = re.search(r"\(([0-9.]+)\s*kg\)", text, flags=re.IGNORECASE)
    if kg_match:
        return float(kg_match.group(1)) * 1000.0
    g_match = re.search(r"\(([0-9.]+)\s*g\)", text, flags=re.IGNORECASE)
    if g_match:
        return float(g_match.group(1))
    lb_match = re.search(r":\s*([0-9.]+)\s*lb\b", text, flags=re.IGNORECASE)
    if lb_match:
        return float(lb_match.group(1)) * 453.59237
    oz_match = re.search(r":\s*([0-9.]+)\s*oz\b", text, flags=re.IGNORECASE)
    if oz_match:
        return float(oz_match.group(1)) * 28.349523125
    return None


def parse_count(text: str) -> float | None:
    count_match = re.search(r":\s*([0-9.]+)\s*(tablet|count|pack)\b", text, flags=re.IGNORECASE)
    if count_match:
        return float(count_match.group(1))
    return None


def stock_item_by_name(name: str) -> dict | None:
    stock = load_json(STOCK_FILE)
    name_n = normalize_token(name)
    name_words = [word for word in re.split(r"[^a-z0-9]+", name.lower()) if word]
    best_exact: dict | None = None
    best_prefix: dict | None = None
    for item in stock.get("items", []):
        item_n = normalize_token(item.get("name", ""))
        item_words = [word for word in re.split(r"[^a-z0-9]+", item.get("name", "").lower()) if word]
        if name_n == item_n:
            best_exact = item
            break
        if item_n.startswith(name_n) or name_n.startswith(item_n):
            if best_prefix is None or len(item_n) < len(normalize_token(best_prefix.get("name", ""))):
                best_prefix = item
            continue
        if name_words and all(word in item_words for word in name_words):
            if best_prefix is None or len(item_words) < len(re.split(r"[^a-z0-9]+", best_prefix.get("name", "").lower())):
                best_prefix = item
    return best_exact or best_prefix


def markdown_recipe_shortages(recipe_path: Path) -> tuple[str, list[dict], list[dict]]:
    title, sections = parse_markdown_sections(recipe_path.read_text(encoding="utf-8"))
    required: list[dict] = []
    optional: list[dict] = []
    seen: set[str] = set()

    def add_row(name: str, buy_amount: str, optional_item: bool = False) -> None:
        key = (name.lower(), buy_amount.lower(), optional_item)
        if str(key) in seen:
            return
        seen.add(str(key))
        row = {"name": name, "buy_amount": buy_amount}
        if optional_item:
            optional.append(row)
        else:
            required.append(row)

    fermentables = find_section(sections, "FERMENTABLES")
    for raw in fermentables:
        stripped = raw.strip()
        if not stripped.startswith("- "):
            continue
        item = stripped[2:].strip()
        name = item.split(":", 1)[0].strip()
        grams = parse_weight_to_grams(item)
        stock_item = stock_item_by_name(name)
        on_hand = float(stock_item.get("on_hand", 0.0)) if stock_item else 0.0
        if grams is None:
            continue
        shortage = grams - on_hand
        if shortage > 1e-6:
            if stock_item:
                add_row(stock_item.get("name", name), shopping_amount_text(stock_item, shortage))
            else:
                add_row(name, shopping_amount_text({"unit": "g", "category": "grain"}, shortage))

    hops = find_section(sections, "HOPS")
    for raw in hops:
        stripped = raw.strip()
        if not stripped.startswith("- "):
            continue
        item = stripped[2:].strip()
        if ":" not in item:
            continue
        body = item.split(":", 1)[1].strip()
        hop_match = re.match(r"([A-Za-z0-9' -]+?)\s+[0-9.]+\s*(oz|g)\b", body)
        if not hop_match:
            continue
        hop_name = hop_match.group(1).strip()
        grams = parse_weight_to_grams(f"X: {body}")
        if grams is None:
            continue
        stock_item = stock_item_by_name(hop_name)
        on_hand = float(stock_item.get("on_hand", 0.0)) if stock_item else 0.0
        shortage = grams - on_hand
        if shortage > 1e-6:
            if stock_item:
                add_row(stock_item.get("name", hop_name), shopping_amount_text(stock_item, shortage))
            else:
                add_row(hop_name, shopping_amount_text({"unit": "g", "category": "hop"}, shortage))

    yeast = find_section(sections, "YEAST")
    for raw in yeast:
        stripped = raw.strip()
        if not stripped.startswith("- "):
            continue
        item = stripped[2:].strip()
        lowered = item.lower()
        if lowered.startswith(("fallback", "pitch target", "target pitch")):
            continue
        if "preferred" not in lowered and "jasper yeast" not in lowered:
            continue
        yeast_name = re.sub(r",.*$", "", item).replace("`", "").strip()
        stock_item = stock_item_by_name(yeast_name)
        on_hand = float(stock_item.get("on_hand", 0.0)) if stock_item else 0.0
        if on_hand < 1.0:
            add_row(yeast_name, "1 count")
        break

    kettle = find_section(sections, "HOPS")
    for raw in kettle:
        stripped = raw.strip()
        if not stripped.startswith("- "):
            continue
        item = stripped[2:].strip()
        if "Whirlfloc:" not in item:
            continue
        count = parse_count(item)
        stock_item = stock_item_by_name("Whirlfloc")
        on_hand = float(stock_item.get("on_hand", 0.0)) if stock_item else 0.0
        if count is not None and count - on_hand > 1e-6:
            if stock_item:
                add_row(stock_item.get("name", "Whirlfloc"), shopping_amount_text(stock_item, count - on_hand))
            else:
                add_row("Whirlfloc", f"{math.ceil(count)} count")

    return recipe_title_for_display(recipe_path) or title, required, optional


def shopping_shortages(recipe_entry: dict) -> tuple[list[dict], list[dict]]:
    stock = load_json(STOCK_FILE)
    by_id = {item["id"]: item for item in stock.get("items", [])}
    required: list[dict] = []
    optional: list[dict] = []
    for line in recipe_entry.get("consumption", []):
        item = by_id.get(line["item_id"])
        if not item:
            continue
        required_amount = float(line["amount"])
        on_hand = float(item.get("on_hand", 0.0))
        shortage = required_amount - on_hand
        if shortage <= 1e-6:
            continue
        row = {
            "name": item["name"],
            "buy_amount": shopping_amount_text(item, shortage),
        }
        if line.get("optional", False):
            optional.append(row)
        else:
            required.append(row)
    return required, optional


def active_recipe_entries() -> list[dict]:
    payload = load_json(ACTIVE_ARTIFACTS_FILE)
    out: list[dict] = []
    seen: set[str] = set()
    for pair in payload.get("active_pairs", []):
        recipe_rel = pair.get("recipe", "")
        recipe_path = ROOT / recipe_rel
        if not recipe_path.exists():
            continue
        recipe_entry = recipe_usage_for_path(recipe_path)
        if recipe_entry and recipe_entry["id"] not in seen:
            seen.add(recipe_entry["id"])
            out.append(recipe_entry)
    return out


def shopping_intent_payload() -> dict:
    if SHOPPING_INTENT_FILE.exists():
        return load_json(SHOPPING_INTENT_FILE)
    return {}


def planned_recipe_entries() -> list[tuple[dict, str, str]]:
    payload = shopping_intent_payload()
    out: list[tuple[dict, str, str]] = []
    for row in payload.get("recipe_queue", []):
        recipe_id = row.get("recipe_id", "")
        recipe_entry = recipe_usage_for_token(recipe_id)
        if recipe_entry:
            out.append((recipe_entry, row.get("horizon", ""), row.get("note", "")))
            continue
        recipe_path = resolve_recipe_markdown(recipe_id)
        if recipe_path:
            out.append(({"id": recipe_id, "display_name": recipe_title_for_display(recipe_path), "recipe_path": recipe_path.relative_to(ROOT).as_posix()}, row.get("horizon", ""), row.get("note", "")))
    return out


def render_shopping_page(recipe_token: str) -> tuple[bytes, str]:
    planned = planned_recipe_entries()
    if recipe_token:
        recipe_entry = recipe_usage_for_token(recipe_token)
        if recipe_entry:
            entries = [(recipe_entry, "", "")]
        else:
            recipe_path = resolve_recipe_markdown(recipe_token)
            entries = [({"id": recipe_token, "display_name": recipe_title_for_display(recipe_path), "recipe_path": recipe_path.relative_to(ROOT).as_posix()}, "", "")] if recipe_path else []
    else:
        entries = planned
    sections: list[str] = []
    raw_lines: list[str] = []
    for entry, horizon, note in entries:
        recipe_path = entry.get("recipe_path")
        if recipe_path:
            heading, required, optional = markdown_recipe_shortages(ROOT / recipe_path)
        else:
            required, optional = shopping_shortages(entry)
            heading = entry["display_name"]
        if horizon:
            heading = f"{heading} ({horizon})"
        raw_lines.append(heading)
        if not required and not optional:
            note_html = f'<p class="notes">{html.escape(note)}</p>' if note else ""
            sections.append(f"<section><h2>{html.escape(heading)}</h2>{note_html}<p class=\"notes\">No shortages.</p></section>")
            raw_lines.append("  No shortages.")
            continue
        blocks: list[str] = []
        if note:
            blocks.append(f'<p class="notes">{html.escape(note)}</p>')
        if required:
            rows = "".join(
                f"<tr><td>{html.escape(row['name'])}</td><td>{html.escape(row['buy_amount'])}</td></tr>"
                for row in required
            )
            blocks.append("<h3>Required</h3><table><thead><tr><th>Item</th><th>Buy</th></tr></thead><tbody>" + rows + "</tbody></table>")
            raw_lines.extend([f"  {row['name']}: {row['buy_amount']}" for row in required])
        if optional:
            rows = "".join(
                f"<tr><td>{html.escape(row['name'])}</td><td>{html.escape(row['buy_amount'])}</td></tr>"
                for row in optional
            )
            blocks.append("<h3>Optional / situational</h3><table><thead><tr><th>Item</th><th>Buy</th></tr></thead><tbody>" + rows + "</tbody></table>")
            raw_lines.extend([f"  Optional {row['name']}: {row['buy_amount']}" for row in optional])
        sections.append(f"<section><h2>{html.escape(heading)}</h2>{''.join(blocks)}</section>")

    if not recipe_token:
        intent = shopping_intent_payload()
        equipment_rows = intent.get("equipment_wishlist", [])
        research_rows = intent.get("research_queue", [])
        if equipment_rows:
            rows = "".join(
                f"<tr><td>{html.escape(row.get('item', ''))}</td><td>{html.escape(row.get('priority', ''))}</td><td>{html.escape(row.get('note', ''))}</td></tr>"
                for row in equipment_rows
            )
            sections.append("<section><h2>Equipment Wishlist</h2><table><thead><tr><th>Item</th><th>Priority</th><th>Note</th></tr></thead><tbody>" + rows + "</tbody></table></section>")
            raw_lines.append("Equipment Wishlist")
            raw_lines.extend([f"  {row.get('item', '')}: {row.get('priority', '')} | {row.get('note', '')}".rstrip(" |") for row in equipment_rows])
        if research_rows:
            rows = "".join(
                f"<tr><td>{html.escape(row.get('topic', ''))}</td><td>{html.escape(row.get('priority', ''))}</td><td>{html.escape(row.get('note', ''))}</td></tr>"
                for row in research_rows
            )
            sections.append("<section><h2>Research Queue</h2><table><thead><tr><th>Topic</th><th>Priority</th><th>Note</th></tr></thead><tbody>" + rows + "</tbody></table></section>")
            raw_lines.append("Research Queue")
            raw_lines.extend([f"  {row.get('topic', '')}: {row.get('priority', '')} | {row.get('note', '')}".rstrip(" |") for row in research_rows])

    title = "Shopping - Planned Recipes" if not recipe_token else f"Shopping - {entries[0][0]['display_name'] if entries else recipe_token}"
    body = "".join(sections) if sections else '<p class="notes">No planned shopping needs found.</p>'
    raw_href = f"/shopping?recipe={urllib.parse.quote(recipe_token)}&raw=1" if recipe_token else "/shopping?raw=1"
    page = render_structured_page(title, "Shopping intent drives the default view. Shortage-only, imperial-facing recipe lists plus wishlist/research reminders.", body, raw_href)
    raw_text = "\n".join(raw_lines) or "No shopping needs."
    return page, raw_text


def render_json_value(value: object) -> str:
    if isinstance(value, dict):
        rows = []
        for key, child in value.items():
            rows.append(
                '<div class="kv-row">'
                f'<div class="kv-key">{html.escape(str(key))}</div>'
                f'<div>{render_json_value(child)}</div>'
                '</div>'
            )
        return f'<div class="kv">{"".join(rows)}</div>'
    if isinstance(value, list):
        if not value:
            return '<span class="muted">[]</span>'
        items = "".join(f"<li>{render_json_value(child)}</li>" for child in value)
        return f"<ul>{items}</ul>"
    return html.escape(str(value))


def render_stock_page(path: Path) -> bytes:
    payload = json.loads(path.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in payload.get("items", []):
        grouped[item.get("category", "other").title()].append(item)

    sections: list[str] = []
    for category in sorted(grouped):
        rows: list[str] = []
        for item in sorted(grouped[category], key=lambda row: row.get("name", "").lower()):
            qty = item.get("on_hand", 0)
            unit = item.get("unit", "")
            qty_text = f"{float(qty):.2f} {unit}".strip()
            extras: list[str] = []
            if item.get("alpha_acid_pct") is not None:
                extras.append(f"AA {float(item['alpha_acid_pct']):.1f}%")
            tags = item.get("tags", [])
            if tags:
                extras.append(", ".join(tags))
            meta = " | ".join(extras)
            rows.append(
                "<tr>"
                f"<td>{html.escape(item.get('name', ''))}</td>"
                f"<td>{html.escape(qty_text)}</td>"
                f"<td>{html.escape(meta)}</td>"
                "</tr>"
            )
        sections.append(
            f"<section><h2>{html.escape(category)}</h2>"
            "<table><thead><tr><th>Item</th><th>On Hand</th><th>Notes</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></section>"
        )

    title = html.escape(path.relative_to(ROOT).as_posix())
    return render_structured_page("Inventory Stock", payload.get("notes", ""), "".join(sections), raw_url(path))


def render_json_page(path: Path) -> bytes:
    payload = json.loads(path.read_text(encoding="utf-8"))
    notes = payload.get("notes", "") if isinstance(payload, dict) else ""
    body = render_json_value(payload)
    return render_structured_page(path.relative_to(ROOT).as_posix(), notes, body, raw_url(path))


def render_yaml_page(path: Path) -> bytes:
    general_rows: list[str] = []
    sections: list[tuple[str, list[str], list[str]]] = []
    current_title = "Details"
    current_rows: list[str] = []
    current_notes: list[str] = []

    def flush_section() -> None:
        nonlocal current_title, current_rows, current_notes
        if current_rows or current_notes:
            sections.append((current_title, current_rows[:], current_notes[:]))
        current_rows = []
        current_notes = []

    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()

        if stripped.startswith("#"):
            note = f'<div class="yaml-line yaml-comment">{html.escape(stripped)}</div>'
            if sections or current_rows:
                current_notes.append(note)
            else:
                general_rows.append(note)
            continue

        if indent == 0 and ":" in stripped and not stripped.startswith("- "):
            key, rest = stripped.split(":", 1)
            key = key.strip()
            rest = rest.strip()
            if not rest:
                flush_section()
                current_title = key.replace("_", " ").title()
                continue
            general_rows.append(
                '<div class="kv-row">'
                f'<div class="kv-key">{html.escape(key)}</div>'
                f'<div>{html.escape(rest)}</div>'
                '</div>'
            )
            continue

        if ":" in stripped and not stripped.startswith("- "):
            key, rest = stripped.split(":", 1)
            current_rows.append(
                '<div class="kv-row">'
                f'<div class="kv-key">{html.escape(key.strip())}</div>'
                f'<div>{html.escape(rest.strip())}</div>'
                '</div>'
            )
            continue

        current_rows.append(f'<div class="yaml-line">{html.escape(stripped)}</div>')

    flush_section()

    blocks: list[str] = []
    if general_rows:
        blocks.append(f'<div class="kv">{"".join(general_rows)}</div>')
    for title, rows, notes in sections:
        blocks.append(f"<section><h2>{html.escape(title)}</h2>")
        if notes:
            blocks.append(f'<div class="yaml-block">{"".join(notes)}</div>')
        if rows:
            blocks.append(f'<div class="kv">{"".join(rows)}</div>')
        blocks.append("</section>")
    body = "".join(blocks) if blocks else '<div class="muted">No YAML content</div>'
    return render_structured_page(path.relative_to(ROOT).as_posix(), "", body, raw_url(path))


def dashboard_output(mode: str) -> str:
    cmd = ["python3", "tools/batch_state_summary.py"]
    if mode == "next":
        cmd.append("--with-next-actions")
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)
    return proc.stdout


def active_pairs_payload() -> list[dict]:
    if ACTIVE_ARTIFACTS_FILE.exists():
        return load_json(ACTIVE_ARTIFACTS_FILE).get("active_pairs", [])
    return []


def brew_history_events() -> list[dict]:
    history_file = ROOT / "libraries" / "inventory" / "brew_history.json"
    if history_file.exists():
        return load_json(history_file).get("events", [])
    return []


def canonical_recipe_token(recipe_path: Path) -> str:
    recipe_entry = recipe_usage_for_path(recipe_path)
    if recipe_entry:
        return recipe_entry["id"]
    return recipe_stem_candidates(recipe_path.stem)[-1]


def resolve_recipe_context_from_path(path: Path) -> tuple[str, Path] | None:
    if path.suffix == ".md" and "recipes" in path.parts:
        return canonical_recipe_token(path), path
    if path.suffix == ".html" and path.parent == ROOT / "recipes" / "html_exports":
        recipe_path = resolve_recipe_markdown(path.stem)
        if recipe_path:
            return canonical_recipe_token(recipe_path), recipe_path
    if path.suffix == ".html" and path.parent == ROOT / "brewing" / "brew_day_sheets":
        stem = re.sub(r"_brew_day_sheet(?:_\d{4}-\d{2}-\d{2})?$", "", path.stem)
        recipe_path = resolve_recipe_markdown(stem)
        if recipe_path:
            return canonical_recipe_token(recipe_path), recipe_path
    return None


def recipe_state(recipe_token: str, recipe_path: Path) -> dict[str, str]:
    brew_sheet_date = ""
    brew_sheet_rel = ""
    for pair in active_pairs_payload():
        pair_recipe = ROOT / pair.get("recipe", "")
        if pair_recipe.resolve() == recipe_path.resolve():
            match = re.search(r"_(\d{4}-\d{2}-\d{2})\.html$", pair.get("brew_sheet", ""))
            brew_sheet_date = match.group(1) if match else ""
            brew_sheet_rel = pair.get("brew_sheet", "")
            break
    events = brew_history_events()
    brew_events = [event for event in events if event.get("type") == "brew" and normalize_token(event.get("recipe_id", "")) == normalize_token(recipe_token)]
    package_events = [event for event in events if event.get("type") == "package" and normalize_token(event.get("recipe_id", "")) == normalize_token(recipe_token)]
    if brew_events:
        latest_brew = max(brew_events, key=lambda row: row.get("brew_date", ""))
        latest_brew_date = latest_brew.get("brew_date", "")
        packaged = any(event.get("brew_date", "") == latest_brew_date for event in package_events)
        if not packaged:
            return {"state": "brewed_not_packaged", "brew_date": latest_brew_date, "brew_sheet": latest_brew.get("brew_sheet", brew_sheet_rel)}
    if brew_sheet_date:
        return {"state": "prepared_not_brewed", "brew_date": brew_sheet_date, "brew_sheet": brew_sheet_rel}
    return {"state": "recipe_ready", "brew_date": "", "brew_sheet": ""}


def next_action_text_for_recipe(recipe_token: str, recipe_path: Path) -> str:
    state = recipe_state(recipe_token, recipe_path)
    if state["state"] == "brewed_not_packaged":
        return f"Ready to package. Last un-packaged batch was brewed {state['brew_date']}."
    if state["state"] == "prepared_not_brewed":
        return f"Ready to register brew for the dated sheet {state['brew_date']}."
    return f"Next likely action: prepare {recipe_token} when ready to brew."


def package_form_url(recipe: str, brew_date: str = "") -> str:
    query = {"recipe": recipe}
    if brew_date:
        query["brew_date"] = brew_date
    return "/package-form?" + urllib.parse.urlencode(query)


def render_package_form(recipe_token: str, brew_date: str) -> bytes:
    default_date = __import__("datetime").date.today().isoformat()
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Package {html.escape(recipe_token)}</title>
  <style>
    body {{ margin: 0; background: #f5efe5; color: #1d1a18; font-family: Georgia, "Times New Roman", serif; }}
    .wrap {{ max-width: 760px; margin: 0 auto; padding: 18px 22px 28px; }}
    h1 {{ margin: 0 0 10px; color: #8a4b24; font-size: 28px; }}
    p {{ color: #6a635d; }}
    form {{ background: #fffdf8; border: 1px solid #d6cab8; border-radius: 10px; padding: 16px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; align-items: start; }}
    label {{ display: block; font-size: 14px; color: #4d2a13; font-weight: 700; margin-bottom: 4px; }}
    input, select {{ width: 100%; padding: 8px 9px; border: 1px solid #d6cab8; border-radius: 6px; background: #fff; }}
    .hint {{ margin-top: 4px; color: #6a635d; font-size: 13px; }}
    .full {{ grid-column: 1 / -1; }}
    .actions {{ margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; }}
    button, a.button {{ display: inline-block; padding: 8px 11px; border-radius: 6px; border: 1px solid #d6cab8; background: #fffdf8; color: #4d2a13; text-decoration: none; font-weight: 700; }}
    @media (max-width: 700px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Register Package</h1>
    <p>Complete the packaging details for <strong>{html.escape(recipe_token)}</strong>.</p>
    <form method="get" action="/operate">
      <input type="hidden" name="action" value="package">
      <input type="hidden" name="recipe" value="{html.escape(recipe_token)}">
      <div class="grid">
        <div>
          <label for="brew_date">Brew Date</label>
          <input id="brew_date" name="brew_date" type="date" value="{html.escape(brew_date)}" required>
        </div>
        <div>
          <label for="package_date">Package Date</label>
          <input id="package_date" name="package_date" type="date" value="{html.escape(default_date)}" required>
        </div>
        <div>
          <label for="fg">FG</label>
          <input id="fg" name="fg" placeholder="1.013" required>
        </div>
        <div>
          <label for="packaged_volume">Packaged Volume</label>
          <input id="packaged_volume" name="packaged_volume" placeholder="5.00" required>
        </div>
        <div>
          <label for="packaged_volume_unit">Volume Unit</label>
          <select id="packaged_volume_unit" name="packaged_volume_unit" required>
            <option value="gal" selected>Gallons</option>
            <option value="l">Liters</option>
          </select>
        </div>
        <div>
          <label for="harvest_yeast">Harvest Yeast</label>
          <input id="harvest_yeast" name="harvest_yeast" placeholder="1968 or wlp007">
        </div>
        <div>
          <label for="harvest_generation">Harvest Generation</label>
          <input id="harvest_generation" name="harvest_generation" placeholder="2">
        </div>
        <div>
          <label for="co2_vols">CO2 Vols</label>
          <input id="co2_vols" name="co2_vols" placeholder="2.4">
          <div class="hint">Optional. Leave blank to keep the recipe or brew-sheet target.</div>
        </div>
      </div>
      <div class="actions">
        <button type="submit">Register Package</button>
        <a class="button" href="{html.escape(operator_url('status', recipe=recipe_token))}">Cancel</a>
      </div>
    </form>
  </div>
</body>
</html>
""".encode("utf-8")


def action_panel_html(recipe_token: str, recipe_path: Path, current_rel: str = "") -> str:
    state = recipe_state(recipe_token, recipe_path)
    refresh_params = {"recipe": recipe_token}
    if current_rel:
        refresh_params["return_path"] = current_rel
    trust_params = {}
    if current_rel:
        trust_params["return_path"] = current_rel
    links = [f'<a href="{html.escape(operator_url("status", recipe=recipe_token))}" target="content">Next Action</a>']
    if state["state"] == "brewed_not_packaged":
        links.append(f'<a href="{html.escape(package_form_url(recipe_token, state["brew_date"]))}" target="content">Register Package</a>')
    elif state["state"] == "prepared_not_brewed":
        links.append(f'<a href="{html.escape(operator_url("brew", recipe=recipe_token, date=state["brew_date"]))}" target="content">Register Brew</a>')
    else:
        links.append(f'<a href="{html.escape(operator_url("prepare", recipe=recipe_token, date="today", run_trust_check="1"))}" target="content">Prepare Today</a>')
    links.extend([
        f'<a href="{html.escape(operator_url("refresh-html", **refresh_params))}" target="content">Refresh Print</a>',
        f'<a href="{html.escape(operator_url("trust-check", **trust_params))}" target="content">Run Trust Check</a>',
    ])
    return (
        "<h2>Actions</h2>"
        f"<p>{html.escape(next_action_text_for_recipe(recipe_token, recipe_path))}</p>"
        f'<div class="action-links">{"".join(links)}</div>'
    )


def render_html_wrapper(path: Path, action_html: str = "", notice_text: str = "") -> bytes:
    title = path.relative_to(ROOT).as_posix()
    src = raw_url(path)
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
      max-width: 1200px;
      margin: 0 auto;
      padding: 18px 22px 28px;
    }}
    .top {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 12px;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      color: #8a4b24;
    }}
    a {{
      color: #8a4b24;
      text-decoration: none;
      font-weight: 700;
    }}
    .action-panel {{
      margin: 0 0 16px;
      padding: 12px 14px;
      border: 1px solid #d6cab8;
      border-radius: 8px;
      background: #fcf8f1;
      position: sticky;
      top: 0;
      z-index: 20;
    }}
    .action-panel h2 {{
      margin: 0 0 8px;
      font-size: 16px;
      color: #8a4b24;
    }}
    .action-panel p {{
      margin: 0 0 10px;
      color: #6a635d;
      font-size: 14px;
      line-height: 1.4;
    }}
    .action-links {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .action-links a {{
      display: inline-block;
      padding: 7px 10px;
      border-radius: 6px;
      border: 1px solid #d6cab8;
      background: #fffdf8;
      color: #4d2a13;
      text-decoration: none;
      font-weight: 700;
    }}
    .notice-banner {{
      margin: 0 0 16px;
      padding: 10px 12px;
      border: 1px solid #b9d9b9;
      border-radius: 8px;
      background: #edf8ed;
      color: #245224;
      font-size: 15px;
    }}
    iframe {{
      width: 100%;
      height: 1200px;
      border: 1px solid #d6cab8;
      border-radius: 8px;
      background: white;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <h1>{html.escape(title)}</h1>
      <a href="{html.escape(src)}">Raw file</a>
    </div>
    {render_notice(notice_text)}
    {render_action_panel(action_html)}
    <iframe src="{html.escape(src)}"></iframe>
  </div>
</body>
</html>
""".encode("utf-8")


def operate_output(action: str, params: dict[str, str]) -> tuple[str, bool]:
    if action == "install-launcher":
        proc = subprocess.run(["python3", "tools/web_ui_service.py", "install"], cwd=ROOT, capture_output=True, text=True)
        return proc.stdout + proc.stderr, proc.returncode == 0
    if action == "trust-check":
        proc = subprocess.run(["make", "trust-check"], cwd=ROOT, capture_output=True, text=True)
        return proc.stdout + proc.stderr, proc.returncode == 0
    if action == "refresh-html":
        recipe = params.get("recipe", "")
        proc = subprocess.run(["python3", "tools/refresh_recipe_html.py", "--recipe", recipe], cwd=ROOT, capture_output=True, text=True)
        return proc.stdout + proc.stderr, proc.returncode == 0
    if action == "package":
        cmd = [
            "python3", "tools/register_package.py",
            "--recipe", params.get("recipe", ""),
            "--brew-date", params.get("brew_date", ""),
            "--package-date", params.get("package_date", ""),
            "--fg", params.get("fg", ""),
            "--packaged-volume", params.get("packaged_volume", ""),
            "--packaged-volume-unit", params.get("packaged_volume_unit", "gal"),
        ]
        if params.get("co2_vols"):
            cmd.extend(["--co2-vols", params["co2_vols"]])
        if params.get("harvest_yeast"):
            cmd.extend(["--harvest-yeast", params["harvest_yeast"]])
        if params.get("harvest_generation"):
            cmd.extend(["--harvest-generation", params["harvest_generation"]])
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        refresh_lines = []
        if proc.returncode == 0 and params.get("recipe"):
            refresh = subprocess.run(["python3", "tools/refresh_recipe_html.py", "--recipe", params["recipe"]], cwd=ROOT, capture_output=True, text=True)
            refresh_lines.append(refresh.stdout + refresh.stderr)
        status = subprocess.run(["python3", "tools/batch_state_summary.py", "--with-next-actions"], cwd=ROOT, capture_output=True, text=True)
        payload = proc.stdout + proc.stderr
        if refresh_lines:
            payload += "\n" + "\n".join(refresh_lines)
        payload += "\n" + status.stdout + status.stderr
        return payload, proc.returncode == 0
    cmd = ["python3", "tools/brew_op.py", "--action", action]
    if params.get("recipe"):
        cmd.extend(["--recipe", params["recipe"]])
    if params.get("date"):
        cmd.extend(["--date", params["date"]])
    if params.get("run_trust_check"):
        cmd.append("--run-trust-check")
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    refresh_lines = []
    if proc.returncode == 0 and params.get("recipe"):
        refresh = subprocess.run(["python3", "tools/refresh_recipe_html.py", "--recipe", params["recipe"]], cwd=ROOT, capture_output=True, text=True)
        refresh_lines.append(refresh.stdout + refresh.stderr)
    status = subprocess.run(["python3", "tools/batch_state_summary.py", "--with-next-actions"], cwd=ROOT, capture_output=True, text=True)
    payload = proc.stdout + proc.stderr
    if refresh_lines:
        payload += "\n" + "\n".join(refresh_lines)
    payload += "\n" + status.stdout + status.stderr
    return payload, proc.returncode == 0


def render_view_response(path: Path, notice_text: str = "") -> bytes:
    if path == STOCK_FILE.resolve():
        return render_stock_page(path)
    if path.suffix == ".json":
        return render_json_page(path)
    if path.suffix in {".yaml", ".yml"}:
        return render_yaml_page(path)
    context = resolve_recipe_context_from_path(path)
    action_html = ""
    if context:
        recipe_token, recipe_path = context
        action_html = action_panel_html(recipe_token, recipe_path, path.relative_to(ROOT).as_posix())
    if path.suffix == ".html":
        return render_html_wrapper(path, action_html, notice_text)
    body = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        body = json.dumps(json.loads(body), indent=2)
    return render_text_page(path, body, action_html, notice_text)


class BrewUIHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/":
            default_rel = DEFAULT_FILE.relative_to(ROOT).as_posix()
            self.respond_bytes(200, "text/html; charset=utf-8", render_index(default_rel))
            return

        if parsed.path == "/shopping":
            recipe_token = params.get("recipe", [""])[0]
            page, raw_text = render_shopping_page(recipe_token)
            if params.get("raw", ["0"])[0] == "1":
                self.respond_bytes(200, "text/plain; charset=utf-8", raw_text.encode("utf-8"))
                return
            self.respond_bytes(200, "text/html; charset=utf-8", page)
            return

        if parsed.path == "/package-form":
            recipe_token = params.get("recipe", [""])[0]
            brew_date = params.get("brew_date", [""])[0]
            if not recipe_token:
                self.respond_text(400, "Missing recipe.")
                return
            self.respond_bytes(200, "text/html; charset=utf-8", render_package_form(recipe_token, brew_date))
            return

        if parsed.path == "/operate":
            action = params.get("action", [""])[0]
            if not action:
                self.respond_text(400, "Missing action.")
                return
            flat_params = {key: values[0] for key, values in params.items() if values}
            payload, ok = operate_output(action, flat_params)
            if action == "install-launcher":
                default_rel = DEFAULT_FILE.relative_to(ROOT).as_posix()
                notice = "Background launcher installed." if ok else "Background launcher install failed."
                self.respond_bytes(200, "text/html; charset=utf-8", render_index(default_rel, notice))
                return
            if action == "refresh-html" and ok and flat_params.get("return_path"):
                try:
                    path = ensure_allowed(ROOT / flat_params["return_path"])
                except ValueError:
                    self.respond_text(403, "Path not allowed.")
                    return
                if not path.exists() or not path.is_file():
                    self.respond_text(404, "File not found.")
                    return
                recipe_label = flat_params.get("recipe", "").replace("_", " ").title()
                notice = f"Recipe Print Refresh Successful for {recipe_label}"
                self.respond_bytes(200, "text/html; charset=utf-8", render_view_response(path, notice))
                return
            if action == "trust-check" and flat_params.get("return_path"):
                try:
                    path = ensure_allowed(ROOT / flat_params["return_path"])
                except ValueError:
                    self.respond_text(403, "Path not allowed.")
                    return
                if not path.exists() or not path.is_file():
                    self.respond_text(404, "File not found.")
                    return
                notice = "Trust Check Passed" if ok else "Trust Check Failed"
                self.respond_bytes(200, "text/html; charset=utf-8", render_view_response(path, notice))
                return
            title = f"Operation - {action}"
            action_html = ""
            recipe_token = flat_params.get("recipe", "")
            if recipe_token:
                recipe_path = resolve_recipe_markdown(recipe_token)
                if recipe_path:
                    action_html = action_panel_html(canonical_recipe_token(recipe_path), recipe_path)
            page = render_dashboard_page(title, payload or ("OK" if ok else "No output"), action_html)
            self.respond_bytes(200, "text/html; charset=utf-8", page)
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

            if path == STOCK_FILE.resolve():
                self.respond_bytes(200, "text/html; charset=utf-8", render_stock_page(path))
                return

            if path.suffix == ".json":
                self.respond_bytes(200, "text/html; charset=utf-8", render_json_page(path))
                return

            if path.suffix in {".yaml", ".yml"}:
                self.respond_bytes(200, "text/html; charset=utf-8", render_yaml_page(path))
                return

            self.respond_bytes(200, "text/html; charset=utf-8", render_view_response(path))
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
    parser.add_argument("--reload", action="store_true", help="Auto-restart the server when web_ui.py changes")
    return parser


def start_reload_watcher(server: ThreadingHTTPServer, source_path: Path) -> threading.Event:
    restart_requested = threading.Event()
    initial_mtime = source_path.stat().st_mtime_ns

    def watch() -> None:
        last_mtime = initial_mtime
        while not restart_requested.is_set():
            time.sleep(1.0)
            try:
                current_mtime = source_path.stat().st_mtime_ns
            except FileNotFoundError:
                continue
            if current_mtime != last_mtime:
                restart_requested.set()
                server.shutdown()
                return

    threading.Thread(target=watch, name="brew-ui-reload-watch", daemon=True).start()
    return restart_requested


def main() -> int:
    args = build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), BrewUIHandler)
    restart_requested: threading.Event | None = None
    if args.reload:
        restart_requested = start_reload_watcher(server, WEB_UI_SOURCE)
    print(f"BREW_UI_OK http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    if restart_requested and restart_requested.is_set():
        os.execv(sys.executable, [sys.executable, str(WEB_UI_SOURCE), *sys.argv[1:]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
