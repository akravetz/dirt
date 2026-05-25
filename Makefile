.PHONY: help dev-up dev-down dev-reset dev-refresh-db dev-refresh-assets dev-status fix

help: ## List available commands.
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_-]+:.*##/ {printf "%-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

dev-up: ## Start the local dev environment.
	scripts/dev-env up

dev-down: ## Stop the local dev environment.
	scripts/dev-env down

dev-reset: ## Reset the local dev environment.
	scripts/dev-env reset

dev-refresh-db: ## Refresh the local dev database from the hosted control plane.
	scripts/dev-env refresh-db

dev-refresh-assets: ## Refresh local dev assets.
	scripts/dev-env refresh-assets

dev-status: ## Show local dev environment status.
	scripts/dev-env status

fix: ## Run repo formatter and safe lint-fix pass.
	scripts/agent-fix
