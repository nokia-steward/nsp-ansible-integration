.PHONY: help setup install-dev check-venv lint flake8 pylint format yamllint security bandit audit validate validate-syntax validate-ansible test docs docs-serve build import-galaxy publish clean clean-all ci test-all

# Virtual environment variables
# Requires Python 3.12+ (ansible-core 2.20+)
PYTHON := python3
VENV_DIR := ansible-env
VENV_ACTIVE := $(shell echo $${VIRTUAL_ENV})
IN_VENV := $(shell if [ -n "$$VIRTUAL_ENV" ]; then echo "yes"; else echo "no"; fi)

# Extract collection info from galaxy.yml
COLLECTION_NAMESPACE := $(shell grep "^namespace:" galaxy.yml | awk '{print $$2}')
COLLECTION_NAME := $(shell grep "^name:" galaxy.yml | awk '{print $$2}')
COLLECTION_FULL_NAME := $(COLLECTION_NAMESPACE).$(COLLECTION_NAME)
COLLECTION_FILENAME := "$(yq -r '. | "\(.namespace)-\(.name)-\(.version).tar.gz"' galaxy.yml)"

# Default target
help:
	@echo ""
	@echo "Ansible Collection '$(COLLECTION_FULL_NAME)' - Development Tasks"
	@echo ""
	@if [ -z "$(VENV_ACTIVE)" ]; then \
		echo "⚠️  Environment: Not in a virtual environment"; \
		echo "   Activate with: source ansible-env/bin/activate"; \
	else \
		echo "✓ Environment: $(VENV_ACTIVE)"; \
	fi
	@echo ""
	@echo "SETUP:"
	@echo "  make setup              Set up development environment"
	@echo ""
	@echo "CODE QUALITY:"
	@echo "  make lint               Run all linting (flake8 + pylint + yamllint)"
	@echo "  make flake8             Flake8 check (catches unused imports/variables)"
	@echo "  make pylint             PyLint code analysis"
	@echo "  make format             Auto-format code (Black + isort)"
	@echo ""
	@echo "SECURITY SCANNING:"
	@echo "  make security           All security checks (bandit + pip-audit)"
	@echo "  make bandit             SAST scan (hardcoded secrets, injection risks)"
	@echo "  make audit              Dependency CVE detection"
	@echo ""
	@echo "VALIDATION & TESTING:"
	@echo "  make validate           Python + Ansible syntax check"
	@echo "  make test               Run all playbook tests (report under tests/reports/)"
	@echo ""
	@echo "DOCUMENTATION:"
	@echo "  make docs               Build mkdocs documentation"
	@echo "  make docs-serve         Serve docs locally (http://localhost:8000)"
	@echo ""
	@echo "BUILD, INSTALL, PUBLISH:"
	@echo "  make build              Build collection artifact"
	@echo "  make import-galaxy      Validate built tarball with galaxy-importer"
	@echo "  make install            Install collection artifact"
	@echo "  make dev-install        Fast symlink install (changes take effect immediately)"
	@echo "  make publish            Publish to Ansible Galaxy"
	@echo ""
	@echo "CLEANUP:"
	@echo "  make clean              Remove build artifacts, caches"
	@echo "  make clean-all          Full cleanup + remove ansible-env"
	@echo ""
	@echo "CI/CD PIPELINES:"
	@echo "  make ci                 CI pipeline (validate + lint + security)"
	@echo "  make test-all           Full pipeline (ci + test + docs)"
	@echo ""

# ============================================================================
# Virtual Environment Check
# ============================================================================

check-venv:
	@if [ -z "$$VIRTUAL_ENV" ]; then \
		echo "⚠️ ERROR: Not in a virtual environment!"; \
		echo ""; \
		echo "Create and activate with:"; \
		echo "  python -m venv ansible-env"; \
		echo "  source ansible-env/bin/activate"; \
		exit 1; \
	fi

# ============================================================================
# Setup & Installation
# ============================================================================

