.PHONY: help fix

help:
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "%-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

fix: ## Run repo formatter and safe lint-fix pass.
	scripts/agent-fix
