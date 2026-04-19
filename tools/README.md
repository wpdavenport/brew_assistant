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
- `python3 tools/batch_state_summary.py --with-next-actions`
- `make batch-state`
- `make batch-state-next`

Use `brew_op.py` as the single operator entry point when you want fewer explicit lifecycle commands:

- `python3 tools/brew_op.py --text "status"`
- `python3 tools/brew_op.py --text "prepare old crown lazy lager on 2026-04-15" --dry-run`
- `python3 tools/brew_op.py --text "brew davenport esb on 2026-03-28" --dry-run`
- `python3 tools/brew_op.py --text "package davenport esb brewed 2026-03-28 on 2026-04-10 at 4.55 gal fg 1.013" --dry-run`
- `python3 tools/brew_op.py --action prepare --recipe old_crown_lazy_lager --date 2026-04-15 --run-trust-check`
- `make brew-op TEXT="status"`
- `make brew-op TEXT="prepare old crown lazy lager on 2026-04-15"`
- `make brew-op ACTION=package RECIPE=davenport_esb BREW_DATE=2026-03-28 PACKAGE_DATE=2026-04-10 FG=1.013 PACKAGED_VOLUME=4.55`

Use `intake_insight.py` when a new durable rule, preference, or learned process insight should be captured into repo state instead of staying only in chat memory:

- `python3 tools/intake_insight.py --text "Target defaults to UK unless explicitly marked American"`
- `python3 tools/intake_insight.py --text "Use dated brew-day sheets as the canonical batch record" --record`
- `make insight TEXT="My shopping list should follow explicit next/soon intent, not inferred active fermentor state"`

Use `insight_report.py` to review the captured integration queue:

- `python3 tools/insight_report.py`
- `python3 tools/insight_report.py --status captured`
- `make insight-report`

Use `validate_bjcp_question_sources.py` to ensure BJCP study questions remain tied to explicit source material:

- `python3 tools/validate_bjcp_question_sources.py`
- `make bjcp-question-sources`

Use `bjcp_question_report.py` to review BJCP question-bank coverage by topic, difficulty, and source section:

- `python3 tools/bjcp_question_report.py`
- `make bjcp-question-report`
- `make bjcp-study-check`

Use `render_recipe_html.py` to create a printable recipe handout from the canonical recipe markdown:

- `python3 tools/render_recipe_html.py --recipe davenport_esb`
- `python3 tools/render_recipe_html.py --all`
- `python3 tools/render_recipe_html.py --recipe old_crown_lazy_lager`
- `make recipe-html RECIPE=davenport_esb`
- `make recipe-html-all`

Use `refresh_recipe_html.py` to refresh only the print exports affected by current repo changes:

- `python3 tools/refresh_recipe_html.py --changed`
- `python3 tools/refresh_recipe_html.py --recipe davenport_esb`
- `python3 tools/refresh_recipe_html.py --all`
- `make recipe-html-refresh`

Use `web_ui.py` to launch a simple local browser for recipe prints, brew-day sheets, inventory, profiles, and research:

- `python3 tools/web_ui.py`
- `python3 tools/web_ui.py --port 9000`
- `make web-ui`
- `make web-ui PORT=9000`

Use `validate_recipe_html_sync.py` to ensure generated recipe HTML is up to date with recipe markdown:

- `python3 tools/validate_recipe_html_sync.py --all`
- `python3 tools/validate_recipe_html_sync.py --recipe davenport_esb`
- `make recipe-html-sync`

Use `validate_print_readability.py` to catch basic printable-page regressions in recipe and brew-sheet HTML:

- `python3 tools/validate_print_readability.py`
- `make print-readability`

Use `validate_branch_shared_artifacts.py` to ensure shared planning brew sheets and brew-sheet templates stay in sync across `main` and `personal`:

- `python3 tools/validate_branch_shared_artifacts.py`
- `python3 tools/validate_branch_shared_artifacts.py --left main --right personal`
- `make branch-shared-sync`

Use `validate_intent_lifecycle.py` to catch contradictions between shopping intent and actual batch lifecycle:

- `python3 tools/validate_intent_lifecycle.py`
- `make intent-lifecycle`

Use `hop_lot_guidance.py` to get recipe-level guidance when a hop has multiple tracked AA lots:

- `python3 tools/hop_lot_guidance.py --recipe patient_number_9`
- `make hop-lot-guidance RECIPE=patient_number_9`

Use `package_readiness.py` to turn current fermentation facts into a packaging gate decision:

- `python3 tools/package_readiness.py --recipe davenport_esb --current-fg 1.014 --stable-48h --vdk-clean`
- `make package-readiness RECIPE=davenport_esb ARGS="--current-fg 1.014 --stable-48h --vdk-clean"`

Use `sensory_learning.py` to summarize recorded sensory lessons and next-iteration implications:

- `python3 tools/sensory_learning.py --recipe copper_crown_esb`
- `make sensory-learning RECIPE=copper_crown_esb`

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
