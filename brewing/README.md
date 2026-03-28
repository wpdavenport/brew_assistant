# Brewing Artifacts

## Brew Day Sheets (`brew_day_sheets/`)

The brew day sheet is the single canonical artifact for each batch. It serves as both the pre-brew execution guide and the brew day record.

**Reference example:** `brew_day_sheets/copper_crown_brew_day_sheet.html`

### What a brew day sheet contains
- Page 1: Recipe targets — grain bill, water chemistry, hop schedule, yeast and pitch plan
- Page 2: Brew day execution — pre-brew QC, mash checklist, boil additions, transfer and pitch
- Page 3: Fermentation log, packaging gate, brew notes

### Naming convention
- **Undated** `<slug>_brew_day_sheet.html` — competition-locked recipe, no brew date committed yet
- **Dated** `<slug>_brew_day_sheet_<YYYY-MM-DD>.html` — brew date committed; this is both the live sheet and the permanent record

When a brew date is set, rename the undated file immediately using `git mv`. If the brew date is known when the sheet is first generated, name it with the date from the start. Dated files are never renamed after the fact.

### Guardrails (enforced by system prompt)
- Yeast plan must match `libraries/inventory/stock.json` reality
- Hop AA values must be synced with `stock.json` (`AA_SYNC_OK` required)
- Fermentation dates must be anchored to actual brew date — no unresolved `YYYY-MM-DD` placeholders
- Timed additions must be per-addition amounts, not grouped
- In printable brew-day logs, each timed action gets its own line item even when multiple additions happen at the same minute mark
- Water-acid additions must specify timing (post-mash-in, after pH check)
