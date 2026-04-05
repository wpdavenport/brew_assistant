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
import random
import re
import subprocess
import sys
import threading
import time
import urllib.parse
from collections import defaultdict
from copy import deepcopy
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
    "BJCP Study": [
        ROOT / "libraries" / "bjcp_study" / "_index.md",
        ROOT / "libraries" / "bjcp_study" / "curriculum.md",
        ROOT / "libraries" / "bjcp_study" / "rubrics.md",
        ROOT / "libraries" / "bjcp_study" / "progress_template.json",
        ROOT / "libraries" / "bjcp_study" / "question_bank.json",
    ],
}

DEFAULT_FILE = ROOT / "README.md"
BEER_RESEARCH_DIR = ROOT / "libraries" / "beer_research"
BJCP_OVERLAYS_DIR = ROOT / "libraries" / "bjcp_overlays"
STOCK_FILE = ROOT / "libraries" / "inventory" / "stock.json"
RECIPE_USAGE_FILE = ROOT / "libraries" / "inventory" / "recipe_usage.json"
ACTIVE_ARTIFACTS_FILE = ROOT / "project_control" / "ACTIVE_ARTIFACTS.json"
SHOPPING_INTENT_FILE = ROOT / "libraries" / "inventory" / "shopping_intent.json"
BJCP_STUDY_DIR = ROOT / "libraries" / "bjcp_study"
BJCP_PROGRESS_TEMPLATE_FILE = BJCP_STUDY_DIR / "progress_template.json"
BJCP_PROGRESS_FILE = BJCP_STUDY_DIR / "progress.json"
BJCP_QUESTION_BANK_FILE = BJCP_STUDY_DIR / "question_bank.json"
WEB_UI_SOURCE = Path(__file__).resolve()
LAUNCH_AGENT_LABEL = "com.serenity.brewassistant.webui"
LAUNCH_AGENT_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
RNG = random.SystemRandom()


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


def study_item(label: str = "Study Overview") -> dict[str, str]:
    return {
        "label": label,
        "view": "/study",
        "raw": "/study?raw=1",
        "current": "study:overview",
    }


