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

recipe-html-sync:
	python3 tools/validate_recipe_html_sync.py --all

print-readability:
	python3 tools/validate_print_readability.py

intent-lifecycle:
	python3 tools/validate_intent_lifecycle.py

aa-sync:
	python3 tools/validate_hop_aa_sync.py

prepare-brew:
	python3 tools/prepare_brew.py --recipe "$(RECIPE)" --date "$(DATE)" --run-trust-check

batch-lifecycle:
	python3 tools/batch_lifecycle.py --recipe "$(RECIPE)" $(if $(DATE),--date "$(DATE)",) $(if $(RUN_TRUST_CHECK),--run-trust-check,) $(if $(FG),--fg "$(FG)",) $(if $(PACKAGED_VOLUME),--packaged-volume "$(PACKAGED_VOLUME)",) $(if $(PACKAGE_DATE),--package-date "$(PACKAGE_DATE)",) $(if $(HARVEST_YEAST),--harvest-yeast "$(HARVEST_YEAST)",)

register-brew:
	python3 tools/register_brew.py --recipe "$(RECIPE)" --date "$(DATE)"

register-package:
	python3 tools/register_package.py --recipe "$(RECIPE)" --brew-date "$(BREW_DATE)" --package-date "$(PACKAGE_DATE)" --fg "$(FG)" --packaged-volume "$(PACKAGED_VOLUME)"

yield-report:
	python3 tools/yield_report.py

batch-state:
	python3 tools/batch_state_summary.py

batch-state-next:
	python3 tools/batch_state_summary.py --with-next-actions

recipe-html:
	python3 tools/render_recipe_html.py --recipe "$(RECIPE)"

recipe-html-all:
	python3 tools/render_recipe_html.py --all

recipe-html-refresh:
	python3 tools/refresh_recipe_html.py --changed

brew-op:
	python3 tools/brew_op.py $(if $(TEXT),--text "$(TEXT)",) $(if $(ACTION),--action "$(ACTION)",) $(if $(RECIPE),--recipe "$(RECIPE)",) $(if $(DATE),--date "$(DATE)",) $(if $(BREW_DATE),--brew-date "$(BREW_DATE)",) $(if $(PACKAGE_DATE),--package-date "$(PACKAGE_DATE)",) $(if $(FG),--fg "$(FG)",) $(if $(PACKAGED_VOLUME),--packaged-volume "$(PACKAGED_VOLUME)",) $(if $(PACKAGED_VOLUME_UNIT),--packaged-volume-unit "$(PACKAGED_VOLUME_UNIT)",) $(if $(CO2_VOLS),--co2-vols "$(CO2_VOLS)",) $(if $(HARVEST_YEAST),--harvest-yeast "$(HARVEST_YEAST)",) $(if $(HARVEST_GENERATION),--harvest-generation "$(HARVEST_GENERATION)",) $(if $(NOTE),--note "$(NOTE)",) $(if $(RUN_TRUST_CHECK),--run-trust-check,) $(if $(INCLUDE_OPTIONAL),--include-optional,) $(if $(RECORD_HISTORY),--record-history,) $(if $(NO_REFRESH_HTML),--no-refresh-html,)

insight:
	python3 tools/intake_insight.py --text "$(TEXT)" --record

insight-report:
	python3 tools/insight_report.py

bjcp-question-sources:
	python3 tools/validate_bjcp_question_sources.py

bjcp-question-report:
	python3 tools/bjcp_question_report.py

bjcp-study-check:
	python3 tools/validate_bjcp_question_sources.py
	python3 tools/bjcp_question_report.py

web-ui:
	python3 tools/web_ui_bootstrap.py $(if $(HOST),--host "$(HOST)",) $(if $(PORT),--port "$(PORT)",)

web-ui-agent-install:
	python3 tools/web_ui_service.py install

web-ui-agent-status:
	python3 tools/web_ui_service.py status

web-ui-agent-uninstall:
	python3 tools/web_ui_service.py uninstall

trust-check:
	python3 tools/drift_review.py --passed-check "python3 tools/drift_review.py"
	python3 tools/prompt_harness.py eval-all
	python3 tools/validate_hop_aa_sync.py
	python3 tools/validate_recipe_brewsheet_sync.py --all
	python3 tools/validate_recipe_beerxml_sync.py --all
	python3 tools/refresh_recipe_html.py --changed
	python3 tools/validate_recipe_html_sync.py --all
	python3 tools/validate_print_readability.py
	python3 tools/validate_intent_lifecycle.py
