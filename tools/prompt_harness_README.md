# Prompt Harness

This harness gives the brewing assistant a lightweight prompt-governance loop.

It is designed to catch drift in:
- guardrails
- clone fidelity discipline
- live-batch intervention behavior
- measurement-confidence language
- brew-day operational clarity

## What it does

`tools/prompt_harness.py` can:
- render the current master prompt bundle from `system_prompt.md` + `Brewing_Assistant.md`
- list canned evaluation scenarios
- evaluate a saved assistant response against brewing-specific guardrail checks

This harness does **not** call a model by itself. It evaluates responses you already generated.

## Files

- `tools/prompt_harness.py`
- `tools/prompt_harness_cases.json`
- `tools/prompt_harness_README.md`

## Recommended workflow

1. Change a prompt or guardrail file.
2. Generate responses for a few representative scenarios using your preferred assistant/client.
3. Save each response to a text file.
4. Run the harness against those saved responses.
5. If a case fails, tighten the prompt or the repo guidance before trusting the new behavior.

## Commands

Render the combined prompt bundle:

`python3 tools/prompt_harness.py render-prompt`

List scenarios:

`python3 tools/prompt_harness.py list-cases`

Show one scenario:

`python3 tools/prompt_harness.py show-case technique_question_direct`

Evaluate a saved response:

`python3 tools/prompt_harness.py eval refractometer_uncertain_fg /path/to/response.txt`

## What a good response file looks like

A plain text assistant response is enough. Example:

```text
Corrected FG is about 1.023, but confidence is limited because the OG is approximate.
A hydrometer reading would resolve the uncertainty.
```

## Suggested regression set

Run these after prompt changes:
- `technique_question_direct`
- `locked_recipe_iteration`
- `refractometer_uncertain_fg`
- `live_batch_single_intervention`
- `brew_sheet_operational_clarity`

## Limitations

- This is a rule-based harness, not a judge of beer quality.
- It catches prompt-behavior regressions, not whether the brewing advice is chemically correct in every case.
- If you want a stronger harness later, the next step is adding scored rubrics and golden-response examples per scenario.
