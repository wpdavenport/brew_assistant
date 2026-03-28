# 🍺 Brew Assistant (Repo-RAG)

**Your AI Head Brewer that actually knows *your* system.**

Welcome to **Brew Assistant**, a repository-based Retrieval Augmented Generation (RAG) system designed to turn your coding assistant into a world-class brewing coach.
You are an expert beer homebrewer and a Master-level BJCP judge.

## 🚀 Why is this amazing?

Most AI brewing advice is generic. It assumes 5 gallons, 70% efficiency, and tap water.

**Brew Assistant is different.** It consults *this* repository before answering. It knows:
*   **Your Equipment:** It knows your G40's deadspace, your boil-off rates, and your glycol chiller's limits.
*   **Your Water:** It builds recipes from *your* RO baseline, not some generic "city water" profile.
*   **Your History:** It remembers that time you stalled the Belgian Dark Strong and suggests a fix for next time.
*   **Your Doctrine:** It respects your house rules (e.g., "No secondary fermentation," "Closed transfers only").

It's not just a recipe generator; it's a **process engine** focused on repeatability and BJCP competition quality.

## 🛠️ Getting Started

**💡 Pro Tip:** The easiest way to use this is inside **VS Code** with your preferred AI chat client. The important part is not the model vendor; it is starting the session with the repo contract loaded in the right order.

### Recommended onboarding for every new chat

Use this exact startup instruction:

`Read system_prompt.md first, then use knowledge_index.md as the repo map.`

Then make sure the assistant confirms these core files are loaded before giving repo-specific advice:
- `profiles/equipment.yaml`
- `profiles/water_profiles.md`
- `libraries/yeast_library.md`
- `libraries/inventory/stock.json`

Expected startup behavior:
- `CONTEXT_READY` if the core files are readable
- explicit mention of any missing files if context is blocked
- repo-specific brewing advice only after context is confirmed

### First-time setup

1. **Clone this repo**
2. **Fill in your profiles**
   - Edit `profiles/equipment.yaml` with your verified system stats
   - Update `profiles/water_profiles.md` with your source water and salts context
   - Keep `libraries/yeast_library.md` current for house strains and handling notes
3. **Start the assistant with the repo contract**
   - `system_prompt.md` is the behavior contract
   - `knowledge_index.md` is the retrieval map
4. **Ask brewing questions inside the repo workflow**
   - *"Design a BJCP 26D Belgian Dark Strong for my system."*
   - *"Why did my last IPA finish sweet? Check the logs."*
   - *"Create a fermentation schedule for a German Pilsner."*

### Fresh-chat rule

For a new user or a new chat, the system works the same way **only if the startup instruction above is used**.

This repo is not designed around generic chat behavior. It is designed around:
- loading `system_prompt.md`
- using `knowledge_index.md`
- confirming the core context files

If that boot sequence is skipped, responses may still be useful, but they are not operating inside the repo control model.


## 📂 How it Works

The brain of the operation is the **Knowledge Index**. The AI uses `knowledge_index.md` to navigate your brewing reality.

### The Core Memory
*   **`profiles/equipment.yaml`**: The hard truth about your hardware.
*   **`profiles/water_profiles.md`**: Your water chemistry targets.
*   **`libraries/yeast_library.md`**: Your house strains and how they behave.
*   **`recipes/`**: Your working recipe history and iteration notes.

### The Workflow
1.  **Design**: Ask for a recipe. The AI checks `libraries/beer_research/` and `libraries/bjcp_overlays/` to build a winner.
2.  **Plan**: It generates a minute-by-minute brew day checklist tailored to your system.
3.  **Execute**: It calculates strike temps and salt additions using your specific `tools/calculations.md`.
4.  **Learn**: After the brew, you log the data. The AI uses this to troubleshoot and improve the next batch.

### Iteration Discipline
- Locked competition recipes are treated as canonical brewed versions, not scratchpads.
- Post-batch sensory findings should be captured explicitly, then the next formulation should be created as a new iteration when needed.
- For clone beers, keep three things separate:
  - the brewed recipe
  - the tasting/calibration notes
  - the next clone iteration

### Drift Review
- If assistant behavior starts drifting from your expectations, ask directly for a `drift review`.
- Good prompts are:
  - `Review system_prompt.md for drift against recent behavior.`
  - `Compare recent assistant behavior to system_prompt.md and knowledge_index.md and identify missing guardrails.`
  - `Audit the prompt docs for drift based on these last few conversations.`
- Include concrete examples when possible. The harness catches known regressions; a drift review is how you discover new ones and tighten the guardrails.

