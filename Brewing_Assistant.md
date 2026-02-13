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
- Working recipe memory: measured outcomes, notes, and iteration history

## Secondary (check when applicable)
6) libraries/beer_research/_index.md
- Style doctrine map; open the matching file in libraries/beer_research/

7) libraries/bjcp_overlays/_index.md
- BJCP constraints and judge-facing risk overlays by style

8) tools/calculations.md
- Standard formulas/assumptions we use in this repo

9) tools/batch_log_template.md
- Batch log template for consistent capture

10) libraries/beer_xml_imports/
- Location for external BeerXML files to be read/analyzed

11) libraries/inventory/
- Inventory state + recipe consumption maps + brew history for stock-aware recommendations

12) tools/inventory_cli.py
- Command workflow for stock updates ("I brewed X"), stock-aware style options, and Garbage Beer concepts

## Output locations (write new artifacts here)
- New recipe drafts: libraries/my_recipes/
- Locked/stable recipes: libraries/my_recipes/ (use filename/tag convention)
- BeerXML Exports: libraries/beer_xml_exports/

## Hard rules
- Never invent values that should come from these files.
- If a file is missing or empty, say so and proceed with explicit assumptions.
- Prefer house strains and house processes over generic advice.

## Books (optional; books/)
Reference PDFs covering the four core ingredients plus style-specific brewing.

| Topic | File | Author(s) |
|-------|------|-----------|
| Water | john_palmer_colin_kaminski-water_a_comprehensive_g.pdf | John Palmer, Colin Kaminski |
| Hops | For_The_Love_of_Hops_-_Stan_Hieronymus.pdf | Stan Hieronymus |
| Yeast | Yeast_The_Practical_Guide_to_Beer_Fermentation_-_Chris_White__Jamil_Zainasheff.pdf | Chris White, Jamil Zainasheff |
| Malt | Malt_-_John_Mallett.pdf | John Mallett |
| Belgian Styles | Brew_Like_a_Monk__Trappist_Abbey_and_Str_-_Stan_Hieronymus.pdf | Stan Hieronymus |

Consult these when ingredient-specific or style-specific depth is needed beyond house profiles.

Cross-reference with house files:
- Water book ↔ profiles/water_profiles.md
- Yeast book ↔ libraries/yeast_library.md
- Hops / Malt / Belgian Styles books ↔ libraries/beer_research/, libraries/my_recipes/
