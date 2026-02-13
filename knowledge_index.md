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
- libraries/templates/grainfather_beerxml_template.xml
- recipes/beer_xml_imports/
- recipes/beer_xml_exports/

## Inventory workflow (when relevant)
- libraries/inventory/stock.json
- libraries/inventory/recipe_usage.json
- libraries/inventory/brew_history.json
- libraries/inventory/style_option_templates.json
- tools/inventory_cli.py

## Output locations (write new artifacts here)
- New recipe drafts: recipes/in_development/
- Locked/stable recipes: recipes/locked/
- New batch logs: batch_logs/YYYY-MM-DD_style.md
- BeerXML Exports: recipes/beer_xml_exports/

## Hard rules
- Never invent values that should come from repo files.
- If a file is missing or empty, say so and proceed with explicit assumptions.
- Prefer house strains and house processes over generic advice.
- Fail-closed core context gate: if profiles/equipment.yaml, profiles/water_profiles.md, or libraries/yeast_library.md are missing/unreadable, stop and request those files instead of using defaults.
