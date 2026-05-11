#!/usr/bin/env python3
"""Create a simple printable brew-day packet from one recipe.

This is intentionally operator-facing. It wraps the existing recipe print,
brew-sheet, and validation tools so a brewer can run one command and get a
clear "ready" or "needs attention" result.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import subprocess
import sys
from pathlib import Path

from prepare_brew import ARCHIVE_SHEETS_DIR, SHEETS_DIR, derive_sheet_base, resolve_beerxml
from render_recipe_html import ROOT, render_one, resolve_recipe
from validate_print_readability import check_brew_sheet, check_recipe_html


ACTION_REQUIRED = "ACTION REQUIRED"


def checkbox() -> str:
    return '<span class="checkbox"></span>'


def normalize_heading(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def parse_sections(text: str) -> tuple[str, dict[str, list[str]]]:
    title = "Recipe"
    current = ""
    sections: dict[str, list[str]] = {}
    for raw in text.splitlines():
        line = raw.rstrip()
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


def find_section(sections: dict[str, list[str]], *needles: str) -> list[str]:
    normalized_needles = [normalize_heading(needle) for needle in needles]
    for heading, lines in sections.items():
        normalized = normalize_heading(heading)
        if any(needle in normalized for needle in normalized_needles):
            return lines
    return []


def section_bullets(lines: list[str]) -> list[str]:
    out: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("- "):
            out.append(stripped[2:].strip())
    return out


def numbered_steps(lines: list[str]) -> list[str]:
    out: list[str] = []
    for raw in lines:
        stripped = raw.strip()
        if re.match(r"^\d+\.\s+", stripped):
            out.append(re.sub(r"^\d+\.\s+", "", stripped).strip())
    return out


def target_value(lines: list[str], label: str, default: str = ACTION_REQUIRED) -> str:
    pattern = re.compile(rf"^-\s*{re.escape(label)}:\s*(.+)$", re.IGNORECASE)
    for raw in lines:
        match = pattern.match(raw.strip())
        if match:
            return match.group(1).strip()
    return default


def bjcp_category(sections: dict[str, list[str]]) -> str:
    for lines in sections.values():
        for item in section_bullets(lines):
            if "BJCP Category:" in item:
                return item.split("BJCP Category:", 1)[1].strip()
    return ACTION_REQUIRED


def format_metric(amount: str, unit: str) -> str:
    value = float(amount)
    if unit.lower() == "kg" and value < 1:
        return f"{round(value * 1000):.0f} g"
    if unit.lower() == "kg":
        return f"{value:.2f} kg"
    return f"{value:.0f} g"


def parse_fermentables(lines: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    pattern = re.compile(r"^-\s*([0-9.]+)\s*lb\s*\(([0-9.]+)\s*(kg|g)\)\s+(.+)$", re.IGNORECASE)
    for raw in lines:
        match = pattern.match(raw.strip())
        if not match:
            continue
        pounds, metric_amount, metric_unit, name = match.groups()
        out.append(
            {
                "name": name.strip(),
                "amount": f"{float(pounds):.2f} lb ({format_metric(metric_amount, metric_unit)})",
                "notes": "",
            }
        )
    return out


def clean_hop_name(text: str) -> tuple[str, str]:
    match = re.match(r"(.+?)\s*\(([0-9.]+)%\)\s*$", text.strip())
    if match:
        return match.group(1).strip(), match.group(2)
    return text.strip(), "-"


def normalize_hop_timing(text: str) -> str:
    timing = text.strip()
    lowered = timing.lower()
    if lowered in {"first wort", "first wort hop", "first wort hopping"}:
        return "FWH"
    if lowered.startswith("mash"):
        return "Mash"
    if lowered.startswith("dry hop"):
        return "Dry Hop"
    if lowered.startswith("0 min") or lowered.startswith("flameout") or lowered.startswith("hop stand"):
        return "0 min"
    match = re.search(r"(\d+)\s*min", lowered)
    if match:
        return f"{match.group(1)} min"
    return timing


def parse_hops(lines: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    pattern = re.compile(r"^-\s*([0-9.]+)\s*oz\s*\(([0-9.]+)\s*g\)\s+(.+?)\s+-\s+(.+)$", re.IGNORECASE)
    for raw in lines:
        match = pattern.match(raw.strip())
        if not match:
            continue
        ounces, grams, name_part, timing = match.groups()
        name, aa = clean_hop_name(name_part)
        out.append(
            {
                "timing": normalize_hop_timing(timing),
                "name": name,
                "amount": f"{float(ounces):.2f} oz ({round(float(grams))} g)",
                "grams": f"{round(float(grams))} g",
                "aa": aa,
                "purpose": timing.strip(),
            }
        )
    return out


def parse_yeast(lines: list[str]) -> list[str]:
    bullets = section_bullets(lines)
    return bullets or [ACTION_REQUIRED]


def parse_water(lines: list[str]) -> tuple[list[str], list[str]]:
    salts: list[str] = []
    ions: list[str] = []
    for item in section_bullets(lines):
        lowered = item.lower()
        if any(salt in lowered for salt in ("gypsum", "epsom", "calcium chloride", "baking soda", "salt")):
            salts.append(item)
        elif ":" in item and any(ion in lowered for ion in ("ca", "mg", "na", "so4", "cl", "hco3")):
            ions.append(item)
    return salts, ions


def extract_boil_minutes(hops: list[dict[str, str]], process_steps: list[str]) -> str:
    for step in process_steps:
        match = re.search(r"\bboil\s+(\d+)\s*minutes?", step, re.IGNORECASE)
        if match:
            return match.group(1)
    timed = [int(match.group(1)) for hop in hops if (match := re.match(r"(\d+)\s+min", hop["timing"]))]
    return str(max(timed)) if timed else "60"


def row(cells: list[str], class_name: str = "") -> str:
    class_attr = f' class="{class_name}"' if class_name else ""
    return f"<tr{class_attr}>" + "".join(cells) + "</tr>"


def td(value: str, class_name: str = "") -> str:
    class_attr = f' class="{class_name}"' if class_name else ""
    return f"<td{class_attr}>{value}</td>"


def th(value: str, class_name: str = "") -> str:
    class_attr = f' class="{class_name}"' if class_name else ""
    return f"<th{class_attr}>{value}</th>"


def action_note(items: list[str], fallback: str) -> str:
    if items:
        return "<br>".join(html.escape(item) for item in items)
    return f"<strong>{ACTION_REQUIRED}:</strong> {html.escape(fallback)}"


def render_brew_sheet(recipe_path: Path, sheet_path: Path, brew_date: str = "") -> tuple[str, list[str]]:
    title, sections = parse_sections(recipe_path.read_text(encoding="utf-8"))
    targets = find_section(sections, "TARGET PARAMETERS")
    fermentables = parse_fermentables(find_section(sections, "FERMENTABLES"))
    hops = parse_hops(find_section(sections, "HOPS"))
    yeast = parse_yeast(find_section(sections, "YEAST"))
    water_salts, water_ions = parse_water(find_section(sections, "WATER"))
    process_steps = numbered_steps(find_section(sections, "BREW DAY PROCESS", "PROCESS"))
    fermentation_steps = numbered_steps(find_section(sections, "FERMENTATION"))
    category = bjcp_category(sections)
    boil_minutes = extract_boil_minutes(hops, process_steps)
    packet_id = sheet_path.stem.replace("_brew_day_sheet", "").upper()

    missing: list[str] = []
    if not fermentables:
        missing.append("fermentables")
    if not hops:
        missing.append("hop schedule")
    if yeast == [ACTION_REQUIRED]:
        missing.append("yeast")
    if not water_salts and not water_ions:
        missing.append("water profile")
    if not process_steps:
        missing.append("brew day process")
    if not fermentation_steps:
        missing.append("fermentation schedule")

    grain_rows = "".join(
        row(
            [
                td(html.escape(item["name"])),
                td(html.escape(item["amount"]), "right"),
                td(html.escape(item["notes"] or "Weigh separately")),
                td(checkbox(), "center"),
            ]
        )
        for item in fermentables
    ) or row([td(f"<strong>{ACTION_REQUIRED}</strong>"), td("", "right"), td("Add fermentables from recipe"), td(checkbox(), "center")])

    hop_rows = "".join(
        row(
            [
                td(html.escape(hop["timing"])),
                td(html.escape(hop["name"])),
                td(html.escape(hop["amount"]), "right"),
                td(html.escape(hop["aa"])),
                td(html.escape(hop["purpose"])),
                td(checkbox(), "center"),
            ]
        )
        for hop in hops
    ) or row([td(ACTION_REQUIRED), td("Hop schedule"), td("", "right"), td("-"), td("Add hop schedule from recipe"), td(checkbox(), "center")])

    boil_rows = "".join(
        row(
            [
                td(html.escape(hop["timing"]), "bold" if hop["timing"] in {"FWH", "0 min"} else ""),
                td(f"{html.escape(hop['name'])} {html.escape(hop['amount'])}"),
                td(html.escape(hop["purpose"])),
                td(checkbox(), "center"),
            ],
            "highlight-row" if hop["timing"] in {"FWH", "0 min"} else "",
        )
        for hop in hops
        if hop["timing"] != "Dry Hop"
    ) or row([td(ACTION_REQUIRED, "bold"), td("Add boil schedule"), td("Recipe did not contain timed hop additions"), td(checkbox(), "center")])

    mash_rows = "".join(
        row([td(f"Step {idx}"), td(html.escape(step)), td(""), td(checkbox(), "center"), td(""), td("")])
        for idx, step in enumerate(process_steps[:8], start=1)
    ) or row([td(ACTION_REQUIRED), td("Mash schedule missing"), td(""), td(checkbox(), "center"), td("Add mash schedule before brew day"), td("")])

    fermentation_rows = "".join(
        row(
            [
                td(f"D+{idx - 1}"),
                td(str(idx - 1)),
                td(""),
                td(""),
                td(html.escape(step)),
                td(""),
            ]
        )
        for idx, step in enumerate(fermentation_steps[:10], start=1)
    ) or row([td(ACTION_REQUIRED), td(""), td(""), td(""), td("Add fermentation schedule"), td("")])

    brew_date_field = brew_date or '<span class="blank"></span>'
    schedule_anchor = (
        f'<p class="small" style="margin-bottom:4px;"><strong>Schedule anchor:</strong> Brew day assumed <strong>{brew_date}</strong>. Record actual pitch timestamp and adjust if brew day shifts.</p>'
        if brew_date
        else '<p class="small" style="margin-bottom:4px;"><strong>Schedule anchor:</strong> Planning sheet. Add brew date before execution.</p>'
    )

    yeast_summary = "<br>".join(html.escape(item) for item in yeast)
    water_summary = action_note(water_salts + water_ions, "Add water profile, salts, and acid strategy.")
    style = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; line-height: 1.3; color: #1a1a1a; padding: 0.5in; }
  h1 { font-size: 16pt; font-weight: 700; border-bottom: 2.5px solid #1a1a1a; padding-bottom: 3px; margin-bottom: 3px; }
  h2 { font-size: 10.5pt; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; border-bottom: 1.5px solid #555; padding-bottom: 1px; margin-top: 10px; margin-bottom: 4px; }
  h3 { font-size: 9pt; font-weight: 700; margin-top: 6px; margin-bottom: 2px; }
  .header-row { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; }
  .subtitle { font-size: 9pt; color: #444; font-style: italic; }
  .info-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px 16px; margin-bottom: 10px; font-size: 8.5pt; }
  .info-grid .field { display: flex; gap: 6px; align-items: flex-end; min-height: 22px; }
  .info-grid .label { font-weight: 600; white-space: nowrap; }
  .blank { border-bottom: 1px solid #777; flex: 1; min-width: 140px; min-height: 16px; display: inline-block; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 5px; font-size: 8.5pt; }
  th { background: #e8e8e8; font-weight: 700; text-align: left; padding: 2px 4px; border: 1px solid #999; font-size: 7.5pt; text-transform: uppercase; letter-spacing: 0.3px; }
  td { padding: 2px 4px; border: 1px solid #bbb; vertical-align: top; }
  .center { text-align: center; }
  .right { text-align: right; }
  .bold { font-weight: 700; }
  .small { font-size: 7.5pt; color: #555; }
  .highlight-row { background: #f5f5dc; }
  .critical { font-weight: 700; color: #b00; }
  .check-col { width: 24px; text-align: center; }
  .actual-col { width: 90px; }
  .checkbox { display: inline-block; width: 10px; height: 10px; border: 1.5px solid #333; vertical-align: middle; }
  .blank-sm { border-bottom: 1px solid #999; display: inline-block; min-width: 45px; }
  .blank-md { border-bottom: 1px solid #999; display: inline-block; min-width: 80px; }
  .alert-box { border: 1.5px solid #b00; padding: 3px 6px; margin: 4px 0; font-size: 8pt; }
  .alert-box .alert-title { font-weight: 700; text-transform: uppercase; font-size: 7.5pt; color: #b00; }
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 16px; }
  .three-col { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 2px 10px; }
  .notes-area { border: 1px solid #bbb; min-height: 80px; padding: 3px; margin-bottom: 4px; }
  .page { page-break-after: always; position: relative; min-height: 10.1in; padding-bottom: 0.28in; }
  .page:last-child { page-break-after: auto; }
  .page-footer { position: absolute; left: 0; right: 0; bottom: 0; padding-top: 4px; border-top: 1px solid #bbb; font-size: 7.5pt; color: #555; text-align: right; }
  @page { margin: 0.4in 0.5in; size: letter; }
  @media print { body { padding: 0; font-size: 8.5pt; } h1 { font-size: 14pt; } h2 { font-size: 9.5pt; margin-top: 7px; margin-bottom: 3px; } table { font-size: 8pt; margin-bottom: 4px; break-inside: avoid; } th { font-size: 7pt; padding: 1.5px 3px; } td { padding: 1.5px 3px; } .small { font-size: 7pt; } .page { min-height: auto; padding-bottom: 0.22in; } .page-footer { font-size: 7pt; padding-top: 3px; } }
"""
    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{html.escape(title)} Brew Day Sheet</title>
