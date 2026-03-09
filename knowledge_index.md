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
6) recipes/

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

## Retrieval rules
- Never invent values that should come from repo files.
- If a file is missing or empty, say so and proceed with explicit assumptions.
- If a style is specified, open both the matching research file and BJCP overlay before giving style-specific advice.
- Use `libraries/inventory/stock.json` as the source-of-truth for hop alpha acid values when retrieving or reconciling recipe data.
