# BJCP Study Matrix

Purpose: keep BJCP study sources, question quality, test behavior, and saved progress from drifting apart.

Use:
- Update when the study system changes in a way that could break trust or learning quality.
- Keep this separate from brewing drift control.
- Prefer short notes tied to real checks.

Status:
- Stable = reviewed and trusted
- Watch = changed or likely impacted, needs review
- Guarded = high-risk area, must pass checks before trust
- Stale = entry no longer reflects reality

| Area | Canonical Source | Depends On / Affects | Review Trigger | Required Check | Owner | Status | Last Reviewed | Notes |
|---|---|---|---|---|---|---|---|---|
| Study source material | `books/BJCP_Study_Guide.pdf`, `books/SCP_BeerScoreSheet.pdf`, `libraries/bjcp_study/_index.md`, `libraries/bjcp_study/curriculum.md`, `libraries/bjcp_study/rubrics.md` | question writing, explanations, judging mechanics, study recommendations | source PDF added/removed, curriculum rewrite, rubric rewrite | confirm the PDF paths still exist locally and study docs still point to the intended exam materials | Human + AI | Watch | 2026-03-30 | PDFs are local/private sources; the shared repo should not assume they are committed. |
| Question bank quality | `libraries/bjcp_study/question_bank.json` | mini tests, answer explanations, topic stats | question edit, schema change, new bank import, topic rebalance | run `python3 tools/validate_bjcp_question_sources.py` and confirm every active question is source-backed | Human + AI | Guarded | 2026-03-30 | Starter bank is now source-tagged, but still intentionally small. |
| Study progress integrity | `libraries/bjcp_study/progress_template.json`, `libraries/bjcp_study/progress.json` | accuracy stats, weak-topic tracking, test history, resets | progress schema change, reset flow change, scoring logic change | confirm reset returns to a clean template and history/accuracy update after a test | Human + AI | Watch | 2026-03-30 | `progress.json` is user-state, not canonical shared knowledge. |
| Test UI behavior | `tools/web_ui.py` study routes and forms | timer behavior, answer reveal mode, saved test flow, review UX | any edit to `/study`, `/study/test`, `/study/reset`, results rendering | run a manual mini test and confirm setup, submit, history, missed-answer review, and reset still work | Human | Watch | 2026-03-30 | Training mode allows immediate answer feedback; exam-like mode should remain available. |
| Study prompt/index isolation | `system_prompt.md`, `knowledge_index.md` | whether BJCP help stays separate from brewing mode | prompt edit, startup/index edit, study-mode rule change | confirm BJCP mode remains explicit opt-in and references the correct study files | Human + AI | Watch | 2026-03-30 | BJCP should not leak into normal brewing responses by default. |
| Coverage reporting | `tools/bjcp_question_report.py` | topic balance, source-section visibility, future bank growth | report logic change, topic taxonomy change, question-bank expansion | run `python3 tools/bjcp_question_report.py` and confirm counts match the bank | Human + AI | Watch | 2026-03-30 | This is the management view for scaling beyond the starter bank. |