<style>{style}</style>
</head>
<body>
<section class="page">
  <div class="header-row">
    <h1>{html.escape(title)}</h1>
    <span class="subtitle">BJCP {html.escape(category)}</span>
  </div>
  <div class="info-grid" style="margin-top:4px;">
    <div class="field"><span class="label">Date:</span> {brew_date_field}</div>
    <div class="field"><span class="label">System:</span> <span>ACTION REQUIRED</span></div>
    <div class="field"><span class="label">Fermenter:</span> <span>ACTION REQUIRED</span></div>
  </div>
  <h2>Target Window</h2>
  <table>
    <tr>{th("Parameter")}{th("Target")}{th("Actual", "actual-col")}{th("Parameter")}{th("Target")}</tr>
    {row([td("OG", "bold"), td(html.escape(target_value(targets, "OG"))), td(""), td("IBU", "bold"), td(html.escape(target_value(targets, "IBU", target_value(targets, "Bitterness"))))])}
    {row([td("FG", "bold"), td(html.escape(target_value(targets, "FG"))), td(""), td("Color", "bold"), td(html.escape(target_value(targets, "Color", target_value(targets, "SRM"))))])}
    {row([td("ABV", "bold"), td(html.escape(target_value(targets, "ABV"))), td(""), td("Mash pH", "bold"), td(html.escape(target_value(targets, "Mash pH (room temp)", target_value(targets, "Mash pH"))))])}
    {row([td("Style", "bold"), td(html.escape(category)), td(""), td("Batch", "bold"), td(ACTION_REQUIRED)])}
  </table>
  <div class="alert-box"><span class="alert-title">Packet Gate:</span> Resolve every ACTION REQUIRED field before brew day.</div>
  <div class="two-col">
    <div>
      <h2>Grain Bill</h2>
      <table>
        <tr>{th("Grain")}{th("Amount", "right")}{th("Notes")}{th("&check;", "check-col")}</tr>
        {grain_rows}
      </table>
    </div>
    <div>
      <h2>Water Chemistry</h2>
      <p class="small">{water_summary}</p>
    </div>
  </div>
  <h2>Hop Schedule</h2>
  <table>
    <tr>{th("Timing")}{th("Variety")}{th("Amount", "right")}{th("AA%")}{th("Purpose")}{th("&check;", "check-col")}</tr>
    {hop_rows}
  </table>
  <h2>Yeast and Pitch Plan</h2>
  <table>
    {row([td("Yeast", "bold"), td(yeast_summary)])}
    {row([td("Source / generation", "bold"), td(ACTION_REQUIRED)])}
    {row([td("Starter or pitch method", "bold"), td(ACTION_REQUIRED)])}
    {row([td("Pitch temp", "bold"), td(ACTION_REQUIRED)])}
  </table>
  <div class="page-footer">{html.escape(packet_id)} | Page 1 of 3</div>
