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

## Reference library (when technique depth is needed)
- books/ — brewing reference texts (local only, not committed). Check for PDFs when asked about technique, history, or master brewer perspective. If present, treat as authoritative source material. Cite the author and title when drawing from them.

## External historical sources (when style history or traditional brewery practice matters)
- Barclay Perkins blog — https://barclayperkins.blogspot.com/
  - High-value source for historical British brewing records, logs, recipes, and process context.
  - Use especially for English, Scottish, porter/stout, historical mild, and pre-modern process questions.
  - Treat as research support for historical interpretation, not as a substitute for the target beer's own commercial facts when doing clone work.

## Tools / templates (when needed)
- tools/calculations.md
- libraries/templates/grainfather_beerxml_template.xml
- recipes/beer_xml_imports/
- recipes/beer_xml_exports/

## Inventory workflow (when relevant)
- libraries/inventory/stock.json
- libraries/inventory/recipe_usage.json
- libraries/inventory/brew_history.json
- libraries/inventory/shopping_intent.json
- libraries/inventory/style_option_templates.json
- tools/inventory_cli.py

## Rule / insight capture (when relevant)
- project_control/insight_register.json
- tools/intake_insight.py
- tools/insight_report.py

## BJCP study mode (when explicitly enabled)
- libraries/bjcp_study/_index.md
- libraries/bjcp_study/curriculum.md
- libraries/bjcp_study/rubrics.md
- libraries/bjcp_study/question_bank.json
- libraries/bjcp_study/progress_template.json
- project_control/BJCP_STUDY_MATRIX.md
- books/BJCP_Study_Guide.pdf
- books/SCP_BeerScoreSheet.pdf

## Output locations (write new artifacts here)
- New recipe drafts: recipes/
- Locked/stable recipes: recipes/locked/
- Brew day sheets: brewing/brew_day_sheets/ (naming: <slug>_brew_day_sheet.html or <slug>_brew_day_sheet_<YYYY-MM-DD>.html)
- BeerXML Exports: recipes/beer_xml_exports/

## Retrieval rules
- Never invent values that should come from repo files.
- If a file is missing or empty, say so and proceed with explicit assumptions.
- If a style is specified, open both the matching research file and BJCP overlay before giving style-specific advice.
- If a recipe is being created and the matching style research file or BJCP overlay does not exist, create the missing file(s) first and use them as the recipe baseline instead of relying only on a nearest-style substitute.
- Use `libraries/inventory/stock.json` as the source-of-truth for hop alpha acid values when retrieving or reconciling recipe data.
