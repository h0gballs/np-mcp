SHELL := /bin/bash
PY    := .venv/bin/python
DEPS  := .venv/.deps

# systemd deployment
SERVICE := np-mcp
DIR     := $(CURDIR)
USER    := $(shell id -un)
UNIT    := /etc/systemd/system/$(SERVICE).service

.DEFAULT_GOAL := help

.PHONY: help install test run smoke clean \
        service-install service-uninstall service-status service-logs service-restart service-stop

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- Local (virtualenv) ---------------------------------------------------

$(DEPS): ## (internal) create venv + install deps
	python3 -m venv .venv
	.venv/bin/pip install -q --upgrade pip
	.venv/bin/pip install -q "mcp>=1.8" requests pyyaml pytest
	touch $(DEPS)

install: $(DEPS) ## Create the venv and install runtime + dev deps

test: install ## Run the pytest suite
	$(PY) -m pytest

run: install ## Run the MCP server in the foreground (Ctrl-C to stop)
	set -a && source .env && set +a && $(PY) -m np_mcp

smoke: install ## Hit a running server's check_events once (peek) via MCP
	set -a && source .env && set +a && $(PY) -m np_mcp.smoke

# --- systemd (deployment) -------------------------------------------------

service-install: install ## Install, enable and start the systemd service (sudo)
	sed -e 's|__DIR__|$(DIR)|g' -e 's|__USER__|$(USER)|g' \
		deploy/$(SERVICE).service.template > /tmp/$(SERVICE).service
	sudo cp /tmp/$(SERVICE).service $(UNIT)
	sudo systemctl daemon-reload
	sudo systemctl enable --now $(SERVICE)
	@echo "Installed. Status: make service-status"

service-status: ## Show systemd service status
	systemctl status $(SERVICE) --no-pager

service-logs: ## Follow the systemd service logs
	journalctl -u $(SERVICE) -f

service-restart: ## Restart the service (sudo); use after editing config/code
	sudo systemctl restart $(SERVICE)

service-stop: ## Stop the service (sudo)
	sudo systemctl stop $(SERVICE)

service-uninstall: ## Disable and remove the systemd service (sudo)
	-sudo systemctl disable --now $(SERVICE)
	sudo rm -f $(UNIT)
	sudo systemctl daemon-reload

# --- Housekeeping ---------------------------------------------------------

clean: ## Remove the venv and Python caches
	rm -rf .venv .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
