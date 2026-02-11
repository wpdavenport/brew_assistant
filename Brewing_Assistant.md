# brewing_assistant.md

# Knowledge Index (Brew Assistant RAG Map)

Codex must treat the following as retrievable brewing memory and should consult them before giving advice.

## Highest priority (always check if relevant)
1) profiles/equipment.yaml
- Volumes, losses, boil-off, efficiencies, fermentation control limits

2) libraries/yeast.md
- House strains, temp ranges, attenuation, flavor, handling notes

3) profiles/water.md
- Source water + house target profiles + typical salt additions

4) house_style_guide.md
- My brewing doctrine: what “good” means, my preferences, my non-negotiables

5) batch_logs/
- Past measured OG/FG, pH, temps, timelines, tasting notes, issues, fixes

## Secondary (check when applicable)
6) codex/checklists/
- Brew day and fermentation execution steps

7) tools/calculators.md
- Standard formulas/assumptions we use in this repo

8) libraries/templates/
- grainfather_beerxml_template.xml: Standard schema for Grainfather imports/exports

## Output locations (write new artifacts here)
- New recipe drafts: recipes/in_development/
- Locked/stable recipes: recipes/locked/
- New batch logs: batch_logs/YYYY-MM-DD_style.md

## Hard rules
- Never invent values that should come from these files.
- If a file is missing or empty, say so and proceed with explicit assumptions.
- Prefer house strains and house processes over generic advice.

## Books (books/)
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
- Water book ↔ profiles/water.md
- Yeast book ↔ libraries/yeast.md
- Hops / Malt / Belgian Styles books ↔ house_style_guide.md, recipes/