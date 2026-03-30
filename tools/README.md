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
- `python3 tools/inventory_cli.py phrase "i packaged davenport esb brewed 2026-03-28 on 2026-04-10 at 4.55 gal fg 1.013"`
- `python3 tools/inventory_cli.py phrase "i packaged davenport esb brewed 2026-03-28 on 2026-04-10 at 4.55 gal fg 1.013 harvested 1968 gen 2"`
- `python3 tools/inventory_cli.py phrase "create a beer i haven't made before with the ingredients i have"`
- `python3 tools/inventory_cli.py phrase "garbage beer"`

Use `prepare_brew.py` to activate a real brew date and update live trust scope:

- `python3 tools/prepare_brew.py --recipe old_crown_lazy_lager --date 2026-04-15 --dry-run`
- `python3 tools/prepare_brew.py --recipe old_crown_lazy_lager --date 2026-04-15 --run-trust-check`
- `make prepare-brew RECIPE=old_crown_lazy_lager DATE=2026-04-15`

Use `batch_lifecycle.py` when you want the repo to choose the next lifecycle action automatically:

- `python3 tools/batch_lifecycle.py --recipe old_crown_lazy_lager --dry-run`
- `python3 tools/batch_lifecycle.py --recipe old_crown_lazy_lager --date 2026-04-15 --run-trust-check`
- `python3 tools/batch_lifecycle.py --recipe davenport_esb --date 2026-03-28 --dry-run`
- `python3 tools/batch_lifecycle.py --recipe davenport_esb --date 2026-03-28 --fg 1.013 --packaged-volume 4.55 --package-date 2026-04-10 --harvest-yeast 1968 --dry-run`
- `make batch-lifecycle RECIPE=old_crown_lazy_lager DATE=2026-04-15 RUN_TRUST_CHECK=1`

Use `register_brew.py` after the batch is actually brewed to decrement inventory and append the brew event:

- `python3 tools/register_brew.py --recipe davenport_esb --date 2026-03-28 --dry-run`
- `python3 tools/register_brew.py --recipe davenport_esb --date 2026-03-28`
- `make register-brew RECIPE=davenport_esb DATE=2026-03-28`

Use `register_package.py` after packaging to capture FG, packaged yield, and optional harvested yeast:

- `python3 tools/register_package.py --recipe davenport_esb --brew-date 2026-03-28 --package-date 2026-04-10 --fg 1.013 --packaged-volume 4.55 --dry-run`
- `python3 tools/register_package.py --recipe davenport_esb --brew-date 2026-03-28 --package-date 2026-04-10 --fg 1.013 --packaged-volume 4.55 --harvest-item wyeast_1968_gen2_slurry --harvest-amount 1 --harvest-unit count`
- `python3 tools/register_package.py --recipe davenport_esb --brew-date 2026-03-28 --package-date 2026-04-10 --fg 1.013 --packaged-volume 4.55 --harvest-yeast 1968`
- `make register-package RECIPE=davenport_esb BREW_DATE=2026-03-28 PACKAGE_DATE=2026-04-10 FG=1.013 PACKAGED_VOLUME=4.55`

Use `yield_report.py` to review packaged yield history against your keg target:

- `python3 tools/yield_report.py`
- `python3 tools/yield_report.py --recipe davenport_esb`
- `python3 tools/yield_report.py --target-gal 5.0`
- `make yield-report`

Use `batch_state_summary.py` to see what is prepared, brewed but not packaged, and how packaged yield is trending:

- `python3 tools/batch_state_summary.py`
- `python3 tools/batch_state_summary.py --recipe davenport_esb`
- `python3 tools/batch_state_summary.py --target-gal 5.0`
- `make batch-state`

Use `render_recipe_html.py` to create a printable recipe handout from the canonical recipe markdown:

- `python3 tools/render_recipe_html.py --recipe davenport_esb`
- `python3 tools/render_recipe_html.py --all`
- `python3 tools/render_recipe_html.py --recipe old_crown_lazy_lager`
- `make recipe-html RECIPE=davenport_esb`
- `make recipe-html-all`

Use `web_ui.py` to launch a simple local browser for recipe prints, brew-day sheets, inventory, profiles, and research:

- `python3 tools/web_ui.py`
- `python3 tools/web_ui.py --port 9000`
- `make web-ui`
- `make web-ui PORT=9000`

Use `validate_recipe_html_sync.py` to ensure generated recipe HTML is up to date with recipe markdown:

- `python3 tools/validate_recipe_html_sync.py --all`
- `python3 tools/validate_recipe_html_sync.py --recipe davenport_esb`
- `make recipe-html-sync`

## Prompt Harness

Use the prompt harness to regression-test brewing-assistant guardrails after prompt changes:

- `python3 tools/prompt_harness.py render-prompt`
- `python3 tools/prompt_harness.py list-cases`
- `python3 tools/prompt_harness.py show-case technique_question_direct`
- `python3 tools/prompt_harness.py eval refractometer_uncertain_fg /path/to/response.txt`
- `python3 tools/prompt_harness.py eval-all`
- `make prompt-test`
- `make prompt-cases`
- `make prompt-bundle`

Reference:
- `tools/prompt_harness_README.md`
