#!/usr/bin/env python3
"""Simple local web UI for browsing brew-assistant artifacts."""

from __future__ import annotations

import argparse
import html
import json
import math
import mimetypes
import re
import subprocess
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


def render_text_page(path: Path, body: str, action_html: str = "") -> bytes:
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
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <h1>{title}</h1>
      <a href="{html.escape(raw_url(path))}">Raw file</a>
    </div>
    {render_action_panel(action_html)}
    {content}
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


def render_structured_page(title: str, notes: str, body_html: str, raw_href: str, action_html: str = "") -> bytes:
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


def resolve_recipe_context_from_path(path: Path) -> tuple[str, Path] | None:
    if path.suffix == ".md" and "recipes" in path.parts:
        return path.stem, path
    if path.suffix == ".html" and path.parent == ROOT / "recipes" / "html_exports":
        recipe_path = resolve_recipe_markdown(path.stem)
        if recipe_path:
            return recipe_path.stem, recipe_path
    if path.suffix == ".html" and path.parent == ROOT / "brewing" / "brew_day_sheets":
        stem = re.sub(r"_brew_day_sheet(?:_\d{4}-\d{2}-\d{2})?$", "", path.stem)
        recipe_path = resolve_recipe_markdown(stem)
        if recipe_path:
            return recipe_path.stem, recipe_path
    return None


def next_action_text_for_recipe(recipe_token: str, recipe_path: Path) -> str:
    brew_sheet_date = ""
    for pair in active_pairs_payload():
        pair_recipe = ROOT / pair.get("recipe", "")
        if pair_recipe.resolve() == recipe_path.resolve():
            match = re.search(r"_(\d{4}-\d{2}-\d{2})\.html$", pair.get("brew_sheet", ""))
            brew_sheet_date = match.group(1) if match else ""
            break
    events = brew_history_events()
    brew_events = [event for event in events if event.get("type") == "brew" and normalize_token(event.get("recipe_id", "")) == normalize_token(recipe_token)]
    package_events = [event for event in events if event.get("type") == "package" and normalize_token(event.get("recipe_id", "")) == normalize_token(recipe_token)]
    if brew_events:
        latest_brew = max(brew_events, key=lambda row: row.get("brew_date", ""))
        latest_brew_date = latest_brew.get("brew_date", "")
        packaged = any(event.get("brew_date", "") == latest_brew_date for event in package_events)
        if not packaged:
            return f"Next likely action: package {recipe_token} brewed {latest_brew_date}."
    if brew_sheet_date:
        return f"Next likely action: register brew for dated sheet {brew_sheet_date}."
    return f"Next likely action: prepare {recipe_token} when ready to brew."


def action_panel_html(recipe_token: str, recipe_path: Path) -> str:
    links = [
        f'<a href="{html.escape(operator_url("status", recipe=recipe_token))}" target="content">Next Action</a>',
        f'<a href="{html.escape(operator_url("refresh-html", recipe=recipe_token))}" target="content">Refresh Print</a>',
        f'<a href="{html.escape(operator_url("trust-check"))}" target="content">Run Trust Check</a>',
        f'<a href="{html.escape(operator_url("prepare", recipe=recipe_token, date="today", run_trust_check="1"))}" target="content">Prepare Today</a>',
        f'<a href="{html.escape(operator_url("brew", recipe=recipe_token, date="today"))}" target="content">Register Brew Today</a>',
        f'<a href="{html.escape('/shopping?recipe=' + urllib.parse.quote(recipe_path.relative_to(ROOT).as_posix()))}" target="content">Shopping</a>',
    ]
    return (
        "<h2>Actions</h2>"
        f"<p>{html.escape(next_action_text_for_recipe(recipe_token, recipe_path))}</p>"
        f'<div class="action-links">{"".join(links)}</div>'
    )


def render_html_wrapper(path: Path, action_html: str = "") -> bytes:
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
    {render_action_panel(action_html)}
    <iframe src="{html.escape(src)}"></iframe>
  </div>
</body>
</html>
""".encode("utf-8")


def operate_output(action: str, params: dict[str, str]) -> tuple[str, bool]:
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
    if params.get("run_trust_check"):
        cmd.append("--run-trust-check")
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return proc.stdout + proc.stderr, proc.returncode == 0


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

        if parsed.path == "/operate":
            action = params.get("action", [""])[0]
            if not action:
                self.respond_text(400, "Missing action.")
                return
            flat_params = {key: values[0] for key, values in params.items() if values}
            payload, ok = operate_output(action, flat_params)
            title = f"Operation - {action}"
            page = render_dashboard_page(title, payload or ("OK" if ok else "No output"))
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

            if path.suffix == ".html":
                context = resolve_recipe_context_from_path(path)
                action_html = ""
                if context:
                    recipe_token, recipe_path = context
                    action_html = action_panel_html(recipe_token, recipe_path)
                self.respond_bytes(200, "text/html; charset=utf-8", render_html_wrapper(path, action_html))
                return

            body = path.read_text(encoding="utf-8")
            if path.suffix == ".json":
                body = json.dumps(json.loads(body), indent=2)
            context = resolve_recipe_context_from_path(path)
            action_html = ""
            if context:
                recipe_token, recipe_path = context
                action_html = action_panel_html(recipe_token, recipe_path)
            self.respond_bytes(200, "text/html; charset=utf-8", render_text_page(path, body, action_html))
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
