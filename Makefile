.DEFAULT_GOAL := help
SHELL := $(shell which bash)
PYTHON_VERSION := 3.12.7

help: ## Show this help
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'

.venv: ## create venv if it doesn't exist
	python3 -m venv .venv
	source .venv/bin/activate && pip install --upgrade pip setuptools
	source .venv/bin/activate && pip install -r requirements.txt

clean-venv: clean-cache ## rm .venv and re-create it
	rm -rf .venv
	$(MAKE) .venv

black: .venv ## format python files
	source .venv/bin/activate && git ls-files '*.py' | xargs black --line-length=79

black-check: .venv ## check python formatting without modifying
	source .venv/bin/activate && git ls-files '*.py' | xargs black --check --line-length=79

pylint: .venv ## lint python files
	source .venv/bin/activate && git ls-files '*.py' | xargs pylint --max-line-length=90

mypy: .venv ## type check python files
	source .venv/bin/activate && python3 -m mypy $(shell git ls-files '*.py')

shellcheck: ## check shell scripts
	git ls-files 'scripts/*.sh' | xargs -r shellcheck --severity=error --format=gcc

unit: .venv ## run unit tests
	source .venv/bin/activate && python3 -m pytest -v -m "unit" tests/

unit-update-golden: .venv ## update golden files
	source .venv/bin/activate && python3 -m pytest -v -m "unit" tests/ --update_golden

integration: .venv ## run integration tests (requires credentials)
	source .venv/bin/activate && python3 -m pytest -v -m "integration" tests/

static-check: black-check mypy shellcheck pylint unit ## run all static checks (CI)

static: black mypy shellcheck pylint unit ## run all static checks with auto-format

clean-cache: ## clean python and pytest cache data
	@find . -type f -name "*.py[co]" -delete -not -path "./.venv/*"
	@find . -type d -name __pycache__ -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache

.PHONY: help black black-check pylint mypy shellcheck unit unit-update-golden integration static static-check clean-cache clean-venv