## AI-assisted workflow

Start with:
- `system_prompt.md`
- `knowledge_index.md`

Project control files:
- `project_control/REVIEW_RULES.md`
- `project_control/DRIFT_MATRIX.md`

Use `drift review` before trusting meaningful changes.

Control-plane commands:
- `make drift-review`
- `make aa-sync`
- `make recipe-sync`
- `make beerxml-sync`
- `make prepare-brew RECIPE=<recipe_slug> DATE=<YYYY-MM-DD>`
- `make register-brew RECIPE=<recipe_slug> DATE=<YYYY-MM-DD>`
- `make register-package RECIPE=<recipe_slug> BREW_DATE=<YYYY-MM-DD> PACKAGE_DATE=<YYYY-MM-DD> FG=<1.013> PACKAGED_VOLUME=<5.00>`
- `make trust-check`

### Recipe and log paths
- Recipes (drafts and locked): `recipes/`
- Printable brew-day sheets and tips: `brewing/brew_day_sheets/`
- Dated brew-day sheets are the single canonical batch record for new brews
- Legacy historical batch logs: `batch_logs/`
- Completed brew reports/results: `batch_logs/`
- BeerXML imports: `recipes/beer_xml_imports/`
- BeerXML exports: `recipes/beer_xml_exports/`
- Grainfather template: `libraries/templates/grainfather_beerxml_template.xml`
- Yeast generation tracking convention: `G0` = fresh lab pack, `G1+` = repitch generations (always record source batch ID/date)
- Guardrail: do not create a separate batch log for a new brew when a dated brew-day sheet exists. Put actual brew data into the dated brew-day sheet and use `brew_history.json` only for minimal event/index metadata.

## 📦 Inventory Workflow (Phase 1/2/3)

Inventory files live in `libraries/inventory/` and are driven by `tools/inventory_cli.py`.

### Phase 1
When you brew, decrement inventory:

`python3 tools/inventory_cli.py phrase "i brewed patient number 9"`

### Phase 2
Get stock-aware options for beers you have not brewed before:

`python3 tools/inventory_cli.py phrase "create a beer i haven't made before with the ingredients i have"`

### Phase 3
Generate experimental "Garbage Beer" concepts from leftovers:

`python3 tools/inventory_cli.py phrase "garbage beer"`

Useful commands:
- `python3 tools/inventory_cli.py stock`
- `python3 tools/inventory_cli.py restock --item pale_malt_us --amount 5000 --unit g`
- `python3 tools/inventory_cli.py options --count 5`
- `python3 tools/inventory_cli.py garbage --count 3`

## Hop AA Source-of-Truth Guardrail

- `libraries/inventory/stock.json` is the authoritative source for hop alpha acid values.
- Update `stock.json` first when lot AA changes.
- Re-sync recipe/log/export artifacts from `stock.json`, then run:
  - `python3 tools/validate_hop_aa_sync.py`
- Only finalize/commit hop-AA-related changes after validator output is `AA_SYNC_OK`.

## 🎓 BJCP Study Mode (Opt-In)

This mode is for learning and testing BJCP knowledge for the online entrance exam.
It is not enabled by default.

### Enter / Exit
- Enter: `enter bjcp mode`
- Exit: `exit bjcp mode`

### Commands in Study Mode
- `bjcp teach <topic>`
- `bjcp quiz <topic> <count>`
- `bjcp mock <count>`
- `bjcp review missed`
- `bjcp status`

### Study Assets
- `libraries/bjcp_study/_index.md`
- `libraries/bjcp_study/curriculum.md`
- `libraries/bjcp_study/rubrics.md`
- `libraries/bjcp_study/question_bank.json`
- `libraries/bjcp_study/progress_template.json`

## 🧠 The "Hard Rules"

To keep the AI honest, we enforce these rules:
*   **No Hallucinations**: If a file is missing, the AI must say so.
*   **House First**: We prefer house yeast and processes over generic internet wisdom.
*   **Competition Standard**: Default assumption is "We are brewing to win gold."
*   **Measurement Confidence**: The AI must distinguish measured, corrected, inferred, and uncertain values before making process calls.
*   **One Intervention At A Time**: For live-batch rescue advice, confirm the problem, make one move, then reassess.
*   **Clone Fidelity Over Generic Optimization**: Clone recipes are tuned toward the commercial target, not toward a generic "better IPA" or "better ESB."
*   **Operational Brew Sheets**: Printable sheets must be unambiguous at brew time and fit the intended page count without hiding critical instructions.

---
*Brew better. Brew smarter. Brew with data.* 🍻
