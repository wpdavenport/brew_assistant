# Review Rules

This repo uses a small drift-review loop.

## drift review

Use before commit, after meaningful changes, or before trusting AI-generated output.

Do:
- compare changed files to matrix rows
- identify affected rows
- flag stale mappings
- flag missing required checks
- propose status and note updates

## 1) sync review

Use after changing a source-of-truth file or any file that drives downstream outputs.

Examples:
- `knowledge_index.md`
- `system_prompt.md`
- `libraries/inventory/stock.json`
- recipe files
- brew-day sheets
- batch log template
- inventory scripts
- BeerXML files

Do:
- identify affected rows in `DRIFT_MATRIX.md`
- set affected rows to `Watch` or `Guarded`
- run listed checks
- add one short note if trust changed
- update `Last Reviewed`

## 2) drift check

Use before commit, before trusting AI-generated output, or after a burst of edits.

Do:
- compare changed files against matrix rows
- flag anything touched with no matching row update
- mark rows `Stale` if the matrix is no longer telling the truth
- list missing checks before calling work done

## 3) lock review

Use before promoting something to trusted output.

Examples:
- moving recipe draft to `recipes/locked/`
- trusting a new brew-day sheet
- trusting a BeerXML export
- trusting a stock-aware plan after inventory edits

Do:
- verify source-of-truth alignment
- verify required checks passed
- verify prompt/index/docs are not lying about the area
- move status to `Stable` only when the area is actually trusted

## Practical rules

- Keep rows few and concrete.
- Delete rows nobody uses.
- Prefer one validator script over long prose.
- Prefer one-line notes over paragraphs.
- If a row stays vague, split it or simplify it.
- If a control does not improve trust after change, remove it.
