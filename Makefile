.PHONY: help init test clean

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

clean: ## Remove .venv/, __pycache__/, and .pytest_cache/
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .pytest_cache
