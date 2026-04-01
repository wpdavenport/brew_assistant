#!/usr/bin/env python3
"""Provide hop lot-selection guidance for actual brew execution."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECIPES_DIR = ROOT / "recipes"
STOCK_FILE = ROOT / "libraries" / "inventory" / "stock.json"

RE_HOP_LINE = re.compile(r"^- ([0-9.]+) oz \(([0-9.]+) g\) (.+?) - (.+)$")
RE_HOP_SCHEDULE_LINE = re.compile(r"^- (.+?):\s+(.+?)\s+([0-9.]+) oz \(([0-9.]+) g\)(?:\s+at\s+([0-9.]+)% AA)?$", re.IGNORECASE)


def normalize_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def recipe_stem_candidates(stem: str) -> list[str]:
    candidates = [stem]
    candidates.append(re.sub(r"_clone_\d{1,2}[A-Z]$", "", stem))
    candidates.append(re.sub(r"_\d{1,2}[A-Z]$", "", stem))
    out: list[str] = []
    for value in candidates:
        if value and value not in out:
            out.append(value)
    return out


def resolve_recipe(token: str) -> Path:
    explicit = ROOT / token
    if explicit.exists() and explicit.suffix == ".md":
        return explicit.resolve()
    candidates = [
        path
        for path in RECIPES_DIR.rglob("*.md")
        if "historical" not in path.parts and "locked" not in path.parts and "in_development" not in path.parts
    ]
    token_n = normalize_token(token)
    exact = [path for path in candidates if normalize_token(path.stem) == token_n]
    if len(exact) == 1:
        return exact[0].resolve()
    stem_matches = []
    for path in candidates:
        for candidate in recipe_stem_candidates(path.stem):
            if normalize_token(candidate) == token_n:
                stem_matches.append(path)
                break
    stem_matches = sorted(set(stem_matches))
    if len(stem_matches) == 1:
        return stem_matches[0].resolve()
    raise ValueError(f"Could not resolve recipe from token: {token}")


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


def clean_hop_name(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", text).strip()


def parse_timing_bucket(timing: str) -> tuple[str, int]:
    timing_n = timing.strip().lower()
    if timing_n.startswith("first wort") or timing_n == "fwh":
        return "bittering", 90
    if timing_n.startswith("dry hop"):
        return "dry hop", -1
    zero_match = re.search(r"(^|[^0-9])0\s*min([^0-9]|$)", timing_n)
    if zero_match or "hop stand" in timing_n or "whirlpool" in timing_n or "flameout" in timing_n:
        return "aroma", 0
    minute_match = re.search(r"(\d+)\s*min", timing_n)
    if minute_match:
        minutes = int(minute_match.group(1))
        if minutes >= 30:
            return "bittering", minutes
        if minutes >= 10:
            return "flavor", minutes
        return "aroma", minutes
    return "unknown", -2


def parse_recipe_hops(recipe_path: Path) -> tuple[str, list[dict]]:
    title, sections = parse_markdown_sections(recipe_path.read_text(encoding="utf-8"))
    hops_section = find_section(sections, "HOPS")
    subsection = ""
    hops: list[dict] = []
    for raw in hops_section:
        line = raw.strip()
        if line.startswith("### "):
            subsection = line[4:].strip().lower()
            continue
        if not line.startswith("- "):
            continue
        schedule_match = RE_HOP_SCHEDULE_LINE.match(line)
        if schedule_match:
            timing = schedule_match.group(1).strip()
            name = clean_hop_name(schedule_match.group(2))
            bucket, minute_sort = parse_timing_bucket(timing)
            hops.append(
                {
                    "name": name,
                    "grams": float(schedule_match.group(4)),
                    "timing": timing,
                    "bucket": bucket,
                    "minute_sort": minute_sort,
                }
            )
            continue
        if subsection not in {"boil / whirlpool", "dry hop (clone-safe, not modern overkill)", "dry hop"}:
            continue
        if subsection.startswith("dry hop"):
            m = re.match(r"^- ([0-9.]+) oz \(([0-9.]+) g\) (.+)$", line)
            if not m:
                continue
            name = clean_hop_name(m.group(3))
            hops.append(
                {
                    "name": name,
                    "grams": float(m.group(2)),
                    "timing": "Dry Hop",
                    "bucket": "dry hop",
                    "minute_sort": -1,
                }
            )
            continue
        m = RE_HOP_LINE.match(line)
        if not m:
            continue
        name = clean_hop_name(m.group(3))
        timing = m.group(4).strip()
        bucket, minute_sort = parse_timing_bucket(timing)
        hops.append(
            {
                "name": name,
                "grams": float(m.group(2)),
                "timing": timing,
                "bucket": bucket,
                "minute_sort": minute_sort,
            }
        )
    return title, hops


def load_stock() -> dict:
    return json.loads(STOCK_FILE.read_text(encoding="utf-8"))


def stock_hop_by_name(name: str, stock: dict) -> dict | None:
    name_n = normalize_token(name)
    for item in stock.get("items", []):
        if item.get("category") != "hop":
            continue
        hay = [normalize_token(item.get("id", "")), normalize_token(item.get("name", ""))]
        if name_n in hay or any(name_n in token for token in hay):
            return item
    return None


def bucket_sort_key(bucket: str) -> int:
    order = {"bittering": 0, "flavor": 1, "aroma": 2, "dry hop": 3, "unknown": 4}
    return order.get(bucket, 9)


def build_guidance(recipe_path: Path) -> dict:
    title, hops = parse_recipe_hops(recipe_path)
    stock = load_stock()
    grouped: dict[str, list[dict]] = defaultdict(list)
    for hop in hops:
        grouped[hop["name"]].append(hop)

    hop_guidance: list[dict] = []
    for hop_name, additions in sorted(grouped.items(), key=lambda row: row[0].lower()):
        stock_item = stock_hop_by_name(hop_name, stock)
        lots = sorted({float(v) for v in ((stock_item or {}).get("lot_alpha_acid_pct") or [])})
        total_grams = round(sum(row["grams"] for row in additions), 1)
        entry = {
            "hop_name": hop_name,
            "on_hand_g": float((stock_item or {}).get("on_hand", 0.0)),
            "base_alpha_pct": (stock_item or {}).get("alpha_acid_pct"),
            "lot_alpha_pct": lots,
            "has_lot_choice": len(lots) > 1,
            "additions": sorted(additions, key=lambda row: (bucket_sort_key(row["bucket"]), -row["minute_sort"], row["timing"])),
            "total_grams": total_grams,
            "guidance": [],
            "warnings": [],
        }
        if not stock_item:
            entry["warnings"].append("No matching stock hop found.")
        elif not lots or len(lots) <= 1:
            entry["guidance"].append("Only one tracked AA lot. No lot-selection choice needed.")
        else:
            low = lots[0]
            high = lots[-1]
            bittering_g = round(sum(row["grams"] for row in additions if row["bucket"] == "bittering"), 1)
            flavor_g = round(sum(row["grams"] for row in additions if row["bucket"] == "flavor"), 1)
            aroma_g = round(sum(row["grams"] for row in additions if row["bucket"] == "aroma"), 1)
            dry_hop_g = round(sum(row["grams"] for row in additions if row["bucket"] == "dry hop"), 1)
            if bittering_g > 0:
                entry["guidance"].append(f"Prefer the lower-AA lot ({low:.1f}%) for bittering additions ({bittering_g:.1f} g total) when you have enough total quantity; early additions care least about freshness.")
            if flavor_g > 0:
                entry["guidance"].append(f"Prefer the higher-AA lot ({high:.1f}%) for flavor additions ({flavor_g:.1f} g total) to preserve the better lot where character still matters.")
            if aroma_g > 0:
                entry["guidance"].append(f"Prefer the higher-AA lot ({high:.1f}%) for aroma / whirlpool additions ({aroma_g:.1f} g total); preserve the better lot for late-hop expression.")
            if dry_hop_g > 0:
                entry["guidance"].append(f"Prefer the higher-AA lot ({high:.1f}%) for dry hop ({dry_hop_g:.1f} g total); lot character matters more there than bittering math.")
            entry["guidance"].append("If quantity becomes tight, spend the lower-AA lot first in early boil positions and keep the higher-AA lot for the latest additions you can preserve.")
        if stock_item and entry["on_hand_g"] + 1e-6 < total_grams:
            entry["warnings"].append(f"On hand {entry['on_hand_g']:.1f} g is short of recipe need {total_grams:.1f} g.")
        hop_guidance.append(entry)

    return {"title": title, "recipe": recipe_path.relative_to(ROOT).as_posix(), "hops": hop_guidance}


def render_text_report(payload: dict) -> str:
    lines = [
        "HOP LOT GUIDANCE",
        "=" * 80,
        payload["title"],
        payload["recipe"],
    ]
    if not payload["hops"]:
        lines.extend(["", "No hop additions parsed."])
        return "\n".join(lines)
    for hop in payload["hops"]:
        lines.extend(["", f"{hop['hop_name']}", "-" * 80])
        base = hop["base_alpha_pct"]
        if base is not None:
            lines.append(f"Tracked AA: {float(base):.1f}%")
        if hop["lot_alpha_pct"]:
            lines.append("Tracked lots: " + ", ".join(f"{value:.1f}%" for value in hop["lot_alpha_pct"]))
        lines.append(f"On hand: {hop['on_hand_g']:.1f} g")
        lines.append(f"Recipe need: {hop['total_grams']:.1f} g")
        lines.append("Additions:")
        for row in hop["additions"]:
            lines.append(f"- {row['grams']:.1f} g @ {row['timing']} [{row['bucket']}]")
        lines.append("Guidance:")
        for row in hop["guidance"] or ["No lot-selection guidance available."]:
            lines.append(f"- {row}")
        if hop["warnings"]:
            lines.append("Warnings:")
            for row in hop["warnings"]:
                lines.append(f"- {row}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Provide hop lot-selection guidance for a recipe")
    parser.add_argument("--recipe", required=True, help="Recipe path, file stem, or slug token")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    recipe_path = resolve_recipe(args.recipe)
    payload = build_guidance(recipe_path)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(render_text_report(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