def study_test_item(label: str = "Mini Test") -> dict[str, str]:
    return {
        "label": label,
        "view": "/study/test",
        "raw": "/study/test?raw=1",
        "current": "study:test",
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
            dashboard_item("Fermentation", "fermentation"),
            shopping_item("Shopping"),
            study_item("BJCP Study"),
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
                    f'<a class="child-link" data-current="{html.escape(item["current"])}" href="{html.escape(item["view"])}" target="content">{html.escape(item["label"])}</a>'
                    for item in items
                ),
                "group_id": group_key,
            }
        )
    sections["Beers"] = beer_entries

    for label, entries in CURATED_SECTIONS.items():
        section_entries: list[dict[str, str]] = []
        if label == "BJCP Study":
            study_children = [study_item("Study Overview"), study_test_item("Mini Test")]
            for path in entries:
                if not path.exists():
                    continue
                rel = path.relative_to(ROOT).as_posix()
                study_children.append(
                    {
                        "label": file_label(path),
                        "view": viewer_url(path),
                        "raw": raw_url(path),
                        "current": rel,
                    }
                )
            section_entries.extend(study_children)
            sections[label] = section_entries
            continue
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
            if label in {"Beers", "BJCP Study"} and entry.get("children_html"):
                active = entry["current"] == current
                active_attr = ' class="active"' if active else ""
                open_attr = " open" if current in entry.get("child_currents", []) else ""
                links.append(
                    f'<details class="beer-group"{open_attr}>'
                    f'<summary><a{active_attr} data-current="{html.escape(entry["current"])}" href="{html.escape(entry["view"])}" target="content">{html.escape(entry["label"])}</a></summary>'
                    f'<div class="child-links">{entry.get("children_html", "")}</div>'
                    '</details>'
                )
            else:
                active = ' class="active"' if entry["current"] == current else ""
                links.append(
                    f'<a{active} data-current="{html.escape(entry["current"])}" href="{html.escape(entry["view"])}" target="content">{html.escape(entry["label"])}</a>'
                )
        if not links:
            links.append('<span class="empty">No files yet</span>')
        section_open = ' open' if label == "Operations" else ""
        blocks.append(
            f'<details class="nav-section"{section_open}>'
            f'<summary><h2>{html.escape(label)}</h2></summary>'
            f'<div class="nav-group">{"".join(links)}</div>'
            f'</details>'
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
    .nav-section {{
      margin-bottom: 18px;
    }}
    .nav-section summary {{
      list-style: none;
      cursor: pointer;
    }}
    .nav-section summary::-webkit-details-marker {{
      display: none;
    }}
    h2 {{
      margin: 0 0 8px;
      padding-bottom: 4px;
      border-bottom: 1px solid var(--rule);
      font-size: 13px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .nav-section summary h2 {{
      margin-bottom: 8px;
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
    .toolbar a, .toolbar button {{
      color: var(--accent);
      font-weight: 700;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 14px;
      background: transparent;
      border: 0;
      padding: 0;
      cursor: pointer;
    }}
    .toolbar-actions {{
      display: flex;
      gap: 12px;
      align-items: center;
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
    @media print {{
      body {{
        background: white;
      }}
      aside,
      .toolbar {{
        display: none !important;
      }}
      .app {{
        display: block;
      }}
      main {{
        background: white;
      }}
      iframe {{
        height: auto;
      }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <h1><a data-current="{html.escape(default_path)}" href="{html.escape('/view?path=' + urllib.parse.quote(default_path))}" target="content">Brew Assistant Viewer</a></h1>
      <p class="sub">Central browser for recipe prints, brew sheets, inventory, profiles, and research.</p>
      {notice_html}
      {install_banner}
      {render_nav(default_path)}
    </aside>
    <main>
      <div class="toolbar">
        <span class="hint">Local viewer. Print from the content pane when needed.</span>
        <div class="toolbar-actions">
          <button type="button" id="print-current">Print Current Page</button>
        </div>
      </div>
      <iframe id="content-frame" name="content" src="{html.escape('/view?path=' + urllib.parse.quote(default_path))}"></iframe>
    </main>
  </div>
  <script>
    const links = Array.from(document.querySelectorAll('aside a[data-current]'));
    const frame = document.getElementById('content-frame');
    const printButton = document.getElementById('print-current');

    function setActive(current) {{
      for (const link of links) {{
        link.classList.toggle('active', link.dataset.current === current);
      }}
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
        setActive(link.dataset.current);
      }});
    }}

    setActive({json.dumps(default_path)});

    printButton.addEventListener('click', () => {{
      const outerWindow = frame.contentWindow;
      const nestedFrame = outerWindow.document.querySelector('iframe');
      const targetWindow = nestedFrame ? nestedFrame.contentWindow : outerWindow;
      targetWindow.focus();
      targetWindow.print();
    }});
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


def render_warning(notice_text: str) -> str:
    if not notice_text:
        return ""
    return f'<div class="notice-banner warning">{html.escape(notice_text)}</div>'


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
    @media print {{
      .top,
      .action-panel,
      .notice-banner {{
        display: none !important;
      }}
      .wrap {{
        max-width: none;
        padding: 0;
      }}
      pre,
      .markdown-body {{
        border: 0;
        border-radius: 0;
        padding: 0;
      }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <h1>{title}</h1>
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
    .action-links button {{
      display: inline-block;
      padding: 7px 10px;
      border-radius: 6px;
      border: 1px solid #d6cab8;
      background: #fffdf8;
      color: #4d2a13;
      font-weight: 700;
      font-family: Georgia, "Times New Roman", serif;
      cursor: pointer;
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
    .notice-banner {{
      margin: 0 0 16px;
      padding: 10px 12px;
      border: 1px solid #b9d9b9;
      border-radius: 8px;
      background: #edf8ed;
      color: #245224;
      font-size: 15px;
    }}
    .notice-banner.warning {{
      border-color: #e0c79f;
      background: #fff7e8;
      color: #7a541c;
    }}
    @media print {{
      .action-panel {{
        display: none !important;
      }}
      .wrap {{
        max-width: none;
        padding: 0;
      }}
      pre {{
        border: 0;
        border-radius: 0;
        padding: 0;
      }}
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
    .notice-banner.warning {{
      border-color: #e0c79f;
      background: #fff7e8;
      color: #7a541c;
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
    @media print {{
      .top,
      .notes,
      .action-panel,
      .notice-banner {{
        display: none !important;
      }}
      .wrap {{
        max-width: none;
        padding: 0;
      }}
      table,
      .kv,
      .yaml-block {{
        border-radius: 0;
      }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <h1>{html.escape(title)}</h1>
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


def save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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


def bjcp_progress_payload() -> dict:
    if BJCP_PROGRESS_FILE.exists():
        return load_json(BJCP_PROGRESS_FILE)
    if BJCP_PROGRESS_TEMPLATE_FILE.exists():
        return deepcopy(load_json(BJCP_PROGRESS_TEMPLATE_FILE))
    return {}


def bjcp_question_bank_payload() -> dict:
    if BJCP_QUESTION_BANK_FILE.exists():
        return load_json(BJCP_QUESTION_BANK_FILE)
    return {}


def persist_bjcp_progress(payload: dict) -> None:
    save_json(BJCP_PROGRESS_FILE, payload)


def reset_bjcp_progress() -> None:
    if BJCP_PROGRESS_TEMPLATE_FILE.exists():
        save_json(BJCP_PROGRESS_FILE, deepcopy(load_json(BJCP_PROGRESS_TEMPLATE_FILE)))
    elif BJCP_PROGRESS_FILE.exists():
        BJCP_PROGRESS_FILE.unlink()


def bjcp_mastery_state(payload: dict | None = None) -> tuple[set[str], list[str]]:
    progress = payload or bjcp_progress_payload()
    bank = {q["id"] for q in bjcp_question_bank_payload().get("questions", [])}
    mastered = set(progress.get("mastered_question_ids", []) or [])
    cycle_completed = list(progress.get("completed_mastery_cycles", []) or [])

    # Keep only currently valid question ids.
    mastered &= bank
    seen_correct: set[str] = set()
    seen_wrong_after_correct: set[str] = set()

    for session in progress.get("sessions", []):
        for result in session.get("results", []):
            qid = result.get("question_id", "")
            if qid not in bank:
                continue
            if result.get("is_correct"):
                seen_correct.add(qid)
            elif qid in seen_correct:
                seen_wrong_after_correct.add(qid)

    mastered |= seen_correct
    mastered -= seen_wrong_after_correct
    return mastered, cycle_completed


def choose_bjcp_test_questions(count: int = 12) -> list[dict]:
    questions = list(bjcp_question_bank_payload().get("questions", []))
    if not questions:
        return []
    progress = bjcp_progress_payload()
    sessions = progress.get("sessions", [])
    last_question_ids: set[str] = set(sessions[-1].get("question_ids", []) or []) if sessions else set()
    mastered, _ = bjcp_mastery_state(progress)
    pool = [question for question in questions if question.get("id") not in mastered]

    # If the mastery pool is exhausted, automatically reset the cycle.
    if not pool:
        pool = list(questions)

    if last_question_ids and len(pool) > count:
        non_repeat_questions = [question for question in pool if question.get("id") not in last_question_ids]
        if len(non_repeat_questions) >= count:
            pool = non_repeat_questions
    if len(pool) <= count:
        RNG.shuffle(pool)
        return pool
    selected = RNG.sample(pool, count)
    RNG.shuffle(selected)
    return selected


def recalc_bjcp_progress_stats(payload: dict) -> dict:
    sessions = payload.get("sessions", [])
    bank = {q["id"]: q for q in bjcp_question_bank_payload().get("questions", [])}
    by_topic: dict[str, dict[str, float]] = deepcopy(
        bjcp_progress_payload().get("stats", {}).get("by_topic", {})
        or {
            "exam_structure": {"answered": 0, "correct": 0, "accuracy_pct": 0.0},
            "ingredients": {"answered": 0, "correct": 0, "accuracy_pct": 0.0},
            "process": {"answered": 0, "correct": 0, "accuracy_pct": 0.0},
            "off_flavors": {"answered": 0, "correct": 0, "accuracy_pct": 0.0},
            "styles_core": {"answered": 0, "correct": 0, "accuracy_pct": 0.0},
            "styles_comparison": {"answered": 0, "correct": 0, "accuracy_pct": 0.0},
            "judging_process": {"answered": 0, "correct": 0, "accuracy_pct": 0.0},
        }
    )
    for topic in by_topic.values():
        topic["answered"] = 0
        topic["correct"] = 0
        topic["accuracy_pct"] = 0.0

    answered = 0
    correct = 0
    misses_by_topic: dict[str, int] = defaultdict(int)
    for session in sessions:
        for result in session.get("results", []):
            qid = result.get("question_id", "")
            question = bank.get(qid, {})
            topic = question.get("topic", "unknown")
            by_topic.setdefault(topic, {"answered": 0, "correct": 0, "accuracy_pct": 0.0})
            by_topic[topic]["answered"] += 1
            answered += 1
            if result.get("is_correct"):
                by_topic[topic]["correct"] += 1
                correct += 1
            else:
                misses_by_topic[topic] += 1

    for topic, row in by_topic.items():
        topic_answered = int(row.get("answered", 0))
        topic_correct = int(row.get("correct", 0))
        row["accuracy_pct"] = round((topic_correct / topic_answered) * 100.0, 1) if topic_answered else 0.0

    accuracy_pct = round((correct / answered) * 100.0, 1) if answered else 0.0
    weak_topics = [
        topic for topic, row in sorted(by_topic.items(), key=lambda item: (item[1].get("accuracy_pct", 0.0), item[0]))
        if int(row.get("answered", 0)) > 0 and float(row.get("accuracy_pct", 0.0)) < 80.0
    ][:3]

    if accuracy_pct >= 90.0:
        readiness_status = "exam_ready"
    elif accuracy_pct >= 80.0:
        readiness_status = "near_ready"
    elif accuracy_pct >= 70.0:
        readiness_status = "foundational_gaps"
    else:
        readiness_status = "not_ready"

    recommended_next = "Start with: bjcp teach exam_structure"
    if weak_topics:
        recommended_next = f"Review missed in: {', '.join(weak_topics)}"
    elif answered >= 12:
        recommended_next = "Take another mini test and compare weak topics."

    payload["stats"] = {
        "questions_answered": answered,
        "correct": correct,
        "accuracy_pct": accuracy_pct,
        "by_topic": by_topic,
    }
    payload["readiness"] = {
        "status": readiness_status,
        "weak_topics": weak_topics,
        "recommended_next": recommended_next,
    }
    return payload


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


def render_study_page() -> tuple[bytes, str]:
    progress = bjcp_progress_payload()
    bank = bjcp_question_bank_payload()
    stats = progress.get("stats", {})
    readiness = progress.get("readiness", {})
    by_topic = stats.get("by_topic", {})
    questions = bank.get("questions", [])
    sessions = list(reversed(progress.get("sessions", [])[-10:]))

    question_count = len(questions)
    answered = int(stats.get("questions_answered", 0))
    accuracy = float(stats.get("accuracy_pct", 0.0))
    weak_topics = readiness.get("weak_topics", [])
    recommended_next = readiness.get("recommended_next", "")

    summary = (
        "<div class=\"kv\">"
        f"<div class=\"kv-row\"><div class=\"kv-key\">Question Bank</div><div>{question_count} questions</div></div>"
        f"<div class=\"kv-row\"><div class=\"kv-key\">Questions Answered</div><div>{answered}</div></div>"
        f"<div class=\"kv-row\"><div class=\"kv-key\">Accuracy</div><div>{accuracy:.1f}%</div></div>"
        f"<div class=\"kv-row\"><div class=\"kv-key\">Readiness</div><div>{html.escape(str(readiness.get('status', 'not_ready')))}</div></div>"
        f"<div class=\"kv-row\"><div class=\"kv-key\">Recommended Next</div><div>{html.escape(recommended_next or 'Start with: bjcp teach exam_structure')}</div></div>"
        "</div>"
    )

    topic_rows = []
    raw_lines = [
        "BJCP STUDY",
        f"question bank: {question_count}",
        f"questions answered: {answered}",
        f"accuracy: {accuracy:.1f}%",
        f"readiness: {readiness.get('status', 'not_ready')}",
        f"recommended next: {recommended_next or 'Start with: bjcp teach exam_structure'}",
        "",
    ]
    for topic, row in by_topic.items():
        topic_rows.append(
            f"<tr><td>{html.escape(topic)}</td><td>{int(row.get('answered', 0))}</td><td>{int(row.get('correct', 0))}</td><td>{float(row.get('accuracy_pct', 0.0)):.1f}%</td></tr>"
        )
        raw_lines.append(
            f"{topic}: answered {int(row.get('answered', 0))}, correct {int(row.get('correct', 0))}, accuracy {float(row.get('accuracy_pct', 0.0)):.1f}%"
        )

    weak_html = (
        "<ul>" + "".join(f"<li>{html.escape(topic)}</li>" for topic in weak_topics) + "</ul>"
        if weak_topics
        else '<p class="notes">No weak topics recorded yet.</p>'
    )
    if weak_topics:
        raw_lines.append("")
        raw_lines.append("weak topics:")
        raw_lines.extend(f"- {topic}" for topic in weak_topics)

    recent_rows = []
    for session in sessions:
        recent_rows.append(
            f"<tr><td>{html.escape(session.get('completed_utc', ''))}</td><td>{int(session.get('correct', 0))}/{int(session.get('total', 0))}</td><td>{float(session.get('score_pct', 0.0)):.1f}%</td><td>{int(session.get('duration_sec', 0))} sec</td></tr>"
        )
    if sessions:
        raw_lines.append("")
        raw_lines.append("recent tests:")
        for session in sessions:
            raw_lines.append(
                f"- {session.get('completed_utc', '')}: {int(session.get('correct', 0))}/{int(session.get('total', 0))} ({float(session.get('score_pct', 0.0)):.1f}%)"
            )

    last_misses = sessions[0].get("misses", []) if sessions else []
    missed_html = (
        "".join(
            "<section>"
            f"<h3>{html.escape(miss.get('prompt', ''))}</h3>"
            f"<p class=\"notes\">Your answer: {html.escape(miss.get('your_answer', '(blank)'))}</p>"
            f"<p><strong>Correct:</strong> {html.escape(miss.get('correct_answer', ''))}</p>"
            f"<p>{html.escape(miss.get('explanation', ''))}</p>"
            "</section>"
            for miss in last_misses
        )
        if last_misses
        else '<p class="notes">No missed questions recorded yet.</p>'
    )

    body = (
        summary
        + "<section><h2>Mini Test</h2><p class=\"notes\">Take a 12-question drill with setup options for difficulty, timer, and immediate answer feedback.</p>"
        + '<div class="action-links"><a href="/study/test" target="content">Start Mini Test</a>'
        + '<form method="post" action="/study/reset" target="content" onsubmit="return confirm(\'Reset all saved BJCP test history and progress?\');" style="display:inline;">'
        + '<button type="submit">Reset Tests</button></form></div></section>'
        + "<section><h2>Topic Progress</h2><table><thead><tr><th>Topic</th><th>Answered</th><th>Correct</th><th>Accuracy</th></tr></thead><tbody>"
        + "".join(topic_rows)
        + "</tbody></table></section>"
        + "<section><h2>Weak Topics</h2>"
        + weak_html
        + "</section>"
        + "<section><h2>Recent Tests</h2><table><thead><tr><th>Completed</th><th>Score</th><th>Percent</th><th>Time</th></tr></thead><tbody>"
        + ("".join(recent_rows) if recent_rows else "<tr><td colspan=\"4\">No saved tests yet.</td></tr>")
        + "</tbody></table></section>"
        + "<section><h2>Latest Missed Questions</h2>"
        + missed_html
        + "</section>"
        + "<section><h2>Study Assets</h2><table><thead><tr><th>File</th><th>Purpose</th></tr></thead><tbody>"
        + "<tr><td><a href=\"/view?path=libraries/bjcp_study/_index.md\" target=\"content\">_index.md</a></td><td>Study mode contract</td></tr>"
        + "<tr><td><a href=\"/view?path=libraries/bjcp_study/curriculum.md\" target=\"content\">curriculum.md</a></td><td>Topic order and readiness standard</td></tr>"
        + "<tr><td><a href=\"/view?path=libraries/bjcp_study/rubrics.md\" target=\"content\">rubrics.md</a></td><td>Scoring bands and remediation rules</td></tr>"
        + "<tr><td><a href=\"/view?path=libraries/bjcp_study/question_bank.json\" target=\"content\">question_bank.json</a></td><td>Tagged practice questions</td></tr>"
        + "<tr><td><a href=\"/view?path=libraries/bjcp_study/progress_template.json\" target=\"content\">progress_template.json</a></td><td>Progress and readiness state</td></tr>"
        + "</tbody></table></section>"
    )
    page = render_structured_page(
        "BJCP Study",
        "Light integration for study prep: readiness snapshot, progress by topic, and direct access to the study assets.",
        body,
        "/study?raw=1",
    )
    return page, "\n".join(raw_lines).rstrip()


def render_study_test_setup_page() -> bytes:
    return b"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>BJCP Mini Test Setup</title>
  <style>
    body { margin: 0; background: #f5efe5; color: #1d1a18; font-family: Georgia, "Times New Roman", serif; }
    .wrap { max-width: 760px; margin: 0 auto; padding: 18px 22px 28px; }
    h1 { margin: 0 0 10px; color: #8a4b24; font-size: 28px; }
    p { color: #6a635d; }
    form { background: #fffdf8; border: 1px solid #d6cab8; border-radius: 10px; padding: 16px; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; align-items: start; }
    label { display: block; font-size: 14px; color: #4d2a13; font-weight: 700; margin-bottom: 4px; }
    select, input[type="checkbox"] { accent-color: #8a4b24; }
    select { width: 100%; padding: 8px 9px; border: 1px solid #d6cab8; border-radius: 6px; background: #fff; }
    .checkbox-row { display: flex; align-items: center; gap: 8px; padding-top: 24px; }
    .checkbox-row label { margin: 0; font-weight: 700; }
    .hint { margin-top: 4px; color: #6a635d; font-size: 13px; }
    .actions { margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; }
    button, a.button { display: inline-block; padding: 8px 11px; border-radius: 6px; border: 1px solid #d6cab8; background: #fffdf8; color: #4d2a13; text-decoration: none; font-weight: 700; }
    @media (max-width: 700px) { .grid { grid-template-columns: 1fr; } .checkbox-row { padding-top: 0; } }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>BJCP Mini Test Setup</h1>
    <p>Choose whether you want a timer and whether you want immediate answer feedback before starting the 12-question mini test.</p>
    <form method="get" action="/study/test/run">
      <div class="grid">
        <div class="checkbox-row">
          <input id="timer_enabled" name="timer_enabled" type="checkbox" value="1" checked>
          <label for="timer_enabled">Use timer</label>
        </div>
        <div class="checkbox-row">
          <input id="show_answers_as_go" name="show_answers_as_go" type="checkbox" value="1">
          <label for="show_answers_as_go">Show answers as I go</label>
        </div>
      </div>
      <div class="actions">
        <button type="submit">Start Mini Test</button>
        <a class="button" href="/study" target="content">Cancel</a>
      </div>
    </form>
  </div>
</body>
</html>"""


def render_study_test_page(timer_enabled: bool = True, show_answers_as_go: bool = False) -> bytes:
    questions = choose_bjcp_test_questions(12)
    allotted_sec = 12 * 60 if timer_enabled else 0
    question_cards = []
    for idx, question in enumerate(questions, start=1):
        choices_list = list(question.get("choices", []))
        RNG.shuffle(choices_list)
        choices = "".join(
            f'<label class="choice"><input type="radio" name="q_{html.escape(question["id"])}" value="{html.escape(choice)}"> {html.escape(choice)}</label>'
            for choice in choices_list
        )
        question_cards.append(
            "<section class=\"question-card\">"
            f"<div class=\"question-meta\">Question {idx} | {html.escape(question.get('topic', ''))}</div>"
            f"<h2>{html.escape(question.get('prompt', ''))}</h2>"
            f"<input type=\"hidden\" name=\"question_id\" value=\"{html.escape(question['id'])}\">"
            f"<div class=\"choices\">{choices}</div>"
            f"<div class=\"feedback\" id=\"feedback_{html.escape(question['id'])}\"></div>"
            f"<details class=\"explain\" id=\"explain_{html.escape(question['id'])}\"><summary>Why?</summary><div>{html.escape(question.get('explanation', ''))}</div></details>"
            "</section>"
        )
    question_ids = ",".join(question["id"] for question in questions)
    question_payload = {
        question["id"]: {
            "answer": question.get("answer", ""),
            "explanation": question.get("explanation", ""),
        }
        for question in questions
    }
    timer_block = (
        f'<div class="timer">Time Remaining: <span id="timer">{allotted_sec // 60}:00</span></div>'
        if timer_enabled
        else '<div class="timer">Timer disabled for this mini test.</div>'
    )
    timer_script = (
        f"""
    const allotted = {allotted_sec};
    let remaining = allotted;
    const timerEl = document.getElementById('timer');
    const formEl = document.getElementById('study-form');
    const durationEl = document.getElementById('duration_sec');
    function renderTime(value) {{
      const minutes = Math.floor(value / 60);
      const seconds = value % 60;
      timerEl.textContent = `${{minutes}}:${{String(seconds).padStart(2, '0')}}`;
    }}
    renderTime(remaining);
    const tick = setInterval(() => {{
      remaining -= 1;
      durationEl.value = String(allotted - Math.max(remaining, 0));
      renderTime(Math.max(remaining, 0));
      if (remaining <= 0) {{
        clearInterval(tick);
        formEl.submit();
      }}
    }}, 1000);
"""
        if timer_enabled
        else """
    const formEl = document.getElementById('study-form');
    const durationEl = document.getElementById('duration_sec');
    const startedAt = Date.now();
    formEl.addEventListener('submit', () => {
      durationEl.value = String(Math.max(0, Math.round((Date.now() - startedAt) / 1000)));
    });
"""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>BJCP Mini Test</title>
  <style>
    body {{ margin: 0; background: #f5efe5; color: #1d1a18; font-family: Georgia, "Times New Roman", serif; }}
    .wrap {{ max-width: 900px; margin: 0 auto; padding: 18px 22px 28px; }}
    h1 {{ margin: 0 0 10px; color: #8a4b24; font-size: 28px; }}
    p {{ color: #6a635d; }}
    .timer {{ position: sticky; top: 0; z-index: 20; margin: 0 0 16px; padding: 10px 12px; border: 1px solid #d6cab8; border-radius: 8px; background: #fcf8f1; color: #4d2a13; font-weight: 700; }}
    form {{ display: grid; gap: 14px; }}
    .question-card {{ background: #fffdf8; border: 1px solid #d6cab8; border-radius: 8px; padding: 14px 16px; }}
    .question-card h2 {{ margin: 0 0 10px; font-size: 19px; color: #1d1a18; }}
    .question-meta {{ margin: 0 0 8px; color: #6a635d; font-size: 13px; text-transform: uppercase; letter-spacing: 0.04em; }}
    .choices {{ display: grid; gap: 8px; }}
    .choice {{ display: block; padding: 8px 10px; border: 1px solid #e7dccb; border-radius: 6px; background: #fff; }}
    .feedback {{ min-height: 24px; margin-top: 10px; font-weight: 700; }}
    .feedback.correct {{ color: #2c5a2c; }}
    .feedback.wrong {{ color: #9a2d2d; }}
    .feedback.hidden {{ display: none; }}
    .explain {{ margin-top: 8px; }}
    .explain.hidden {{ display: none; }}
    .explain summary {{ cursor: pointer; color: #8a4b24; font-weight: 700; }}
    .explain div {{ margin-top: 6px; color: #4d2a13; line-height: 1.4; }}
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    button, a.button {{ display: inline-block; padding: 8px 11px; border-radius: 6px; border: 1px solid #d6cab8; background: #fffdf8; color: #4d2a13; text-decoration: none; font-weight: 700; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>BJCP Mini Test</h1>
    <p>12 mixed questions. Submit when done.</p>
    {timer_block}
    <form id="study-form" method="post" action="/study/submit">
      <input type="hidden" name="question_ids" value="{html.escape(question_ids)}">
      <input type="hidden" name="allotted_sec" value="{allotted_sec}">
      <input type="hidden" name="timer_enabled" value="{"1" if timer_enabled else "0"}">
      <input type="hidden" name="show_answers_as_go" value="{"1" if show_answers_as_go else "0"}">
      <input type="hidden" id="duration_sec" name="duration_sec" value="0">
      {''.join(question_cards)}
      <div class="actions">
        <button type="submit">Submit Mini Test</button>
        <a class="button" href="/study" target="content">Cancel</a>
      </div>
    </form>
  </div>
  <script>
    {timer_script}
    const liveFeedbackEnabled = {"true" if show_answers_as_go else "false"};
    const questionMeta = {json.dumps(question_payload)};
    if (liveFeedbackEnabled) {{
      for (const [qid, meta] of Object.entries(questionMeta)) {{
        const radios = Array.from(document.querySelectorAll(`input[name="q_${{qid}}"]`));
        const feedbackEl = document.getElementById(`feedback_${{qid}}`);
        const explainEl = document.getElementById(`explain_${{qid}}`);
        if (feedbackEl) feedbackEl.classList.remove('hidden');
        if (explainEl) explainEl.classList.add('hidden');
        for (const radio of radios) {{
          radio.addEventListener('change', () => {{
            if (radio.value === meta.answer) {{
              feedbackEl.textContent = '✓ Correct';
              feedbackEl.className = 'feedback correct';
              if (explainEl) {{
                explainEl.open = false;
                explainEl.className = 'explain hidden';
              }}
            }} else {{
              feedbackEl.textContent = '✗ Not quite';
              feedbackEl.className = 'feedback wrong';
              if (explainEl) {{
                explainEl.className = 'explain';
              }}
            }}
          }});
        }}
      }}
    }} else {{
      for (const qid of Object.keys(questionMeta)) {{
        const feedbackEl = document.getElementById(`feedback_${{qid}}`);
        const explainEl = document.getElementById(`explain_${{qid}}`);
        if (feedbackEl) feedbackEl.className = 'feedback hidden';
        if (explainEl) explainEl.className = 'explain hidden';
      }}
    }}
  </script>
</body>
</html>
""".encode("utf-8")


def grade_study_test(form: dict[str, str]) -> tuple[bytes, str]:
    bank = {q["id"]: q for q in bjcp_question_bank_payload().get("questions", [])}
    question_ids = [qid for qid in form.get("question_ids", "").split(",") if qid]
    duration_sec = int(form.get("duration_sec", "0") or "0")
    results = []
    misses = []
    by_topic: dict[str, dict[str, int]] = defaultdict(lambda: {"answered": 0, "correct": 0})
    correct = 0

    for qid in question_ids:
        question = bank.get(qid)
        if not question:
            continue
        your_answer = form.get(f"q_{qid}", "")
        is_correct = your_answer == question.get("answer", "")
        topic = question.get("topic", "unknown")
        by_topic[topic]["answered"] += 1
        if is_correct:
            by_topic[topic]["correct"] += 1
            correct += 1
        else:
            misses.append(
                {
                    "question_id": qid,
                    "topic": topic,
                    "prompt": question.get("prompt", ""),
                    "your_answer": your_answer,
                    "correct_answer": question.get("answer", ""),
                    "explanation": question.get("explanation", ""),
                }
            )
        results.append({"question_id": qid, "your_answer": your_answer, "is_correct": is_correct})

    total = len(question_ids)
    score_pct = round((correct / total) * 100.0, 1) if total else 0.0
    completed_utc = __import__("datetime").datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    progress = bjcp_progress_payload()
    progress.setdefault("schema_version", 1)
    progress.setdefault("mode_active", False)
    progress.setdefault("started_utc", "")
    progress["last_updated_utc"] = completed_utc
    progress.setdefault("sessions", [])
    progress["sessions"].append(
        {
            "id": f"mini_test_{completed_utc}",
            "completed_utc": completed_utc,
            "type": "mini_test",
            "timer_enabled": form.get("timer_enabled", "1") == "1",
            "total": total,
            "correct": correct,
            "score_pct": score_pct,
            "duration_sec": duration_sec,
            "question_ids": question_ids,
            "results": results,
            "misses": misses,
        }
    )
    mastered_before, completed_cycles = bjcp_mastery_state(progress)
    progress["mastered_question_ids"] = sorted(mastered_before)
    current_bank_ids = {q["id"] for q in bjcp_question_bank_payload().get("questions", [])}
    if current_bank_ids and mastered_before >= current_bank_ids:
        completed_cycles = list(completed_cycles)
        completed_cycles.append(completed_utc)
        progress["completed_mastery_cycles"] = completed_cycles
        progress["mastered_question_ids"] = []
    else:
        progress["completed_mastery_cycles"] = completed_cycles
    progress = recalc_bjcp_progress_stats(progress)
    persist_bjcp_progress(progress)

    topic_rows = []
    for topic, row in sorted(by_topic.items()):
        answered = int(row.get("answered", 0))
        topic_correct = int(row.get("correct", 0))
        topic_acc = round((topic_correct / answered) * 100.0, 1) if answered else 0.0
        topic_rows.append(f"<tr><td>{html.escape(topic)}</td><td>{topic_correct}/{answered}</td><td>{topic_acc:.1f}%</td></tr>")

    missed_html = (
        "".join(
            "<section>"
            f"<h3>{html.escape(miss['prompt'])}</h3>"
            f"<p class=\"notes\">Your answer: {html.escape(miss.get('your_answer') or '(blank)')}</p>"
            f"<p><strong>Correct:</strong> {html.escape(miss['correct_answer'])}</p>"
            f"<p>{html.escape(miss['explanation'])}</p>"
            "</section>"
            for miss in misses
        )
        if misses
        else '<p class="notes">Perfect run. No misses to review.</p>'
    )

    page = render_structured_page(
        "BJCP Mini Test Results",
        "Results are saved locally and feed the study overview.",
        "<div class=\"kv\">"
        f"<div class=\"kv-row\"><div class=\"kv-key\">Score</div><div>{correct}/{total}</div></div>"
        f"<div class=\"kv-row\"><div class=\"kv-key\">Percent</div><div>{score_pct:.1f}%</div></div>"
        f"<div class=\"kv-row\"><div class=\"kv-key\">Time</div><div>{duration_sec} sec</div></div>"
        "</div>"
        + "<section><h2>By Topic</h2><table><thead><tr><th>Topic</th><th>Score</th><th>Accuracy</th></tr></thead><tbody>"
        + "".join(topic_rows)
        + "</tbody></table></section>"
        + "<section><h2>Missed Questions</h2>"
        + missed_html
        + "</section>"
        + '<section><h2>Next</h2><div class="action-links"><a href="/study" target="content">Back to BJCP Study</a><a href="/study/test" target="content">Take Another Mini Test</a></div></section>',
        "/study?raw=1",
    )
    raw_lines = [
        "BJCP MINI TEST RESULTS",
        f"score: {correct}/{total}",
        f"percent: {score_pct:.1f}%",
        f"time: {duration_sec} sec",
        "",
    ]
    for miss in misses:
        raw_lines.extend(
            [
                miss["prompt"],
                f"your answer: {miss.get('your_answer') or '(blank)'}",
                f"correct: {miss['correct_answer']}",
                f"why: {miss['explanation']}",
                "",
            ]
        )
    return page, "\n".join(raw_lines).rstrip()


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


def run_text_command(cmd: list[str]) -> tuple[str, int]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return (proc.stdout + proc.stderr).strip(), proc.returncode


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


def shopping_intent_entry(recipe_token: str, bucket: str) -> dict[str, str] | None:
    if not SHOPPING_INTENT_FILE.exists():
        return None
    payload = load_json(SHOPPING_INTENT_FILE)
    recipe_n = normalize_token(recipe_token)
    for item in payload.get(bucket, []):
        if normalize_token(item.get("recipe_id", "")) == recipe_n:
            return item
    return None


def next_action_text_for_recipe(recipe_token: str, recipe_path: Path) -> str:
    state = recipe_state(recipe_token, recipe_path)
    queue_entry = shopping_intent_entry(recipe_token, "recipe_queue")
    if queue_entry:
        horizon = queue_entry.get("horizon", "")
        note = queue_entry.get("note", "")
        if horizon == "next":
            return f"Planned next brew. Prepare when you are ready to lock the brew date.{(' ' + note) if note else ''}"
        if horizon == "soon":
            return f"Planned soon, but not immediate.{(' ' + note) if note else ''}"
    active_entry = shopping_intent_entry(recipe_token, "active_brews")
    if active_entry:
        status = active_entry.get("status", "")
        note = active_entry.get("note", "")
        return f"Active batch state: {status}.{(' ' + note) if note else ''}"
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


def hop_lot_guidance_url(recipe: str) -> str:
    return "/lot-guidance?" + urllib.parse.urlencode({"recipe": recipe})


def package_readiness_url(recipe: str, brew_date: str = "") -> str:
    query = {"recipe": recipe}
    if brew_date:
        query["brew_date"] = brew_date
    return "/package-readiness?" + urllib.parse.urlencode(query)


def sensory_learning_url(recipe: str) -> str:
    return "/sensory-learning?" + urllib.parse.urlencode({"recipe": recipe})


def render_package_form(recipe_token: str, brew_date: str) -> bytes:
    default_date = __import__("datetime").date.today().isoformat()
    default_volume = "5.00"
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
          <input id="packaged_volume" name="packaged_volume" value="{default_volume}" placeholder="5.00" required>
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
          <div class="hint">Optional. Leave blank if no slurry or harvested yeast is being recorded.</div>
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


def render_package_readiness_page(recipe_token: str, brew_date: str, params: dict[str, str] | None = None) -> bytes:
    params = params or {}
    action_html = ""
    recipe_path = resolve_recipe_markdown(recipe_token)
    if recipe_path:
        action_html = action_panel_html(canonical_recipe_token(recipe_path), recipe_path)
    checked_stable = " checked" if params.get("stable_48h") == "1" else ""
    checked_vdk = " checked" if params.get("vdk_clean") == "1" else ""
    checked_bubbling = " checked" if params.get("still_bubbling") == "1" else ""
    result_html = ""
    if params.get("submitted") == "1":
        cmd = ["python3", "tools/package_readiness.py", "--recipe", recipe_token, "--json"]
        if params.get("current_fg"):
            cmd.extend(["--current-fg", params["current_fg"]])
        if params.get("stable_48h") == "1":
            cmd.append("--stable-48h")
        if params.get("vdk_clean") == "1":
            cmd.append("--vdk-clean")
        if params.get("still_bubbling") == "1":
            cmd.append("--still-bubbling")
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if proc.returncode == 0:
            payload = json.loads(proc.stdout)
            status = payload.get("status", "unknown")
            notice_class = "warning" if status != "ready" else ""
            cards = []
            for heading, key in (
                ("Confirmations", "confirmations"),
                ("Cautions", "cautions"),
                ("Blockers", "blockers"),
                ("Recipe Packaging Gates", "packaging_gates"),
            ):
                values = payload.get(key, [])
                items = "".join(f"<li>{html.escape(value)}</li>" for value in values) or "<li>(none)</li>"
                cards.append(f"<section><h2>{html.escape(heading)}</h2><ul>{items}</ul></section>")
            result_html = (
                f'<div class="notice-banner {notice_class}">Packaging Readiness: {html.escape(status.title())}. '
                f'{html.escape(payload.get("next_step", ""))}</div>'
                + "".join(cards)
            )
        else:
            result_html = f'<div class="notice-banner warning"><pre>{html.escape(proc.stdout + proc.stderr)}</pre></div>'
    body_html = f"""
    <section>
      <h2>Packaging Readiness</h2>
      <p class="notes">Use this as a gate check before packaging. It does not replace your own sample, but it should reduce the amount of state you need to hold in your head.</p>
      <form method="get" action="/package-readiness">
        <input type="hidden" name="recipe" value="{html.escape(recipe_token)}">
        <input type="hidden" name="brew_date" value="{html.escape(brew_date)}">
        <input type="hidden" name="submitted" value="1">
        <table><tbody>
          <tr><td>Recipe</td><td>{html.escape(recipe_token)}</td></tr>
          <tr><td>Brew Date</td><td>{html.escape(brew_date or "(not recorded)")}</td></tr>
          <tr><td>Current FG</td><td><input name="current_fg" value="{html.escape(params.get('current_fg', ''))}" placeholder="1.013"></td></tr>
          <tr><td>Stable 48h</td><td><label><input type="checkbox" name="stable_48h" value="1"{checked_stable}> Gravity stable for 48 hours</label></td></tr>
          <tr><td>VDK Clean</td><td><label><input type="checkbox" name="vdk_clean" value="1"{checked_vdk}> Warm sample / VDK check is clean</label></td></tr>
          <tr><td>Still Bubbling</td><td><label><input type="checkbox" name="still_bubbling" value="1"{checked_bubbling}> Still visibly bubbling / venting</label></td></tr>
        </tbody></table>
        <div class="action-links"><button type="submit">Assess Packaging Readiness</button></div>
      </form>
    </section>
    {result_html}
    """
    return render_structured_page(
        f"Package Readiness - {recipe_token.replace('_', ' ').title()}",
        "",
        body_html,
        "",
        action_html=action_html,
    )


def render_sensory_learning_page(recipe_token: str) -> bytes:
    proc = subprocess.run(
        ["python3", "tools/sensory_learning.py", "--recipe", recipe_token, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return render_dashboard_page("Sensory Learning", proc.stdout + proc.stderr)
    payload = json.loads(proc.stdout)
    recipe_path = resolve_recipe_markdown(recipe_token)
    action_html = ""
    if recipe_path:
        action_html = action_panel_html(canonical_recipe_token(recipe_path), recipe_path)
    sections: list[str] = []
    for heading, key in (
        ("Strengths", "strengths"),
        ("Misses", "misses"),
        ("Iteration Implications", "implications"),
        ("Scoring Notes", "scoring"),
    ):
        values = payload.get(key, [])
        items = "".join(f"<li>{html.escape(value)}</li>" for value in values) or "<li>(none)</li>"
        sections.append(f"<section><h2>{html.escape(heading)}</h2><ul>{items}</ul></section>")
    if payload.get("sources"):
        rows = "".join(
            f"<tr><td>{html.escape(row.get('title', ''))}</td><td>{html.escape(row.get('path', ''))}</td></tr>"
            for row in payload["sources"]
        )
        sections.append("<section><h2>Sources</h2><table><thead><tr><th>Document</th><th>Path</th></tr></thead><tbody>" + rows + "</tbody></table></section>")
    return render_structured_page(
        f"Sensory Learning - {payload.get('title', recipe_token)}",
        "Derived from sensory, side-by-side, and scoring sections already recorded in the recipe set.",
        "".join(sections),
        "",
        action_html=action_html,
    )


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
        links.append(f'<a href="{html.escape(package_readiness_url(recipe_token, state["brew_date"]))}" target="content">Packaging Readiness</a>')
    elif state["state"] == "prepared_not_brewed":
        links.append(f'<a href="{html.escape(operator_url("brew", recipe=recipe_token, date=state["brew_date"]))}" target="content">Register Brew</a>')
    else:
        links.append(f'<a href="{html.escape(operator_url("prepare", recipe=recipe_token, date="today", run_trust_check="1"))}" target="content">Prepare Today</a>')
    links.extend([
        f'<a href="{html.escape(sensory_learning_url(recipe_token))}" target="content">Sensory Learning</a>',
        f'<a href="{html.escape(hop_lot_guidance_url(recipe_token))}" target="content">Hop Lot Guidance</a>',
        f'<a href="{html.escape(operator_url("refresh-html", **refresh_params))}" target="content">Refresh Print</a>',
        f'<a href="{html.escape(operator_url("trust-check", **trust_params))}" target="content">Run Trust Check</a>',
    ])
    return (
        "<h2>Actions</h2>"
        f"<p>{html.escape(next_action_text_for_recipe(recipe_token, recipe_path))}</p>"
        f'<div class="action-links">{"".join(links)}</div>'
    )


def parse_key_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    lines = text.splitlines()
    for idx, raw in enumerate(lines):
        line = raw.rstrip()
        if not line:
            continue
        if idx + 1 < len(lines):
            next_line = lines[idx + 1].strip()
            if next_line and set(next_line) in ({"="}, {"-"}):
                current = line
                sections.setdefault(current, [])
                continue
        if set(line) == {"="} or set(line) == {"-"}:
            continue
        if current:
            sections[current].append(line)
    return sections


def render_lines_as_list(lines: list[str], empty_text: str = "(none)") -> str:
    if not lines:
        return f'<p class="notes">{html.escape(empty_text)}</p>'
    items = "".join(f"<li>{html.escape(line)}</li>" for line in lines)
    return f"<ul>{items}</ul>"


def render_operation_result_page(action: str, params: dict[str, str], ok: bool, payload: str) -> bytes:
    recipe_token = params.get("recipe", "")
    recipe_path = resolve_recipe_markdown(recipe_token) if recipe_token else None
    action_html = ""
    if recipe_path:
        action_html = action_panel_html(canonical_recipe_token(recipe_path), recipe_path)

    notice = ""
    if ok:
        if action == "prepare":
            notice = f"Prepare Successful for {recipe_token.replace('_', ' ').title()}"
        elif action == "brew":
            notice = f"Brew Registration Successful for {recipe_token.replace('_', ' ').title()}"
        elif action == "package":
            notice = f"Package Registration Successful for {recipe_token.replace('_', ' ').title()}"
    else:
        notice = f"{action.replace('-', ' ').title()} Failed"

    sections: list[str] = []
    if action == "prepare":
        rows = [
            ("Recipe", recipe_token.replace("_", " ").title()),
            ("Planned Brew Date", params.get("date", "(not provided)") or "(not provided)"),
        ]
        body = "".join(f"<tr><td>{html.escape(label)}</td><td>{html.escape(value)}</td></tr>" for label, value in rows)
        sections.append("<section><h2>What Changed</h2><table><tbody>" + body + "</tbody></table></section>")
    elif action == "brew":
        rows = [
            ("Recipe", recipe_token.replace("_", " ").title()),
            ("Brew Date", params.get("date", "(not provided)") or "(not provided)"),
        ]
        body = "".join(f"<tr><td>{html.escape(label)}</td><td>{html.escape(value)}</td></tr>" for label, value in rows)
        sections.append("<section><h2>What Changed</h2><table><tbody>" + body + "</tbody></table></section>")
    elif action == "package":
        volume = params.get("packaged_volume", "")
        unit = params.get("packaged_volume_unit", "")
        rows = [
            ("Recipe", recipe_token.replace("_", " ").title()),
            ("Brew Date", params.get("brew_date", "")),
            ("Package Date", params.get("package_date", "")),
            ("FG", params.get("fg", "")),
            ("Packaged Volume", f"{volume} {unit}".strip()),
        ]
        if params.get("co2_vols"):
            rows.append(("CO2 Vols", params["co2_vols"]))
        if params.get("harvest_yeast"):
            label = params["harvest_yeast"]
            if params.get("harvest_generation"):
                label += f" (Gen {params['harvest_generation']})"
            rows.append(("Harvest", label))
        body = "".join(f"<tr><td>{html.escape(label)}</td><td>{html.escape(value)}</td></tr>" for label, value in rows if value)
        sections.append("<section><h2>What Changed</h2><table><tbody>" + body + "</tbody></table></section>")

    if recipe_token:
        state_output, _ = run_text_command(["python3", "tools/batch_state_summary.py", "--recipe", recipe_token, "--with-next-actions"])
        state_sections = parse_key_sections(state_output)
        cards = []
        for heading in ("Active Brews", "Prepared, Not Brewed", "Brewed, Not Packaged", "Intent / Lifecycle Agreement", "Suggested Next Actions"):
            cards.append(f"<section><h2>{html.escape(heading)}</h2>{render_lines_as_list(state_sections.get(heading, []))}</section>")
        sections.append("".join(cards))

        yield_output, _ = run_text_command(["python3", "tools/yield_report.py", "--recipe", recipe_token])
        if "YIELD_REPORT_EMPTY" in yield_output:
            sections.append('<section><h2>Yield</h2><p class="notes">No package events recorded yet.</p></section>')
        else:
            yield_sections = parse_key_sections(yield_output)
            sections.append(
                "<section><h2>Yield</h2>"
                f"{render_lines_as_list(yield_sections.get('YIELD REPORT', []))}"
                f"{render_lines_as_list(yield_sections.get('SUMMARY', []), 'No summary yet.')}"
                "</section>"
            )

    raw_html = f"<details><summary>Raw operator output</summary><pre>{html.escape(payload or 'No output')}</pre></details>"
    sections.append(raw_html)
    body_html = "".join(sections)
    page = render_structured_page(
        f"Operation - {action}",
        "Structured confirmation generated from current repo state.",
        body_html,
        "",
        action_html=action_html,
        notice_text=notice,
    )
    if ok:
        return page
    return page.replace(b'class="notice-banner"', b'class="notice-banner warning"', 1)


def render_hop_lot_guidance_page(recipe_token: str) -> bytes:
    proc = subprocess.run(
        ["python3", "tools/hop_lot_guidance.py", "--recipe", recipe_token, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return render_dashboard_page("Hop Lot Guidance", proc.stdout + proc.stderr)
    payload = json.loads(proc.stdout)
    recipe_path = resolve_recipe_markdown(recipe_token)
    action_html = ""
    if recipe_path:
        action_html = action_panel_html(canonical_recipe_token(recipe_path), recipe_path)
    sections: list[str] = []
    for hop in payload.get("hops", []):
        additions = "".join(
            f"<tr><td>{html.escape(row['timing'])}</td><td>{html.escape(row['bucket'])}</td><td>{row['grams']:.1f} g</td></tr>"
            for row in hop.get("additions", [])
        )
        guidance = "".join(f"<li>{html.escape(line)}</li>" for line in hop.get("guidance", []))
        warnings = "".join(f"<li>{html.escape(line)}</li>" for line in hop.get("warnings", []))
        meta_rows = [
            ("Tracked AA", f"{float(hop['base_alpha_pct']):.1f}%" if hop.get("base_alpha_pct") is not None else "(none)"),
            ("Tracked lots", ", ".join(f"{float(v):.1f}%" for v in hop.get("lot_alpha_pct", [])) or "(none)"),
            ("On hand", f"{float(hop.get('on_hand_g', 0.0)):.1f} g"),
            ("Recipe need", f"{float(hop.get('total_grams', 0.0)):.1f} g"),
        ]
        meta_html = "".join(f"<tr><td>{html.escape(label)}</td><td>{html.escape(value)}</td></tr>" for label, value in meta_rows)
        body = [
            "<table><tbody>",
            meta_html,
            "</tbody></table>",
            "<h3>Additions</h3>",
            "<table><thead><tr><th>Timing</th><th>Bucket</th><th>Amount</th></tr></thead><tbody>",
            additions or '<tr><td colspan="3">(none)</td></tr>',
            "</tbody></table>",
            "<h3>Guidance</h3>",
            f"<ul>{guidance}</ul>" if guidance else '<p class="notes">No guidance needed.</p>',
        ]
        if warnings:
            body.extend(["<h3>Warnings</h3>", f"<ul>{warnings}</ul>"])
        sections.append(f"<section><h2>{html.escape(hop['hop_name'])}</h2>{''.join(body)}</section>")
    if not sections:
        sections.append('<p class="notes">No hop additions parsed for this recipe.</p>')
    return render_structured_page(
        f"Hop Lot Guidance - {payload.get('title', recipe_token)}",
        "Guidance layer for allocating higher-AA vs lower-AA lots across bittering and late additions. This does not yet track per-lot weights separately in stock.",
        "".join(sections),
        "",
        action_html=action_html,
    )


def render_fermentation_dashboard_page() -> bytes:
    intent = shopping_intent_payload()
    cards: list[str] = []
    raw_lines: list[str] = []

    active_rows = intent.get("active_brews", [])
    if active_rows:
        section_rows: list[str] = []
        raw_lines.append("Active Fermentation")
        for row in active_rows:
            recipe_id = row.get("recipe_id", "")
            recipe_path = resolve_recipe_markdown(recipe_id)
            if not recipe_path:
                continue
            recipe_token = canonical_recipe_token(recipe_path)
            state = recipe_state(recipe_token, recipe_path)
            next_text = next_action_text_for_recipe(recipe_token, recipe_path)
            action_links = [
                f'<a href="{html.escape(viewer_url(recipe_path))}" target="content">Recipe</a>',
            ]
            if state.get("brew_sheet"):
                action_links.append(
                    f'<a href="{html.escape(viewer_url(ROOT / state["brew_sheet"]))}" target="content">Brew Sheet</a>'
                )
            if state["state"] == "brewed_not_packaged":
                action_links.append(
                    f'<a href="{html.escape(package_form_url(recipe_token, state["brew_date"]))}" target="content">Register Package</a>'
                )
            section_rows.append(
                "<tr>"
                f"<td>{html.escape(recipe_title_for_display(recipe_path))}</td>"
                f"<td>{html.escape(row.get('status', ''))}</td>"
                f"<td>{html.escape(state.get('brew_date', '') or row.get('note', ''))}</td>"
                f"<td>{html.escape(next_text)}</td>"
                f"<td>{''.join(action_links)}</td>"
                "</tr>"
            )
            raw_lines.append(f"  {recipe_id}: {row.get('status', '')} | {next_text}")
        cards.append(
            "<section><h2>Active Fermentation</h2><table><thead><tr><th>Beer</th><th>Status</th><th>Batch</th><th>Next</th><th>Actions</th></tr></thead><tbody>"
            + "".join(section_rows)
            + "</tbody></table></section>"
        )
    else:
        cards.append('<section><h2>Active Fermentation</h2><p class="notes">No active fermentations recorded.</p></section>')

    queued_rows = intent.get("recipe_queue", [])
    if queued_rows:
        rows_html: list[str] = []
        raw_lines.append("Planned Queue")
        for row in queued_rows:
            recipe_id = row.get("recipe_id", "")
            recipe_path = resolve_recipe_markdown(recipe_id)
            if not recipe_path:
                continue
            recipe_token = canonical_recipe_token(recipe_path)
            action_links = [
                f'<a href="{html.escape(viewer_url(recipe_path))}" target="content">Recipe</a>',
                f'<a href="{html.escape(operator_url("prepare", recipe=recipe_token, date="today", run_trust_check="1"))}" target="content">Prepare</a>',
            ]
            rows_html.append(
                "<tr>"
                f"<td>{html.escape(recipe_title_for_display(recipe_path))}</td>"
                f"<td>{html.escape(row.get('horizon', ''))}</td>"
                f"<td>{html.escape(row.get('note', ''))}</td>"
                f"<td>{''.join(action_links)}</td>"
                "</tr>"
            )
            raw_lines.append(f"  {recipe_id}: {row.get('horizon', '')} | {row.get('note', '')}")
        cards.append(
            "<section><h2>Planned Queue</h2><table><thead><tr><th>Beer</th><th>Horizon</th><th>Note</th><th>Actions</th></tr></thead><tbody>"
            + "".join(rows_html)
            + "</tbody></table></section>"
        )

    body_html = "".join(cards)
    return render_structured_page(
        "Fermentation Dashboard",
        "Live fermentation and near-term brewing view from shopping intent, brew history, and active artifacts.",
        body_html,
        "",
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
    @media print {{
      .top,
      .action-panel,
      .notice-banner {{
        display: none !important;
      }}
      .wrap {{
        max-width: none;
        padding: 0;
      }}
      iframe {{
        border: 0;
        border-radius: 0;
        height: auto;
      }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <h1>{html.escape(title)}</h1>
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
    cmd = ["python3", "tools/brew_op.py", "--action", action]
    if params.get("recipe"):
        cmd.extend(["--recipe", params["recipe"]])
    if params.get("date"):
        cmd.extend(["--date", params["date"]])
    if params.get("brew_date"):
        cmd.extend(["--brew-date", params["brew_date"]])
    if params.get("package_date"):
        cmd.extend(["--package-date", params["package_date"]])
    if params.get("fg"):
        cmd.extend(["--fg", params["fg"]])
    if params.get("packaged_volume"):
        cmd.extend(["--packaged-volume", params["packaged_volume"]])
    if params.get("packaged_volume_unit"):
        cmd.extend(["--packaged-volume-unit", params["packaged_volume_unit"]])
    if params.get("co2_vols"):
        cmd.extend(["--co2-vols", params["co2_vols"]])
    if params.get("harvest_yeast"):
        cmd.extend(["--harvest-yeast", params["harvest_yeast"]])
    if params.get("harvest_generation"):
        cmd.extend(["--harvest-generation", params["harvest_generation"]])
    if params.get("run_trust_check"):
        cmd.append("--run-trust-check")
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return proc.stdout + proc.stderr, proc.returncode == 0


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
    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/study/submit":
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            payload = self.rfile.read(content_length).decode("utf-8")
            form = {key: values[0] for key, values in urllib.parse.parse_qs(payload).items() if values}
            page, _raw_text = grade_study_test(form)
            self.respond_bytes(200, "text/html; charset=utf-8", page)
            return
        if parsed.path == "/study/reset":
            reset_bjcp_progress()
            page, _raw_text = render_study_page()
            self.respond_bytes(200, "text/html; charset=utf-8", page)
            return
        self.respond_text(404, "Not found.")

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

        if parsed.path == "/study":
            page, raw_text = render_study_page()
            if params.get("raw", ["0"])[0] == "1":
                self.respond_bytes(200, "text/plain; charset=utf-8", raw_text.encode("utf-8"))
                return
            self.respond_bytes(200, "text/html; charset=utf-8", page)
            return

        if parsed.path == "/study/test":
            if params.get("raw", ["0"])[0] == "1":
                self.respond_text(200, "Mini test is interactive only.")
                return
            self.respond_bytes(200, "text/html; charset=utf-8", render_study_test_setup_page())
            return

        if parsed.path == "/study/test/run":
            if params.get("raw", ["0"])[0] == "1":
                self.respond_text(200, "Mini test is interactive only.")
                return
            timer_enabled = params.get("timer_enabled", ["0"])[0] == "1"
            show_answers_as_go = params.get("show_answers_as_go", ["0"])[0] == "1"
            self.respond_bytes(200, "text/html; charset=utf-8", render_study_test_page(timer_enabled, show_answers_as_go))
            return

        if parsed.path == "/package-form":
            recipe_token = params.get("recipe", [""])[0]
            brew_date = params.get("brew_date", [""])[0]
            if not recipe_token:
                self.respond_text(400, "Missing recipe.")
                return
            self.respond_bytes(200, "text/html; charset=utf-8", render_package_form(recipe_token, brew_date))
            return

        if parsed.path == "/package-readiness":
            recipe_token = params.get("recipe", [""])[0]
            brew_date = params.get("brew_date", [""])[0]
            if not recipe_token:
                self.respond_text(400, "Missing recipe.")
                return
            flat_params = {key: values[0] for key, values in params.items() if values}
            self.respond_bytes(200, "text/html; charset=utf-8", render_package_readiness_page(recipe_token, brew_date, flat_params))
            return

        if parsed.path == "/sensory-learning":
            recipe_token = params.get("recipe", [""])[0]
            if not recipe_token:
                self.respond_text(400, "Missing recipe.")
                return
            self.respond_bytes(200, "text/html; charset=utf-8", render_sensory_learning_page(recipe_token))
            return

        if parsed.path == "/lot-guidance":
            recipe_token = params.get("recipe", [""])[0]
            if not recipe_token:
                self.respond_text(400, "Missing recipe.")
                return
            self.respond_bytes(200, "text/html; charset=utf-8", render_hop_lot_guidance_page(recipe_token))
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
            if action in {"prepare", "brew", "package", "status"}:
                self.respond_bytes(200, "text/html; charset=utf-8", render_operation_result_page(action, flat_params, ok, payload))
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
            if mode not in {"state", "next", "fermentation"}:
                self.respond_text(400, "Unsupported dashboard mode.")
                return
            if mode == "fermentation":
                self.respond_bytes(200, "text/html; charset=utf-8", render_fermentation_dashboard_page())
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
