# Brewing_Assistant.md

# Knowledge Index (Brew Assistant RAG Map)

Codex must treat the following as retrievable brewing memory and should consult them before giving advice.

## Highest priority (always check if relevant)
1) profiles/equipment.yaml
- Volumes, losses, boil-off, efficiencies, fermentation control limits

2) libraries/yeast_library.md
- House strains, temp ranges, attenuation, flavor, handling notes

3) profiles/water_profiles.md
- Source water + house target profiles + typical salt additions

4) libraries/_index.md
- Style doctrine index (maps style IDs to research files)

5) libraries/my_recipes/
- Legacy recipe memory: measured outcomes, notes, and iteration history

## Secondary (check when applicable)
6) libraries/beer_research/_index.md
- Style doctrine map; open the matching file in libraries/beer_research/

7) libraries/bjcp_overlays/_index.md
- BJCP constraints and judge-facing risk overlays by style

8) tools/calculations.md
- Standard formulas/assumptions we use in this repo

9) tools/batch_log_template.md
- Batch log template for consistent capture

10) libraries/templates/grainfather_beerxml_template.xml
- Standard schema template for Grainfather BeerXML imports/exports

11) recipes/beer_xml_imports/
- Location for external BeerXML files to be read/analyzed

12) libraries/inventory/
- Inventory state + recipe consumption maps + brew history for stock-aware recommendations

13) tools/inventory_cli.py
- Command workflow for stock updates ("I brewed X"), stock-aware style options, and Garbage Beer concepts

## Output locations (write new artifacts here)
- New recipe drafts: recipes/in_development/
- Locked/stable recipes: recipes/locked/
- New batch logs: batch_logs/YYYY-MM-DD_style.md
- BeerXML Exports: recipes/beer_xml_exports/

## Hard rules
- Never invent values that should come from these files.
- If a file is missing or empty, say so and proceed with explicit assumptions.
- Prefer house strains and house processes over generic advice.

## Books (optional reference titles)
Reference titles covering the four core ingredients plus style-specific brewing.

| Topic | Title | Author(s) |
|-------|------|-----------|
| Water | Water: A Comprehensive Guide for Brewers | John Palmer, Colin Kaminski |
| Hops | For the Love of Hops | Stan Hieronymus |
| Yeast | Yeast: The Practical Guide to Beer Fermentation | Chris White, Jamil Zainasheff |
| Malt | Malt: A Practical Guide from Field to Brewhouse | John Mallett |
| Belgian Styles | Brew Like a Monk | Stan Hieronymus |

Consult these when ingredient-specific or style-specific depth is needed beyond house profiles.

Cross-reference with house files:
- Water book ↔ profiles/water_profiles.md
- Yeast book ↔ libraries/yeast_library.md
- Hops / Malt / Belgian Styles books ↔ libraries/beer_research/, libraries/my_recipes/
