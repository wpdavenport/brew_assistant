# Knowledge Index (Brew Assistant RAG Map)

These files are authoritative brewing memory for this repo. Consult them before giving advice.

## Always check (if relevant)
1) profiles/equipment.yaml
2) libraries/yeast_library.md
3) profiles/water_profiles.md
4) libraries/beer_research/_index.md
   - If a style is specified, open the matching research file in libraries/beer_research/
5) libraries/bjcp_overlays/_index.md
   - If a style is specified, open the matching BJCP overlay file
6) Brewing_Assistant.md
7) recipes/in_development/
8) recipes/locked/
9) libraries/my_recipes/ (legacy recipe memory)

## Tools / templates (when needed)
- tools/calculations.md
- tools/batch_log_template.md
- batch_logs/brew_log_template.html
- libraries/templates/grainfather_beerxml_template.xml
- recipes/beer_xml_imports/
- recipes/beer_xml_exports/

## Inventory workflow (when relevant)
- libraries/inventory/stock.json
- libraries/inventory/recipe_usage.json
- libraries/inventory/brew_history.json
- libraries/inventory/style_option_templates.json
- tools/inventory_cli.py

## BJCP study mode (when explicitly enabled)
- libraries/bjcp_study/_index.md
- libraries/bjcp_study/curriculum.md
- libraries/bjcp_study/rubrics.md
- libraries/bjcp_study/question_bank.json
- libraries/bjcp_study/progress_template.json

## Output locations (write new artifacts here)
- New recipe drafts: recipes/in_development/
- Locked/stable recipes: recipes/locked/
- New batch logs: batch_logs/YYYY-MM-DD_style.md
- Printable brew-day sheets: brewing/brew_day_sheets/
- Printable brew logs: batch_logs/
- Completed brew reports/results: batch_logs/
- BeerXML Exports: recipes/beer_xml_exports/

## Hard rules
- Never invent values that should come from repo files.
- If a file is missing or empty, say so and proceed with explicit assumptions.
- Prefer house strains and house processes over generic advice.
- `libraries/inventory/stock.json` is the source-of-truth for hop alpha acid values; if a recipe/log/printable-HTML/XML value differs, update stock first (if needed), then resync artifacts.
- After any hop AA edit, run `python3 tools/validate_hop_aa_sync.py` and do not finalize changes unless output is `AA_SYNC_OK`.
- Fail-closed core context gate: if profiles/equipment.yaml, profiles/water_profiles.md, or libraries/yeast_library.md are missing/unreadable, stop and request those files instead of using defaults for any repo-dependent recipe, process, historical-analysis, or batch-planning recommendation.
- Measurement formatting: provide dual units for practical brewing quantities; temperatures must be shown as °F first with °C in parentheses.
- Yeast reuse tracking is required: capture generation per batch (G0 fresh pack, G1+ repitch) and source batch ID/date for repitches.
- Brew-day-sheet yeast/pitch reconciliation is required: for `brewing/brew_day_sheets/*.html`, derive yeast plan from `libraries/inventory/stock.json` + recipe OG/volume (and yeast behavior), not from a fixed default starter assumption.
- BJCP mode is opt-in only and must be explicitly entered/exited by user command.
- Printable brew-log guardrail: for new HTML brew logs, start from `batch_logs/brew_log_template.html` and preserve core sections unless the user explicitly overrides.
- Treat `Competition Lock` recipes as canonical brewed versions. New formulation changes should become a new iteration or companion notes file, not a silent overwrite.
- Distinguish measured, corrected, inferred, and uncertain values whenever gravity or pH is driving a recommendation.
- For live-batch troubleshooting, prefer one intervention at a time, then reassess before recommending another.
- For clone work, prioritize fidelity to the declared commercial target over generic style optimization and capture post-packaging side-by-side findings for the next iteration.
