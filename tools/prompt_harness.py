#!/usr/bin/env python3
"""Prompt governance harness for the brewing assistant.

This harness is intentionally simple and local:
- It renders the current master prompt from repo policy files.
- It lists canned evaluation scenarios.
- It scores a saved assistant response against scenario-specific rules.

It does not call an LLM. The expected workflow is:
1. Generate a response with your preferred assistant/client.
2. Save that response to a text file.
3. Run this harness to check whether the response obeys repo guardrails.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "tools" / "prompt_harness_cases.json"
SYSTEM_PROMPT_PATH = ROOT / "system_prompt.md"
BREWING_ASSISTANT_PATH = ROOT / "Brewing_Assistant.md"


def load_cases() -> dict:
    return json.loads(CASES_PATH.read_text())


def render_master_prompt() -> str:
    sections = [
        "# Master Prompt Bundle",
        "",
        "## system_prompt.md",
        SYSTEM_PROMPT_PATH.read_text().rstrip(),
        "",
        "## Brewing_Assistant.md",
        BREWING_ASSISTANT_PATH.read_text().rstrip(),
        "",
    ]
    return "\n".join(sections)


def evaluate_case(case: dict, response_text: str) -> tuple[bool, list[str]]:
    failures: list[str] = []
    normalized = response_text

    for needle in case.get("required_substrings", []):
        if needle not in normalized:
            failures.append(f"missing required substring: {needle!r}")

    for needle in case.get("forbidden_substrings", []):
        if needle in normalized:
            failures.append(f"found forbidden substring: {needle!r}")

    for pattern in case.get("required_regex", []):
        if not re.search(pattern, normalized, flags=re.IGNORECASE | re.MULTILINE):
            failures.append(f"missing required regex: {pattern!r}")

    for pattern in case.get("forbidden_regex", []):
        if re.search(pattern, normalized, flags=re.IGNORECASE | re.MULTILINE):
            failures.append(f"found forbidden regex: {pattern!r}")

    for rule in case.get("meta_rules", []):
        if rule == "no_context_blocked":
            if "CONTEXT_BLOCKED" in normalized:
                failures.append("response incorrectly blocked on missing context")
        elif rule == "mention_uncertainty":
            uncertain_words = ["uncertain", "estimate", "approx", "confidence", "likely"]
            if not any(word in normalized.lower() for word in uncertain_words):
                failures.append("response should acknowledge measurement uncertainty")
        elif rule == "single_intervention_bias":
            action_hits = 0
            action_terms = [
                "add baking soda",
                "pitch us-05",
                "pitch yeast",
                "add sugar",
                "oxygenate",
                "raise temperature",
                "rouse yeast",
            ]
            lower = normalized.lower()
            for term in action_terms:
                if term in lower:
                    action_hits += 1
            if action_hits > 2:
                failures.append("response appears to stack too many rescue interventions")
        else:
            failures.append(f"unknown meta rule: {rule}")

    return not failures, failures


def cmd_render_prompt(_: argparse.Namespace) -> int:
    sys.stdout.write(render_master_prompt())
    return 0


def cmd_list_cases(_: argparse.Namespace) -> int:
    cases = load_cases()["cases"]
    for case in cases:
        print(f"{case['id']}: {case['title']}")
    return 0


def cmd_show_case(args: argparse.Namespace) -> int:
    cases = {case["id"]: case for case in load_cases()["cases"]}
    case = cases.get(args.case_id)
    if case is None:
        print(f"Unknown case: {args.case_id}", file=sys.stderr)
        return 1
    print(json.dumps(case, indent=2))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    cases = {case["id"]: case for case in load_cases()["cases"]}
    case = cases.get(args.case_id)
    if case is None:
        print(f"Unknown case: {args.case_id}", file=sys.stderr)
        return 1

    response_path = Path(args.response_file)
    response_text = response_path.read_text()
    passed, failures = evaluate_case(case, response_text)

    print(f"CASE: {case['id']} - {case['title']}")
    print(f"RESPONSE: {response_path}")
    print(f"RESULT: {'PASS' if passed else 'FAIL'}")
    if failures:
        print("FAILURES:")
        for failure in failures:
            print(f"- {failure}")
    else:
        print("All checks passed.")
    return 0 if passed else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prompt governance harness")
    sub = parser.add_subparsers(dest="command", required=True)

    render_prompt = sub.add_parser("render-prompt", help="Print the combined master prompt")
    render_prompt.set_defaults(func=cmd_render_prompt)

    list_cases = sub.add_parser("list-cases", help="List evaluation scenarios")
    list_cases.set_defaults(func=cmd_list_cases)

    show_case = sub.add_parser("show-case", help="Show one scenario")
    show_case.add_argument("case_id")
    show_case.set_defaults(func=cmd_show_case)

    eval_case = sub.add_parser("eval", help="Evaluate a saved response against a scenario")
    eval_case.add_argument("case_id")
    eval_case.add_argument("response_file")
    eval_case.set_defaults(func=cmd_eval)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