</section>
<section class="page">
  <div class="header-row"><h1 style="font-size:13pt; border-bottom-width:2px;">{html.escape(title)}</h1><span class="subtitle">Brew Day Execution</span></div>
  <h2>Pre-Brew QC</h2>
  <div class="three-col" style="font-size:8pt;">
    <div>{checkbox()} pH meter calibrated</div>
    <div>{checkbox()} Thermometer verified</div>
    <div>{checkbox()} All ingredient weights staged</div>
    <div>{checkbox()} Fermenter and transfer lines sanitized</div>
    <div>{checkbox()} Yeast source confirmed</div>
    <div>{checkbox()} Water ready</div>
  </div>
  <h2>0. Yeast Prep Checklist</h2>
  <table>
    {row([td(ACTION_REQUIRED, "bold"), td("Confirm yeast source, generation, pitch rate, and starter/direct-pitch method."), td(checkbox(), "center")])}
  </table>
  <h2>1. Water Prep Checklist</h2>
  <table>
    {row([td("Water and salts"), td(water_summary), td(checkbox(), "center")])}
    {row([td("Mash pH"), td("Measure 10-15 min after mash-in; adjust only after measured pH."), td(checkbox(), "center")])}
  </table>
  <h2>2. Mash Log</h2>
  <table>
    <tr>{th("Step")}{th("Target")}{th("Actual")}{th("&check;", "check-col")}{th("Notes")}{th("Time")}</tr>
    {mash_rows}
  </table>
  <h2>Volume And Gravity Checks</h2>
  <table>
    <tr>{th("Checkpoint")}{th("Target")}{th("Actual")}{th("Notes")}</tr>
    {row([td("Pre-boil Volume", "bold"), td(ACTION_REQUIRED), td(""), td("")])}
    {row([td("Pre-boil Gravity", "bold"), td(ACTION_REQUIRED), td(""), td("")])}
    {row([td("Post-boil Volume", "bold"), td(ACTION_REQUIRED), td(""), td("")])}
    {row([td("Post-boil Gravity", "bold"), td(html.escape(target_value(targets, "OG"))), td(""), td("")])}
  </table>
  <h2>3. Boil Hop Additions ({html.escape(boil_minutes)} Minutes)</h2>
  <table>
    <tr>{th("Left")}{th("Action")}{th("Notes")}{th("&check;", "check-col")}</tr>
    {boil_rows}
  </table>
  <h2>4. Chill, Transfer, and Pitch</h2>
  <table>
    <tr>{th("Pitch item")}{th("Checklist / Target")}{th("Actual")}{th("Notes")}</tr>
    {row([td("Wort temp at pitch"), td(ACTION_REQUIRED), td('<span class="blank-md"></span> F'), td("")])}
    {row([td("Pitch date/time"), td("Track exact timestamp"), td('<span class="blank-md"></span>'), td("")])}
    {row([td("Yeast generation pitched"), td(ACTION_REQUIRED), td('<span class="blank-md"></span>'), td("Source batch/date if repitch")])}
  </table>
  <div class="page-footer">{html.escape(packet_id)} | Page 2 of 3</div>
