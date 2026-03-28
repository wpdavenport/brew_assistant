prompt-test:
	python3 tools/prompt_harness.py eval-all

prompt-cases:
	python3 tools/prompt_harness.py list-cases

prompt-bundle:
	python3 tools/prompt_harness.py render-prompt

drift-review:
	python3 tools/drift_review.py

recipe-sync:
	python3 tools/validate_recipe_brewsheet_sync.py --all

beerxml-sync:
	python3 tools/validate_recipe_beerxml_sync.py --all

aa-sync:
	python3 tools/validate_hop_aa_sync.py

prepare-brew:
	python3 tools/prepare_brew.py --recipe "$(RECIPE)" --date "$(DATE)" --run-trust-check

trust-check:
	python3 tools/drift_review.py --passed-check "python3 tools/drift_review.py"
	python3 tools/prompt_harness.py eval-all
	python3 tools/validate_hop_aa_sync.py
	python3 tools/validate_recipe_brewsheet_sync.py --all
	python3 tools/validate_recipe_beerxml_sync.py --all