setup:
	@echo "Checking Python version requirement..."
	@if ! $(PYTHON) --version 2>&1 | grep -qE '3\.(12|13|14)'; then \
		echo "⚠️ ERROR: Python 3.12+ required"; \
		echo "   Found: $$($(PYTHON) --version)"; \
		echo "   Install Python 3.12 or higher"; \
		exit 1; \
	fi
	@echo "✓ Python 3.12+ detected"
	@echo ""
	@if [ "$(IN_VENV)" = "yes" ]; then \
		echo "✓ Already in virtual environment: $$VIRTUAL_ENV"; \
	elif [ -d "$(VENV_DIR)" ]; then \
		echo "⚠️  Virtual environment exists but not activated"; \
		echo "   Activate with: source $(VENV_DIR)/bin/activate"; \
		echo "   Then run: make setup"; \
		exit 1; \
	else \
		echo "Creating virtual environment..."; \
		$(PYTHON) -m venv $(VENV_DIR); \
		echo "✓ Virtual environment created"; \
		echo ""; \
		echo "Activating virtual environment..."; \
		echo "⚠️  Please run the following commands:"; \
		echo "   source $(VENV_DIR)/bin/activate"; \
		echo "   make setup"; \
		exit 1; \
	fi
	@echo ""
	@echo "Setting up development environment..."
	$(PYTHON) -m pip install --upgrade pip setuptools wheel
	pip install -r requirements-dev.txt
	@echo ""
	@echo "✓ Development environment ready!"
	@echo ""

install-dev:
	@echo "Installing development dependencies..."
	$(PYTHON) -m pip install --upgrade pip setuptools wheel
	$(PYTHON) -m pip install -r requirements-dev.txt
	@echo "✓ Development dependencies installed"

# ============================================================================
# Code Quality & Linting
# ============================================================================

lint: flake8 pylint yamllint
	@echo "✓ All linting checks passed"

