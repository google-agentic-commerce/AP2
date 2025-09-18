# Makefile for AP2 - Agent Payments Protocol
# This provides commands similar to your Justfile for Rust projects

.PHONY: help install test test-unit test-integration test-scenarios test-all
.PHONY: lint format check clean setup act-install act-test act-lint act-all act-clean
.PHONY: scenarios-cards scenarios-x402 docs serve-docs
.PHONY: act-test-fork act-lint-fork act-docs-fork act-spellcheck-fork act-all-fork

# Default target
help: ## Show this help message
	@echo "AP2 Development Commands"
	@echo ""
	@echo "Setup and Installation:"
	@echo "  make setup          - Set up development environment"
	@echo "  make install        - Install dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test           - Run all tests"
	@echo "  make test-unit      - Run unit tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make test-scenarios - Run scenario tests only"
	@echo "  make test-cov       - Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           - Lint code with ruff"
	@echo "  make format         - Format code with ruff and shell scripts"
	@echo "  make check          - Run linting and format check"
	@echo ""
	@echo "Scenarios:"
	@echo "  make scenarios-cards - Run human-present cards scenario"
	@echo "  make scenarios-x402  - Run human-present x402 scenario"
	@echo ""
	@echo "Documentation:"
	@echo "  make docs           - Build documentation"
	@echo "  make serve-docs     - Serve documentation locally"
	@echo ""
	@echo "Local CI (using act):"
	@echo "  make act-install    - Install act for local GitHub Actions"
	@echo "  make act-test       - Run test workflow locally"
	@echo "  make act-lint       - Run lint workflow locally"
	@echo "  make act-all        - Run all workflows locally"
	@echo "  make act-clean      - Clean up act containers"
	@echo ""
	@echo "Fork Testing (for testing against your fork):"
	@echo "  make act-test-fork REPO=github.com/username/AP2"
	@echo "  make act-lint-fork REPO=github.com/username/AP2"
	@echo "  make act-docs-fork REPO=github.com/username/AP2"
	@echo "  make act-all-fork REPO=github.com/username/AP2"
	@echo ""
	@echo "Utility:"
	@echo "  make clean          - Clean up build artifacts"

# Setup and Installation
setup: ## Set up development environment
	@echo "Setting up AP2 development environment..."
	@if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment..."; \
		uv venv; \
	fi
	@echo "Virtual environment ready."
	@echo "To activate: source .venv/bin/activate"

install: ## Install dependencies
	@echo "Installing dependencies..."
	uv sync --package ap2-samples --extra test
	uv pip install -e .

# Testing - Simple and clean approach
test: test-unit test-integration ## Run all tests

test-unit: ## Run unit tests only
	@echo "Running unit tests..."
	uv run pytest tests/unit -v

test-integration: ## Run integration tests only
	@echo "Running integration tests..."
	uv run pytest tests/integration -v -m "not slow"

test-scenarios: ## Run scenario tests only
	@echo "Running scenario tests..."
	uv run pytest tests/scenarios -v

test-all: ## Run all tests including slow ones
	@echo "Running all tests (including slow ones)..."
	uv run pytest tests/ -v

test-cov: ## Run tests with coverage report
	@echo "Running tests with coverage..."
	uv run pytest tests/ -v --cov=src --cov=samples/python/src --cov-report=html --cov-report=term

# Code Quality
lint: ## Lint code with ruff
	@echo "Linting code..."
	uv run ruff check .

format: ## Format code with ruff and shell scripts
	@echo "Formatting code..."
	bash scripts/format.sh --all

check: ## Run linting and format check
	@echo "Checking code quality..."
	uv run ruff check .
	uv run ruff format --check .

# Scenarios
scenarios-cards: ## Run human-present cards scenario
	@echo "Running human-present cards scenario..."
	@if [ -z "$$GOOGLE_API_KEY" ]; then \
		echo "Error: GOOGLE_API_KEY environment variable is required"; \
		exit 1; \
	fi
	bash samples/python/scenarios/a2a/human-present/cards/run.sh

