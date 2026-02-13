# Inventory Workflow

This folder powers three workflows:

1. Phase 1: decrement stock from a brewed recipe.
2. Phase 2: suggest not-yet-brewed beer options from on-hand inventory.
3. Phase 3: suggest "Garbage Beer" experimental concepts from leftovers.

## Files

- `stock.json`: current inventory on hand.
- `recipe_usage.json`: per-recipe ingredient consumption used to decrement stock.
- `brew_history.json`: immutable brew events.
- `style_option_templates.json`: inventory-aware style suggestion templates.

## CLI

Use:

`python3 tools/inventory_cli.py <command> [options]`

Common commands:

- `stock`
- `brew --recipe patient_number_9`
- `phrase "i brewed patient number 9"`
- `options --count 5`
- `phrase "create a beer i haven't made before with the ingredients i have"`
- `garbage --count 3`
- `phrase "garbage beer"`
- `restock --item pale_malt_us --amount 5000 --unit g`

## Notes

- Default stock starts at zero as a template. Update `stock.json` to your real inventory.
- `brew` does not block negative inventory; it warns and records a shortfall.
- For Patient Number 9, yeast usage assumes `2` packs of WLP007 per batch.