flake8:
	@echo "Running Flake8 strict code quality check..."
	flake8 plugins/modules/*.py plugins/httpapi/*.py plugins/module_utils/*.py \
		--config=.flake8 \
		--show-source \
		--statistics
	@echo "✓ Flake8 check passed"

pylint:
	@echo "Running PyLint code analysis..."
	pylint plugins/modules/*.py plugins/httpapi/*.py plugins/module_utils/*.py \
		--rcfile=.pylintrc \
		--reports=no
	@echo "✓ PyLint check passed"

yamllint:
	@echo "Running YAML linter..."
	yamllint -d '{rules: {line-length: {max: 160}}}' tests/playbooks/*.yml galaxy.yml
	@echo "✓ YAML linting passed"

format:
	@echo "Auto-formatting code with Black..."
	black plugins/ --line-length=120
	@echo "Sorting imports with isort..."
	isort plugins/ --profile black
	@echo "✓ Code formatting complete"

# ============================================================================
# Security Scanning
# ============================================================================

security: bandit audit
	@echo "✓ All security checks passed"

bandit:
	@echo "Running SAST scan with Bandit (detects hardcoded secrets, injection risks)..."
	bandit -r plugins/ -f json -o bandit-report.json || true
	bandit -r plugins/ -f txt
	@echo "✓ Bandit scan complete (report: bandit-report.json)"

audit:
	@echo "Running pip-audit (checking for CVEs in dependencies)..."
	pip-audit --desc
	@echo "✓ Dependency audit complete"

# ============================================================================
# Validation
# ============================================================================

validate: validate-syntax validate-ansible
	@echo "✓ All validation checks passed"

validate-syntax:
	@echo "Validating Python syntax..."
	python -m py_compile plugins/modules/*.py plugins/httpapi/*.py plugins/module_utils/*.py
	@echo "✓ Python syntax valid"

validate-ansible:
	@echo "Running Ansible syntax check..."
	@echo "Installing collection from source (pulls galaxy.yml dependencies)..."
	ansible-galaxy collection install . --force
	ansible-galaxy collection install -r tests/requirements.yml
	@if [ -f tests/inventory.yml ]; then \
		ansible-playbook --syntax-check -i tests/inventory.yml tests/playbooks/*.yml; \
	else \
		echo "Using example inventory for syntax check..."; \
		ansible-playbook --syntax-check -i tests/inventory.example.yml tests/playbooks/*.yml; \
	fi
	@echo "✓ Ansible syntax valid"

# ============================================================================
# Testing
# ============================================================================

test:
	@echo "Running all playbook tests (continues on failure; report under tests/reports/)..."
	ansible-galaxy collection install -r tests/requirements.yml
	@bash tests/run_playbook_tests.sh
	@echo "✓ All playbook tests passed"

# ============================================================================
# Documentation
# ============================================================================

docs:
	@echo "Building documentation..."
	@echo ""
	@echo "1️⃣  Auto-generating module documentation..."
	python tools/generate_docs.py
	@echo "✓ Module docs generated"
	@echo ""
	@echo "2️⃣  Validating mkdocs installation..."
	mkdocs --version
	@echo ""
	@echo "3️⃣  Building documentation site..."
	mkdocs build --clean
	@echo "✓ Documentation built (in site/)"

docs-serve:
	@echo "Serving documentation on http://localhost:8000"
	@echo "Press Ctrl+C to stop"
	mkdocs serve

# ============================================================================
# Build Collection
# ============================================================================

build: validate lint
	@echo "Building collection artifact..."
	ansible-galaxy collection build --force
	@echo "✓ Collection successfully built"

import-galaxy:
	@echo "Validating collection artifact with galaxy-importer (same checks as Ansible Galaxy)..."
	@ARTIFACT="$(COLLECTION_NAMESPACE)-$(COLLECTION_NAME)-$$(grep '^version:' galaxy.yml | awk '{print $$2}').tar.gz"; \
	test -f "$$ARTIFACT" || (echo "Artifact $$ARTIFACT not found; run make build first" >&2; exit 1); \
	$(PYTHON) -m galaxy_importer.main "$$ARTIFACT"
	@echo "✓ galaxy-importer validation passed"

install:
	@echo "Installing collection artifact..."
	ansible-galaxy collection install . --force
	@echo "✓ Collection successfully installed"

dev-install:
	@echo "Installing collection via symlink (fast development mode)..."
	@mkdir -p ~/.ansible/collections/ansible_collections/$(COLLECTION_NAMESPACE)
	@rm -f ~/.ansible/collections/ansible_collections/$(COLLECTION_NAMESPACE)/$(COLLECTION_NAME)
	@ln -sf $(PWD) ~/.ansible/collections/ansible_collections/$(COLLECTION_NAMESPACE)/$(COLLECTION_NAME)
	@echo "✓ Collection symlinked to $(PWD)"
	@echo "  Changes take effect immediately (no rebuild needed)"

publish: build
	@if [ -z "$(GALAXY_TOKEN)" ]; then \
		echo ""; \
		echo "⚠️ ERROR: GALAXY_TOKEN not set"; \
		echo ""; \
		echo "To publish to Ansible Galaxy, you need an API token:"; \
		echo ""; \
		echo "1. Get your token from:"; \
		echo "   https://galaxy.ansible.com/me/preferences"; \
		echo ""; \
		echo "2. Set the environment variable and retry:"; \
		echo "   export GALAXY_TOKEN=<your_api_token>"; \
		echo "   make publish"; \
		echo ""; \
		exit 1; \
	fi
	@echo "Publishing collection artifact to Ansible Galaxy..."
	ansible-galaxy collection publish $(COLLECTION_FILENAME) --api-key $(GALAXY_TOKEN)
	@echo "✓ Collection successfully published"

# ============================================================================
# Cleanup
# ============================================================================

clean:
	@echo "Cleaning up build artifacts..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache .mypy_cache .pylint.d htmlcov
	rm -rf $(COLLECTION_NAMESPACE)-$(COLLECTION_NAME)-*.tar.gz
	rm -f bandit-report.json
	rm -rf site/
	@echo "✓ Cleanup complete"

clean-all: clean
	@echo "Removing virtual environment and all dependencies..."
	@if [ "$(IN_VENV)" = "yes" ] && [ "$$VIRTUAL_ENV" = "$$(pwd)/$(VENV_DIR)" ]; then \
		echo "⚠️  You are currently in the virtual environment that will be deleted"; \
		echo "   Please deactivate first with: deactivate"; \
		echo "   Then run: make clean-all"; \
		exit 1; \
	fi
	rm -rf $(VENV_DIR)
	@echo "✓ Full cleanup complete"

# ============================================================================
# Complete Pipelines
# ============================================================================

ci: validate lint security
	@echo "✓ CI pipeline passed (validate + lint + security)"

test-all: validate lint security install test docs
	@echo "✓ Full test pipeline complete"

# ============================================================================
# Quick Aliases & Default
# ============================================================================

.DEFAULT_GOAL := help