scenarios-x402: ## Run human-present x402 scenario
	@echo "Running human-present x402 scenario..."
	@if [ -z "$$GOOGLE_API_KEY" ]; then \
		echo "Error: GOOGLE_API_KEY environment variable is required"; \
		exit 1; \
	fi
	bash samples/python/scenarios/a2a/human-present/x402/run.sh

# Documentation
docs: ## Build documentation
	@echo "Building documentation..."
	mkdocs build

serve-docs: ## Serve documentation locally
	@echo "Serving documentation at http://localhost:8000"
	mkdocs serve

# Local CI using act (equivalent to your Justfile act commands)
act-install: ## Install act for running GitHub Actions locally
	@echo "Installing act (GitHub Actions runner)..."
	@echo "Note: This will prompt for your sudo password to install act system-wide."
	curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
	@echo "Act installed successfully. You can now run CI tests locally."

act-test: ## Run test workflow locally with act
	@echo "Running test workflow locally..."
	act -W .github/workflows/test.yml --rm

act-lint: ## Run linter workflow locally with act
	@echo "Running linter workflow locally..."
	act -W .github/workflows/linter.yaml --rm

act-spellcheck: ## Run spellcheck workflow locally with act
	@echo "Running spellcheck workflow locally..."
	act -W .github/workflows/spellcheck.yaml --rm

act-docs: ## Run docs workflow locally with act
	@echo "Running docs workflow locally..."
	act -W .github/workflows/docs.yml --rm

act-all: ## Run all workflows locally with act
	@echo "Running all workflows locally..."
	act -W .github/workflows/test.yml --rm
	act -W .github/workflows/linter.yaml --rm
	act -W .github/workflows/spellcheck.yaml --rm
	act -W .github/workflows/docs.yml --rm

# Fork-specific commands for testing new tests against your own fork to ensure they don't break CI
act-test-fork: ## Run test workflow against fork
	@if [ -z "$(REPO)" ]; then \
		echo "Usage: make act-test-fork REPO=github.com/username/AP2"; \
		exit 1; \
	fi
	act -W .github/workflows/test.yml --rm --env GITHUB_REPOSITORY=$(REPO)

act-lint-fork: ## Run lint workflow against fork
	@if [ -z "$(REPO)" ]; then \
		echo "Usage: make act-lint-fork REPO=github.com/username/AP2"; \
		exit 1; \
	fi
	act -W .github/workflows/linter.yaml --rm --env GITHUB_REPOSITORY=$(REPO)

act-docs-fork: ## Run docs workflow against fork
	@if [ -z "$(REPO)" ]; then \
		echo "Usage: make act-docs-fork REPO=github.com/username/AP2"; \
		exit 1; \
	fi
	act -W .github/workflows/docs.yml --rm --env GITHUB_REPOSITORY=$(REPO)

act-spellcheck-fork: ## Run spellcheck workflow against fork
	@if [ -z "$(REPO)" ]; then \
		echo "Usage: make act-spellcheck-fork REPO=github.com/username/AP2"; \
		exit 1; \
	fi
	act -W .github/workflows/spellcheck.yaml --rm --env GITHUB_REPOSITORY=$(REPO)

act-all-fork: ## Run all workflows against fork
	@if [ -z "$(REPO)" ]; then \
		echo "Usage: make act-all-fork REPO=github.com/username/AP2"; \
		exit 1; \
	fi
	@echo "Running all workflows against fork $(REPO)..."
	act -W .github/workflows/test.yml --rm --env GITHUB_REPOSITORY=$(REPO)
	act -W .github/workflows/linter.yaml --rm --env GITHUB_REPOSITORY=$(REPO)
	act -W .github/workflows/spellcheck.yaml --rm --env GITHUB_REPOSITORY=$(REPO)
	act -W .github/workflows/docs.yml --rm --env GITHUB_REPOSITORY=$(REPO)

act-clean: ## Clean up act containers
	@echo "Current act containers:"
	-docker ps --filter "name=act-" || true
	@echo "Stopping and removing act containers..."
	-docker stop $$(docker ps -q --filter "name=act-") 2>/dev/null || true
	-docker rm $$(docker ps -aq --filter "name=act-") 2>/dev/null || true
	@echo "Act containers cleaned up."

# Utility
clean: ## Clean up build artifacts
	@echo "Cleaning up build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete