# Drift Matrix

Purpose: keep repo truth, AI behavior, generated outputs, and operational files from drifting apart.

Use:
- Update only when a drift-sensitive area changes.
- Keep notes short.
- Do not track every file. Track areas where a change can silently break trust.

Status:
- Stable = reviewed and trusted
- Watch = changed or likely impacted, needs review
- Guarded = high-risk area, must pass checks before trust
- Stale = entry no longer reflects reality

| Area | Canonical Source | Depends On / Affects | Review Trigger | Required Check | Owner | Status | Last Reviewed | Notes |
|---|---|---|---|---|---|---|---|---|
| Core brewing context | `profiles/equipment.yaml`, `profiles/water_profiles.md`, `libraries/yeast_library.md` | brewing recommendations, process advice, troubleshooting answers | any change to profile structure, brewing defaults, or core brewing guidance | confirm these files still exist, still match prompt/index references, and fail-closed behavior is still appropriate | Human | Stable | YYYY-MM-DD | |
| Knowledge retrieval map | `knowledge_index.md` | AI retrieval behavior, repo navigation, file selection | file move, file rename, folder add/remove, workflow change | verify every referenced path still exists and output locations still match repo layout | Human + AI | Stable | 2026-03-09 | `PROJECT_CONTEXT.md` removed from retrieval flow; `knowledge_index.md` now acts only as repo map. |
| Prompt contract | `system_prompt.md` | all AI behavior, trust boundaries, workflow behavior | prompt edit, workflow change, new mode, renamed file, changed guardrail | compare prompt rules against actual repo structure and current working process; remove rules that no longer map to real files or scripts | Human | Stable | 2026-03-09 | `system_prompt.md` is now the sole AI entry file; harness and README align to this contract. |
| Hop AA sync | `libraries/inventory/stock.json` | recipes, logs, printable HTML, BeerXML exports, inventory-aware brewing logic | hop lot update, AA edit, recipe/export edit touching hop values | run `python3 tools/validate_hop_aa_sync.py`; do not mark trusted unless result is `AA_SYNC_OK` | Human + AI | Guarded | YYYY-MM-DD | |
| Inventory truth | `libraries/inventory/stock.json` | `tools/inventory_cli.py`, recipe feasibility, shopping logic, stock-aware suggestions | restock, brew completion, schema edit, inventory workflow edit | confirm stock schema still matches CLI expectations and brew/restock flows still make sense | Human + AI | Watch | YYYY-MM-DD | |
| Recipe lifecycle | `recipes/in_development/` and `recipes/locked/` | brew-day sheets, batch logs, exports, repeatability | recipe promoted, recipe revised after batch, duplicate recipe created, BeerXML import/export change | confirm which recipe is current, which is locked, and that downstream artifacts reference the intended version | Human | Watch | YYYY-MM-DD | |
| Brew-day execution artifacts | recipe markdown + `libraries/inventory/stock.json` + `libraries/yeast_library.md` + `profiles/equipment.yaml` | `brewing/brew_day_sheets/`, printable logs, brew execution decisions | new brew-day sheet, OG/volume change, yeast availability change, schedule/date change | confirm yeast source, generation, starter method, and brew-date-anchored dates are explicit and inventory-backed | Human | Watch | YYYY-MM-DD | |
| Batch log truth | `batch_logs/` and `batch_logs/brew_log_template.html` | historical troubleshooting, repitch tracking, completed brew reports | new brew log, completed batch, template edit, HTML printable changes | confirm new printable logs start from template and preserved core sections unless intentionally changed; verify batch data captured cleanly | Human | Watch | YYYY-MM-DD | |
| BJCP study isolation | `libraries/bjcp_study/` files | study behavior vs normal brewing behavior | prompt edit, study command change, new study file, mode handling edits | verify BJCP mode is still explicit opt-in and does not leak into standard brewing responses | Human | Stable | YYYY-MM-DD | |
