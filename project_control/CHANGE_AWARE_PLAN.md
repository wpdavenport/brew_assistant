# Change-Aware Repo Assistant Plan

Purpose: move this repo from "Repo-RAG with guardrails" to a practical change-aware assistant without overbuilding a full control plane.

## Current State

The repo already has the core pieces of level 2 and parts of level 3:

- Retrieval map: `knowledge_index.md`
- Prompt contract: `system_prompt.md`
- Drift state: `project_control/DRIFT_MATRIX.md`
- Review workflow: `project_control/REVIEW_RULES.md`
- Prompt regression harness: `tools/prompt_harness.py`
- One real validator: `tools/validate_hop_aa_sync.py`

This means the repo already knows:
- what files matter
- what rules exist
- where drift can break trust

What it does not yet do reliably:
- classify a change set
- map changed files to affected control rows automatically
- tell the operator which checks must run
- report which checks are still missing
- validate recipe -> brew sheet -> BeerXML sync beyond hop AA

## Target State

The next practical milestone is:

`Repo-RAG + drift-aware control system + local validators`

That means:
- changed files automatically map to affected control rows
- required checks are explicit
- trust is not restored by memory or habit alone
- source-of-truth drift is surfaced before commit or before "this is ready"

## Phased Plan

### Phase 1: Executable Drift Review

Deliverables:
- `tools/drift_review.py`
- `make drift-review`

Behavior:
- inspect changed files (or accept explicit file paths)
- map them to rows in `project_control/DRIFT_MATRIX.md`
- print:
  - affected rows
  - proposed status changes
  - required checks
  - missing checks
  - note/update suggestions

Success condition:
- "drift review" becomes a repeatable command, not a memory exercise

### Phase 2: Formal Check Bundles

Deliverables:
- machine-readable check map, likely `project_control/check_map.json`

Behavior:
- define what must run for each change type
- examples:
  - prompt change -> `python3 tools/prompt_harness.py eval-all`
  - inventory / hop AA change -> `python3 tools/validate_hop_aa_sync.py`
  - BeerXML change -> XML parse + recipe/export sync validator
  - brew-sheet change -> brew-sheet operational validator

Success condition:
- checks stop being tribal knowledge

### Phase 3: Artifact Sync Validators

Deliverables:
- `tools/validate_recipe_brewsheet_sync.py`
- `tools/validate_recipe_beerxml_sync.py`

Behavior:
- catch mismatched fermentables, hop timing, grouped additions, fermentation schedule drift, and dated-sheet naming issues

Success condition:
- recipe, brew sheet, and export stop drifting independently

### Phase 4: Pre-Trust Workflow

Deliverables:
- `make trust-check`

Behavior:
- runs drift review
- runs relevant validators
- reports whether the touched area is actually trustable

Success condition:
- there is one standard "before commit / before trust" command

### Phase 5: Optional Control Plane Expansion

Only after phases 1-4 prove useful.

Possible additions:
- ownership metadata
- stronger recipe state metadata
- release/readiness summaries
- structured review depth rules

## Immediate Next Step

Implement Phase 1 now:

1. Add `tools/drift_review.py`
2. Add `make drift-review`
3. Update `project_control/REVIEW_RULES.md` to point to the executable workflow

## Non-Goals

Not doing yet:
- autonomous multi-step repo mutation
- external services
- heavyweight graph databases
- a general-purpose release platform

The goal is tighter local trust, not complexity for its own sake.
