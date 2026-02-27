# Brewing HTML Artifacts

This folder contains printable/export HTML brew-day artifacts:
- `brew_day_sheets/` for brew-day execution sheets and tips pages

Use this folder for all new `.html` brew-day artifacts.

## Standard Brew Log Template (Guardrail)

- Canonical template: `../batch_logs/brew_log_template.html`
- Start every new printable brew log from this file.
- Replace all bracketed placeholders (example: `[RECIPE_NAME]`, `[OG_TARGET]`) when generating a recipe-specific log.
- Preserve section/page structure unless explicitly requested otherwise:
  - Page 1: Brew setup + ingredient staging
  - Page 2: Mash + boil execution
  - Page 3: Starter + fermentation tracking
  - Page 4: Packaging + competition gate
- Keep required competition controls in every generated log:
  - hop AA values
  - pre/post-boil gravity + volume checkpoints
  - yeast generation tracking (`G0`/`G1+`)
  - forced VDK gate before crash/packaging

## Brew Day Sheet Yeast/Pitch Guardrail

When creating or updating `brew_day_sheets/*.html`:
- Reconcile yeast plan against `libraries/inventory/stock.json` and recipe OG/volume.
- Do not use a fixed starter default for all recipes.
- Explicitly set:
  - yeast source (fresh pack vs harvested slurry),
  - planned generation (`G0` vs `G1+`),
  - pitch method (direct slurry / vitality starter / full starter),
  - starter size only when actually required.
- If stock does not support the required pitch, add an action note/shopping requirement instead of assuming availability.
