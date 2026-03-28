#!/usr/bin/env python3
"""
Validate hop AA values in recipe artifacts against libraries/inventory/stock.json.

Guardrail intent:
- stock.json is the single source-of-truth for hop alpha-acid values.
- recipe/log/printable-html/xml artifacts must stay in sync with stock.json.
- lot-specific alpha values are allowed when listed in lot_alpha_acid_pct.

Exit code:
  0 = all checks passed
  1 = mismatch(es) found
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK_FILE = ROOT / "libraries" / "inventory" / "stock.json"
ACTIVE_ARTIFACTS_FILE = ROOT / "project_control" / "ACTIVE_ARTIFACTS.json"

SCAN_ROOTS = [
    ROOT / "recipes",
    ROOT / "batch_logs",
    ROOT / "brewing" / "brew_day_sheets",
    ROOT / "html",  # legacy location kept for backward compatibility
    ROOT / "recipes" / "beer_xml_exports",
]
ALLOWED_SUFFIXES = {".md", ".html", ".xml"}
EXCLUDED_DIR_NAMES = {"beer_xml_imports"}
EXCLUDED_FILE_PREFIXES = ("orig_",)

# Generic "Hop (X.X% AA)" pattern used in md/html text.
PATTERN_AA_INLINE = re.compile(
    r"(?P<hop>[A-Za-z0-9][A-Za-z0-9 '&\-/\.]{1,60})\s*"
    r"\((?P<aa>\d+(?:\.\d+)?)% AA\)",
    re.IGNORECASE,
)

# Copper brew-day sheet has hop name and AA in separate table columns.
PATTERN_AA_HTML_ROW = re.compile(
    r"<tr><td>[^<]*</td><td>(?P<hop>Target|Northdown|Challenger)[^<]*</td>"
    r"<td[^>]*>[^<]*</td><td>(?P<aa>\d+(?:\.\d+)?)</td>",
    re.IGNORECASE,
)

# BeerXML hop block pattern.
PATTERN_AA_XML_HOP = re.compile(
    r"<HOP>.*?<NAME>(?P<hop>[^<]+)</NAME>.*?<ALPHA>(?P<aa>\d+(?:\.\d+)?)</ALPHA>.*?</HOP>",
    re.IGNORECASE | re.DOTALL,
)


def canonicalize_name(raw: str) -> str:
    normalized = unicodedata.normalize("NFKD", raw)
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower().replace("%", " ").replace("_", " ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def normalize_hop_name(raw: str, alias_to_hop_id: dict[str, str]) -> str | None:
    key = canonicalize_name(raw)
    return alias_to_hop_id.get(key)


def approx_equal(a: float, b: float, tol: float = 0.01) -> bool:
    return abs(a - b) <= tol


def build_hop_aliases(stock: dict) -> tuple[dict[str, list[float]], dict[str, str]]:
    hop_allowed_aa: dict[str, list[float]] = {}
    alias_to_hop_id: dict[str, str] = {}

    for item in stock.get("items", []):
        if item.get("category") != "hop":
            continue

        hop_id = item.get("id")
        if not hop_id:
            continue

        allowed: list[float] = []
        primary = item.get("alpha_acid_pct")
        if primary is not None:
            allowed.append(float(primary))
        for v in item.get("lot_alpha_acid_pct", []) or []:
            if v is not None:
                allowed.append(float(v))

        deduped = sorted({round(v, 4) for v in allowed})
        if deduped:
            hop_allowed_aa[hop_id] = deduped

        aliases = {
            canonicalize_name(hop_id),
            canonicalize_name(hop_id.replace("_", " ")),
            canonicalize_name(item.get("name", "")),
        }
        for alias in aliases:
            if alias:
                alias_to_hop_id[alias] = hop_id

    # Human-facing shorthand aliases used in recipes/logs.
    manual_aliases = {
        "challenger": "challenger_uk",
        "uk challenger": "challenger_uk",
        "target": "target",
        "uk target": "target",
        "hallertau mittelfruh": "hallertauer",
        "hallertau mittelfruh hop": "hallertauer",
        "hallertau mittelfruh pelleted": "hallertauer",
    }
    for alias, hop_id in manual_aliases.items():
        if hop_id in alias_to_hop_id.values():
            alias_to_hop_id[canonicalize_name(alias)] = hop_id

    return hop_allowed_aa, alias_to_hop_id


def load_stock_hops() -> tuple[dict[str, list[float]], dict[str, str]]:
    if not STOCK_FILE.exists():
        raise FileNotFoundError(f"Missing stock file: {STOCK_FILE}")
    stock = json.loads(STOCK_FILE.read_text(encoding="utf-8"))
    return build_hop_aliases(stock)


def load_active_hop_files() -> list[Path] | None:
    if not ACTIVE_ARTIFACTS_FILE.exists():
        return None
    payload = json.loads(ACTIVE_ARTIFACTS_FILE.read_text(encoding="utf-8"))
    files = []
    for rel_path in payload.get("hop_aa_active_files", []):
        path = ROOT / rel_path
        if path.exists():
            files.append(path)
    return sorted(set(files))


def format_allowed(values: list[float]) -> str:
    return ", ".join(f"{v:g}" for v in values)


def check_text_inline(
    path: Path,
    text: str,
    hop_allowed_aa: dict[str, list[float]],
    alias_to_hop_id: dict[str, str],
) -> set[str]:
    errors: set[str] = set()
    for m in PATTERN_AA_INLINE.finditer(text):
        hop_raw = m.group("hop")
        aa_text = float(m.group("aa"))
        hop_id = normalize_hop_name(hop_raw, alias_to_hop_id)
        if not hop_id:
            continue
        allowed = hop_allowed_aa.get(hop_id, [])
        if not allowed:
            errors.add(f"{path}: hop '{hop_raw}' not found in stock.json")
            continue
        if not any(approx_equal(aa_text, aa_stock) for aa_stock in allowed):
            errors.add(
                f"{path}: {hop_raw} inline AA={aa_text:g} but stock.json allows [{format_allowed(allowed)}]"
            )
    return errors


def check_html_table(
    path: Path,
    text: str,
    hop_allowed_aa: dict[str, list[float]],
    alias_to_hop_id: dict[str, str],
) -> set[str]:
    errors: set[str] = set()
    for m in PATTERN_AA_HTML_ROW.finditer(text):
        hop_raw = m.group("hop")
        aa_text = float(m.group("aa"))
        hop_id = normalize_hop_name(hop_raw, alias_to_hop_id)
        if not hop_id:
            continue
        allowed = hop_allowed_aa.get(hop_id, [])
        if not allowed:
            errors.add(f"{path}: hop '{hop_raw}' not found in stock.json")
            continue
        if not any(approx_equal(aa_text, aa_stock) for aa_stock in allowed):
            errors.add(
                f"{path}: {hop_raw} table AA={aa_text:g} but stock.json allows [{format_allowed(allowed)}]"
            )
    return errors


def check_xml(
    path: Path,
    text: str,
    hop_allowed_aa: dict[str, list[float]],
    alias_to_hop_id: dict[str, str],
) -> set[str]:
    errors: set[str] = set()
    for m in PATTERN_AA_XML_HOP.finditer(text):
        hop_raw = m.group("hop")
        aa_text = float(m.group("aa"))
        hop_id = normalize_hop_name(hop_raw, alias_to_hop_id)
        if not hop_id:
            continue
        allowed = hop_allowed_aa.get(hop_id, [])
        if not allowed:
            errors.add(f"{path}: hop '{hop_raw}' not found in stock.json")
            continue
        if not any(approx_equal(aa_text, aa_stock) for aa_stock in allowed):
            errors.add(
                f"{path}: {hop_raw} XML AA={aa_text:g} but stock.json allows [{format_allowed(allowed)}]"
            )
    return errors


def find_target_files() -> list[Path]:
    found: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in ALLOWED_SUFFIXES:
                continue
            if path.name.startswith(EXCLUDED_FILE_PREFIXES):
                continue
            if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
                continue
            found.append(path)
    return sorted(set(found))


def main() -> int:
    hop_allowed_aa, alias_to_hop_id = load_stock_hops()
    errors: set[str] = set()
    target_files = load_active_hop_files() or find_target_files()
    if not target_files:
        print("AA_SYNC_FAILED")
        print("- No target files found to validate.")
        return 1

    for path in target_files:
        text = path.read_text(encoding="utf-8")
        errors.update(check_text_inline(path, text, hop_allowed_aa, alias_to_hop_id))

        if path.suffix == ".html":
            errors.update(check_html_table(path, text, hop_allowed_aa, alias_to_hop_id))
        if path.suffix == ".xml":
            errors.update(check_xml(path, text, hop_allowed_aa, alias_to_hop_id))

    if errors:
        print("AA_SYNC_FAILED")
        for e in sorted(errors):
            print(f"- {e}")
        print("\nFix values in artifacts or update stock.json first, then re-run validator.")
        return 1

    print("AA_SYNC_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
