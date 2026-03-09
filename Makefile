.PHONY: help init test lint fmt clean

PYTHON  := $(shell command -v python3 2>/dev/null)
ifndef PYTHON
$(error python3 not found — install Python 3.12+)
endif
VENV    := .venv
VENVPY  := $(VENV)/bin/python

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

init: ## Create/update .venv and install all dependencies
	$(PYTHON) -m venv $(VENV)
	$(VENVPY) -m pip install --upgrade pip
	$(VENVPY) -m pip install -e ".[dev]"

test: ## Run the full test suite
	$(VENVPY) -m pytest
	@error_count=$$($(VENVPY) -m mypy src tests 2>&1 | grep -c "error:" || true); \
	baseline=$$(head -1 .type_baseline); \
	echo "mypy errors: $$error_count (baseline: $$baseline)"; \
	if [ "$$error_count" -gt "$$baseline" ]; then \
		echo "Type errors increased from $$baseline to $$error_count"; \
		$(VENVPY) -m mypy src tests; \
		exit 1; \
	fi

lint: ## Check code style and lint with ruff
	$(VENVPY) -m ruff check src tests

fmt: ## Auto-format and fix lint issues with ruff
	$(VENVPY) -m ruff format src tests
	$(VENVPY) -m ruff check --fix src tests

clean: ## Remove .venv/, __pycache__/, and .pytest_cache/
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache
