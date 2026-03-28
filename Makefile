prompt-test:
	python3 tools/prompt_harness.py eval-all

prompt-cases:
	python3 tools/prompt_harness.py list-cases

prompt-bundle:
	python3 tools/prompt_harness.py render-prompt

drift-review:
	python3 tools/drift_review.py