</section>
<section class="page">
  <div class="header-row"><h1 style="font-size:13pt; border-bottom-width:2px;">{html.escape(title)}</h1><span class="subtitle">Fermentation and Packaging</span></div>
  {schedule_anchor}
  <h2>5. Fermentation Log</h2>
  <table>
    <tr>{th("Date/Time")}{th("Day")}{th("Temp")}{th("Gravity")}{th("Action")}{th("Notes")}</tr>
    {fermentation_rows}
  </table>
  <h2>6. Packaging</h2>
  <table>
    <tr>{th("Packaging Record")}{th("Target")}{th("Actual", "actual-col")}{th("Notes")}</tr>
    {row([td("Package Date", "bold"), td("When beer is fully clean and stable"), td(""), td("")])}
    {row([td("FG at Packaging", "bold"), td(html.escape(target_value(targets, "FG"))), td(""), td("")])}
    {row([td("Carbonation", "bold"), td(ACTION_REQUIRED), td(""), td("Record PSI/temp or priming details")])}
  </table>
  <h2>Brew Notes</h2>
  <div class="notes-area"></div>
  <div class="page-footer">{html.escape(packet_id)} | Page 3 of 3</div>
</section>
</body>
</html>
"""
    return document, missing


def resolve_sheet_path(recipe_path: Path, brew_date: str) -> tuple[str, Path]:
    base = derive_sheet_base(recipe_path)
    if brew_date:
        return base, ARCHIVE_SHEETS_DIR / f"{base}_brew_day_sheet_{brew_date}.html"
    return base, SHEETS_DIR / f"{base}_brew_day_sheet.html"


def run_command(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def run_prepare(recipe_path: Path, brew_date: str, record_history: bool, verbose: bool) -> int:
    cmd = [sys.executable, "tools/prepare_brew.py", "--recipe", recipe_path.relative_to(ROOT).as_posix(), "--date", brew_date]
    if record_history:
        cmd.append("--record-history")
    rc, output = run_command(cmd)
    if rc != 0:
        print("BREW_PACKET_NEEDS_ATTENTION")
        print(output)
        return rc
    if output and verbose:
        print(output)
    return 0


def build_packet(args: argparse.Namespace) -> int:
    brew_date = args.date
    if brew_date:
        dt.date.fromisoformat(brew_date)

    recipe_path = resolve_recipe(args.recipe)
    recipe_print_path = render_one(recipe_path, "")
    base, sheet_path = resolve_sheet_path(recipe_path, brew_date)
    prepared_existing_sheet = False

    if brew_date:
        undated_path = SHEETS_DIR / f"{base}_brew_day_sheet.html"
        dated_path = ARCHIVE_SHEETS_DIR / f"{base}_brew_day_sheet_{brew_date}.html"
        if not dated_path.exists() and undated_path.exists():
            rc = run_prepare(recipe_path, brew_date, args.record_history, args.verbose)
            if rc != 0:
                return rc
            prepared_existing_sheet = True
        sheet_path = dated_path

    created_sheet = False
    missing_inputs: list[str] = []
    if sheet_path.exists() and not args.force:
        pass
    else:
        if sheet_path.exists() and args.force:
            action = "updated"
        else:
            action = "created"
        sheet_path.parent.mkdir(parents=True, exist_ok=True)
        document, missing = render_brew_sheet(recipe_path, sheet_path, brew_date)
        missing_inputs = missing
        sheet_path.write_text(document, encoding="utf-8")
        created_sheet = True
        print(f"BREW_SHEET_{action.upper()} {sheet_path.relative_to(ROOT).as_posix()}")
        if missing:
            print("MISSING_INPUTS " + ", ".join(missing))

    if brew_date and not prepared_existing_sheet:
        rc = run_prepare(recipe_path, brew_date, args.record_history, args.verbose)
        if rc != 0:
            return rc

    failures: list[str] = []
    for problem in check_recipe_html(recipe_print_path):
        failures.append(f"{recipe_print_path.relative_to(ROOT)}: {problem}")
    for problem in check_brew_sheet(sheet_path):
        failures.append(f"{sheet_path.relative_to(ROOT)}: {problem}")
    if missing_inputs:
        failures.append("missing imported-recipe details: " + ", ".join(missing_inputs))

    sync_cmd = [
        sys.executable,
        "tools/validate_recipe_brewsheet_sync.py",
        recipe_path.relative_to(ROOT).as_posix(),
        "--sheet",
        sheet_path.relative_to(ROOT).as_posix(),
    ]
    rc, output = run_command(sync_cmd)
    if rc != 0:
        failures.append(output or "recipe/brew-sheet sync failed")

    beerxml_path = resolve_beerxml(recipe_path)
    print("")
    print("BREW PACKET")
    print(f"Recipe:       {recipe_path.relative_to(ROOT).as_posix()}")
    print(f"Recipe print: {recipe_print_path.relative_to(ROOT).as_posix()}")
    print(f"Brew sheet:   {sheet_path.relative_to(ROOT).as_posix()}")
    if beerxml_path:
        print(f"BeerXML:      {beerxml_path.relative_to(ROOT).as_posix()}")
    print(f"Sheet base:   {base}")
    print(f"Sheet action: {'created/updated' if created_sheet else 'reused existing'}")

    if failures:
        print("")
        print("BREW_PACKET_NEEDS_ATTENTION")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("")
    print("BREW_PACKET_READY")
    print("- print readability: OK")
    print("- recipe/brew-sheet sync: OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a printable recipe + brew-day sheet packet")
    parser.add_argument("--recipe", required=True, help="Recipe path, file stem, or slug token")
    parser.add_argument("--date", default="", help="Optional brew date in YYYY-MM-DD; creates/uses a dated sheet")
    parser.add_argument("--force", action="store_true", help="Regenerate the brew sheet if it already exists")
    parser.add_argument("--record-history", action="store_true", help="Append a prepare_brew event when --date is used")
    parser.add_argument("--verbose", action="store_true", help="Show wrapped command output")
    return parser


def main() -> int:
    try:
        return build_packet(build_parser().parse_args())
    except Exception as exc:
        print("BREW_PACKET_FAILED")
        print(f"- {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
