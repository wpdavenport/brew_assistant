# Batch Logs

Store individual batches here as:

YYYY-MM-DD_style.md

Example:
2025-02-01_west_coast_ipa.md

## Hop AA Sync Guardrail

`libraries/inventory/stock.json` is the source-of-truth for hop alpha acid values.

Run this check after any updates to hop AA values in recipes/logs/printable HTML/XML:

`python3 tools/validate_hop_aa_sync.py`

Expected output:
- `AA_SYNC_OK` = safe to proceed
- `AA_SYNC_FAILED` = fix artifacts or update `stock.json` first, then re-run

The validator scans brewing artifacts under:
- `recipes/` (excluding `recipes/beer_xml_imports/`)
- `batch_logs/`
- `brewing/brew_day_sheets/`
- `recipes/beer_xml_exports/`

## Inventory CLI

Use `inventory_cli.py` for inventory-aware workflows:

- `python3 tools/inventory_cli.py stock`
- `python3 tools/inventory_cli.py phrase "i brewed patient number 9"`
- `python3 tools/inventory_cli.py phrase "create a beer i haven't made before with the ingredients i have"`
- `python3 tools/inventory_cli.py phrase "garbage beer"`

## Prompt Harness

Use the prompt harness to regression-test brewing-assistant guardrails after prompt changes:

- `python3 tools/prompt_harness.py render-prompt`
- `python3 tools/prompt_harness.py list-cases`
- `python3 tools/prompt_harness.py show-case technique_question_direct`
- `python3 tools/prompt_harness.py eval refractometer_uncertain_fg /path/to/response.txt`
- `python3 tools/prompt_harness.py eval-all`

Reference:
- `tools/prompt_harness_README.md`
