#!/usr/bin/env python3
"""Inventory CLI for brew-assistant.

Phase 1:
  - Decrement stock when a recipe is brewed.

Phase 2:
  - Suggest brewable styles from on-hand ingredients.

Phase 3:
  - Suggest "Garbage Beer" experimental concepts from leftovers.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
INV_DIR = ROOT / "libraries" / "inventory"
STOCK_FILE = INV_DIR / "stock.json"
RECIPE_USAGE_FILE = INV_DIR / "recipe_usage.json"
BREW_HISTORY_FILE = INV_DIR / "brew_history.json"
TEMPLATES_FILE = INV_DIR / "style_option_templates.json"


WEIGHT_FACTORS_TO_G = {
    "g": 1.0,
    "kg": 1000.0,
    "oz": 28.349523125,
    "lb": 453.59237,
}

VOLUME_FACTORS_TO_ML = {
    "ml": 1.0,
    "l": 1000.0,
    "floz": 29.5735295625,
    "gal": 3785.411784,
}


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def item_indexes(stock: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    name_to_id: Dict[str, str] = {}
    for item in stock.get("items", []):
        by_id[item["id"]] = item
        name_to_id[normalize(item["name"])] = item["id"]
    return by_id, name_to_id


def convert(amount: float, from_unit: str, to_unit: str) -> float:
    from_unit = from_unit.lower()
    to_unit = to_unit.lower()
    if from_unit == to_unit:
        return amount

    if from_unit in WEIGHT_FACTORS_TO_G and to_unit in WEIGHT_FACTORS_TO_G:
        g = amount * WEIGHT_FACTORS_TO_G[from_unit]
        return g / WEIGHT_FACTORS_TO_G[to_unit]

    if from_unit in VOLUME_FACTORS_TO_ML and to_unit in VOLUME_FACTORS_TO_ML:
        ml = amount * VOLUME_FACTORS_TO_ML[from_unit]
        return ml / VOLUME_FACTORS_TO_ML[to_unit]

    if from_unit == "count" and to_unit == "count":
        return amount

    raise ValueError(f"Incompatible units: {from_unit} -> {to_unit}")


def find_recipe(recipe_usage: Dict[str, Any], token: str) -> Dict[str, Any]:
    token_n = normalize(token)
    for recipe in recipe_usage.get("recipes", []):
        if normalize(recipe["id"]) == token_n:
            return recipe
        if normalize(recipe.get("display_name", "")) == token_n:
            return recipe
        for alias in recipe.get("aliases", []):
            if normalize(alias) == token_n:
                return recipe
    raise ValueError(f"Unknown recipe: {token}")


def print_stock(stock: Dict[str, Any]) -> None:
    rows = sorted(stock.get("items", []), key=lambda x: (x.get("category", ""), x.get("name", "")))
    print("Inventory")
    print("=" * 80)
    print(f"{'id':26} {'name':32} {'on_hand':>10} {'unit':>6}")
    print("-" * 80)
    for item in rows:
        print(f"{item['id'][:26]:26} {item['name'][:32]:32} {item['on_hand']:10.2f} {item['unit']:>6}")


def append_history_event(history: Dict[str, Any], event: Dict[str, Any]) -> None:
    history.setdefault("events", []).append(event)


def cmd_brew(args: argparse.Namespace) -> int:
    stock = load_json(STOCK_FILE)
    usage = load_json(RECIPE_USAGE_FILE)
    history = load_json(BREW_HISTORY_FILE)
    by_id, _ = item_indexes(stock)

    recipe = find_recipe(usage, args.recipe)
    batches = float(args.batches)
    now = dt.datetime.now(dt.timezone.utc).isoformat()

    print(f"Brew event: {recipe['display_name']} x {batches:g}")
    shortages = []
    deltas = []

    for line in recipe.get("consumption", []):
        if line.get("optional", False) and not args.include_optional:
            continue
        item_id = line["item_id"]
        if item_id not in by_id:
            raise ValueError(f"Item id '{item_id}' in recipe usage not found in stock.json")

        item = by_id[item_id]
        qty = float(line["amount"]) * batches
        qty_in_item_unit = convert(qty, line["unit"], item["unit"])
        before = float(item.get("on_hand", 0.0))
        after = before - qty_in_item_unit
        item["on_hand"] = round(after, 6)

        if after < 0:
            shortages.append(
                {
                    "item_id": item_id,
                    "name": item["name"],
                    "shortfall": abs(after),
                    "unit": item["unit"],
                }
            )
        deltas.append(
            {
                "item_id": item_id,
                "name": item["name"],
                "delta": -qty_in_item_unit,
                "unit": item["unit"],
            }
        )

    append_history_event(
        history,
        {
            "timestamp_utc": now,
            "type": "brew",
            "recipe_id": recipe["id"],
            "recipe_name": recipe["display_name"],
            "style_key": recipe.get("style_key"),
            "batches": batches,
            "include_optional": bool(args.include_optional),
            "deltas": deltas,
        },
    )

    save_json(STOCK_FILE, stock)
    save_json(BREW_HISTORY_FILE, history)

    for row in deltas:
        print(f"  {row['name']}: {row['delta']:.2f} {row['unit']}")

    if shortages:
        print("\nWARNING: negative inventory after brew:")
        for s in shortages:
            print(f"  {s['name']}: short by {s['shortfall']:.2f} {s['unit']}")
        return 2
    return 0


def resolve_item(stock: Dict[str, Any], item_ref: str) -> Dict[str, Any]:
    by_id, name_to_id = item_indexes(stock)
    if item_ref in by_id:
        return by_id[item_ref]
    key = normalize(item_ref)
    if key in name_to_id:
        return by_id[name_to_id[key]]
    raise ValueError(f"Unknown item: {item_ref}")


def cmd_restock(args: argparse.Namespace) -> int:
    stock = load_json(STOCK_FILE)
    history = load_json(BREW_HISTORY_FILE)
    item = resolve_item(stock, args.item)
    qty = convert(float(args.amount), args.unit, item["unit"])
    item["on_hand"] = round(float(item.get("on_hand", 0.0)) + qty, 6)

    append_history_event(
        history,
        {
            "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "type": "restock",
            "item_id": item["id"],
            "item_name": item["name"],
            "delta": qty,
            "unit": item["unit"],
            "note": args.note or "",
        },
    )
    save_json(STOCK_FILE, stock)
    save_json(BREW_HISTORY_FILE, history)
    print(f"Restocked {item['name']}: +{qty:.2f} {item['unit']}. New on_hand={item['on_hand']:.2f}")
    return 0


def evaluate_template(stock: Dict[str, Any], template: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    by_id, _ = item_indexes(stock)
    chosen = []
    capacity = math.inf
    for req in template.get("requirements", []):
        best: Optional[Tuple[str, float, str]] = None
        for item_id in req.get("item_ids", []):
            if item_id not in by_id:
                continue
            item = by_id[item_id]
            try:
                available = convert(float(item.get("on_hand", 0.0)), item["unit"], req["unit"])
            except ValueError:
                continue
            if best is None or available > best[1]:
                best = (item_id, available, item["name"])
        if best is None:
            return None
        req_amount = float(req["amount"])
        local_capacity = best[1] / req_amount if req_amount > 0 else 0
        capacity = min(capacity, local_capacity)
        chosen.append(
            {
                "label": req.get("label", "requirement"),
                "item_id": best[0],
                "item_name": best[2],
                "required": req_amount,
                "required_unit": req["unit"],
                "available": best[1],
            }
        )
    max_batches = math.floor(capacity)
    if max_batches < 1:
        return None
    return {"template": template, "max_batches": max_batches, "chosen": chosen}


def brewed_style_keys(history: Dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for event in history.get("events", []):
        if event.get("type") == "brew" and event.get("style_key"):
            out.add(str(event["style_key"]))
    return out


def generate_name(template: Dict[str, Any]) -> str:
    seed = f"{template['id']}::{dt.date.today().isoformat()}"
    rng = random.Random(seed)
    p = rng.choice(template.get("name_prefixes", ["House"]))
    s = rng.choice(template.get("name_suffixes", ["Batch"]))
    return f"{p} {s}"


def cmd_options(args: argparse.Namespace) -> int:
    stock = load_json(STOCK_FILE)
    history = load_json(BREW_HISTORY_FILE)
    templates = load_json(TEMPLATES_FILE).get("templates", [])
    brewed = brewed_style_keys(history)

    candidates = []
    for t in templates:
        if args.exclude_brewed and t.get("style_key") in brewed:
            continue
        ev = evaluate_template(stock, t)
        if ev:
            candidates.append(ev)

    if not candidates:
        print("No brewable options found with current inventory.")
        return 1

    candidates.sort(key=lambda x: x["max_batches"], reverse=True)
    print("Possible beers from current inventory")
    print("=" * 80)
    for i, c in enumerate(candidates[: args.count], start=1):
        t = c["template"]
        print(f"{i}. {generate_name(t)}")
        print(f"   style: {t['style_name']} ({t['bjcp']})")
        print(f"   max batches now: {c['max_batches']}")
        print("   key constraints:")
        for req in c["chosen"]:
            print(
                f"   - {req['label']}: {req['item_name']} "
                f"({req['available']:.1f}/{req['required']:.1f} {req['required_unit']})"
            )
    return 0


def cmd_garbage(args: argparse.Namespace) -> int:
    stock = load_json(STOCK_FILE)
    items = stock.get("items", [])

    malts = [i for i in items if i.get("category") == "fermentable" and i.get("unit") == "g" and i.get("on_hand", 0) > 0]
    hops = [i for i in items if i.get("category") == "hop" and i.get("unit") == "g" and i.get("on_hand", 0) > 0]
    yeasts = [i for i in items if i.get("category") == "yeast" and i.get("unit") == "count" and i.get("on_hand", 0) > 0]

    if not malts or not hops or not yeasts:
        print("Not enough inventory for Garbage Beer suggestions. Need malt + hops + yeast on hand.")
        return 1

    malts = sorted(malts, key=lambda x: x["on_hand"], reverse=True)
    hops = sorted(hops, key=lambda x: x["on_hand"], reverse=True)
    yeasts = sorted(yeasts, key=lambda x: x["on_hand"], reverse=True)

    prefixes = ["Garbage", "Late Night", "Parking Lot", "Afterparty", "Last Call", "Diner"]
    suffixes = ["Plate", "Special", "Chaos", "Remix", "Mashup", "Deluxe"]
    rng = random.Random(dt.date.today().isoformat())

    print("Garbage Beer concepts (34C Experimental)")
    print("=" * 80)
    for i in range(1, args.count + 1):
        base = malts[(i - 1) % len(malts)]
        specialty = malts[i % len(malts)] if len(malts) > 1 else base
        bitter = hops[(i - 1) % len(hops)]
        aroma = hops[i % len(hops)] if len(hops) > 1 else bitter
        yeast = yeasts[(i - 1) % len(yeasts)]
        name = f"{rng.choice(prefixes)} {rng.choice(suffixes)}"
        print(f"{i}. {name}")
        print("   category: 34C Experimental Beer")
        print(f"   concept: {base['name']} base + {specialty['name']} accent")
        print(f"   hops: {bitter['name']} bitterness, {aroma['name']} late/aroma")
        print(f"   yeast: {yeast['name']}")
        print("   note: Build to balanced gravity and keep process clean; let leftovers drive character.")
    return 0


def cmd_phrase(args: argparse.Namespace) -> int:
    phrase_n = normalize(args.text)
    if phrase_n.startswith("i brewed "):
        recipe_name = phrase_n.replace("i brewed ", "", 1).strip()
        return cmd_brew(
            argparse.Namespace(
                recipe=recipe_name,
                batches=1.0,
                include_optional=False,
            )
        )

    if "create a beer" in phrase_n and "haven t made before" in phrase_n:
        return cmd_options(argparse.Namespace(count=5, exclude_brewed=True))

    if "garbage beer" in phrase_n:
        return cmd_garbage(argparse.Namespace(count=3))

    print("Phrase not recognized. Try:")
    print('- "i brewed patient number 9"')
    print("- \"create a beer i haven't made before with the ingredients i have\"")
    print('- "garbage beer"')
    return 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Inventory CLI for Brew Assistant")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("stock", help="Show current stock")

    b = sub.add_parser("brew", help="Decrement stock for a brewed recipe")
    b.add_argument("--recipe", required=True, help="Recipe id/name/alias")
    b.add_argument("--batches", type=float, default=1.0, help="Batch multiplier")
    b.add_argument("--include-optional", action="store_true", help="Include optional recipe items")

    r = sub.add_parser("restock", help="Add inventory to stock")
    r.add_argument("--item", required=True, help="Item id or exact item name")
    r.add_argument("--amount", required=True, type=float, help="Amount to add")
    r.add_argument("--unit", required=True, help="Unit for amount (g, oz, lb, ml, l, count)")
    r.add_argument("--note", default="", help="Optional note for history")

    o = sub.add_parser("options", help="Suggest brewable options from stock")
    o.add_argument("--count", type=int, default=5, help="Number of options to show")
    o.add_argument("--exclude-brewed", action="store_true", default=True, help="Skip previously brewed style keys")

    g = sub.add_parser("garbage", help="Suggest Garbage Beer experimental concepts")
    g.add_argument("--count", type=int, default=3, help="Number of concepts")

    ph = sub.add_parser("phrase", help="Run phrase-based commands")
    ph.add_argument("text", help="Natural language phrase")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.cmd == "stock":
            print_stock(load_json(STOCK_FILE))
            return 0
        if args.cmd == "brew":
            return cmd_brew(args)
        if args.cmd == "restock":
            return cmd_restock(args)
        if args.cmd == "options":
            return cmd_options(args)
        if args.cmd == "garbage":
            return cmd_garbage(args)
        if args.cmd == "phrase":
            return cmd_phrase(args)
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
