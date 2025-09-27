# Makefile for AP2 - Agent Payments Protocol
# Local development commands that match GitHub CI exactly

.PHONY: help install test test-unit test-integration test-scenarios test-all test-cov
.PHONY: lint format check setup ci-check ci-check-staged
.PHONY: scenarios-cards scenarios-x402 docs serve-docs
.PHONY: act-install act-test act-lint act-spellcheck act-docs act-all act-clean act-lint-staged-debug
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
	@echo "CI Testing (Recommended - All 8 GitHub CI Jobs):"
	@echo "  make ci-check-staged  - Run all 8 CI checks on staged code (before commit)"
	@echo "  make ci-check         - Run all 8 CI checks on committed code (matches GitHub CI)"
	@echo ""
	@echo "Code Quality (Individual Tools):"
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
	@echo "Individual CI Workflows (add -staged for staged code):"
	@echo "  make act-test[-staged]              - Test workflow (3.11, 3.12, scenarios, lint)"
	@echo "  make act-lint[-staged]              - Lint Code Base workflow"
	@echo "  make act-spellcheck[-staged]        - Check Spelling workflow"
	@echo "  make act-conventional-commits[-staged] - Conventional Commits workflow"
	@echo "  make act-docs[-staged]              - Docs Build and Deploy workflow"
	@echo ""
	@echo "Local CI (using act):"
	@echo "  make act-install    - Install act for local GitHub Actions"
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
	@echo "  make act-clean      - Clean up act containers"

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

# Universal CI testing commands - focuses on locally-useful workflows
ci-check: ## Run locally-useful CI checks against committed code
	@echo "Running locally-useful CI checks against committed code..."
	@echo "1. Running Test workflow (Test Suite 3.11, 3.12, Scenario Tests, Lint and Format Check)..."
	make act-test
	@echo "2. Running Spellcheck..."
	make act-spellcheck
	@echo "3. Running Lint Code Base..."
	make act-lint
	@echo "4. Running Docs Build..."
	make act-docs
	@echo "5. Skipping GitHub-specific checks (Conventional Commits)..."
	make act-conventional-commits
	@echo "All locally-useful CI checks completed!"

ci-check-staged: ## Run locally-useful CI checks against staged code (pre-commit testing)
	@echo "Running locally-useful CI checks against staged/working code..."
	@echo "1. Running Test workflow (Test Suite 3.11, 3.12, Scenario Tests, Lint and Format Check)..."
	make act-test-staged
	@echo "2. Running Spellcheck..."
	make act-spellcheck-staged
	@echo "3. Running Lint Code Base..."
	make act-lint-staged
	@echo "4. Running Docs Build..."
	make act-docs-staged
	@echo "5. Skipping GitHub-specific checks (Conventional Commits)..."
	make act-conventional-commits-staged
	@echo "All locally-useful CI checks completed!"

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

act-test: ## Run test workflow against committed code
	@echo "Running test workflow against committed code..."
	act -W .github/workflows/test.yml --rm

act-lint: ## Run super-linter directly with Docker using exact GitHub CI configuration
	@echo "Running super-linter directly with Docker..."
	@echo "Note: Uses exact GitHub CI environment variables from .github/workflows/linter.yaml"
	@echo "Checking for super-linter image..."
	@if ! docker images ghcr.io/super-linter/super-linter:slim-latest | grep -q slim-latest; then \
		echo "Super-linter image not found locally. Pre-pulling..."; \
		echo "This may take 3-5 minutes for first download (~400-800MB)"; \
		docker pull ghcr.io/super-linter/super-linter:slim-latest || echo "Pull failed, continuing anyway..."; \
	else \
		echo "✓ Super-linter image found locally"; \
	fi
	@echo "Running super-linter on current directory..."
	docker run --rm \
		-e DEFAULT_BRANCH=main \
		-e LOG_LEVEL=WARN \
		-e SHELLCHECK_OPTS="-e SC1091 -e 2086" \
		-e VALIDATE_ALL_CODEBASE=false \
		-e FILTER_REGEX_EXCLUDE="^(\\.github/|\\.vscode/|samples/).*|CODE_OF_CONDUCT.md|CHANGELOG.md" \
		-e VALIDATE_PYTHON_BLACK=false \
		-e VALIDATE_PYTHON_FLAKE8=false \
		-e VALIDATE_PYTHON_ISORT=false \
		-e VALIDATE_PYTHON_MYPY=false \
		-e VALIDATE_PYTHON_PYLINT=false \
		-e VALIDATE_CHECKOV=false \
		-e VALIDATE_NATURAL_LANGUAGE=false \
		-e MARKDOWN_CONFIG_FILE=".markdownlint.json" \
		-e VALIDATE_MARKDOWN_PRETTIER=false \
		-e VALIDATE_JAVASCRIPT_PRETTIER=false \
		-e VALIDATE_JSON_PRETTIER=false \
		-e VALIDATE_YAML_PRETTIER=false \
		-e VALIDATE_GIT_COMMITLINT=false \
		-e VALIDATE_GITHUB_ACTIONS_ZIZMOR=false \
		-e VALIDATE_JSCPD=false \
		-e RUN_LOCAL=true \
		-v $$(pwd):/tmp/lint \
		ghcr.io/super-linter/super-linter:slim-latest

act-spellcheck: ## Run spellcheck workflow against committed code
	@echo "Running spellcheck workflow against committed code..."
	act -W .github/workflows/spellcheck.yaml --rm

act-spellcheck-staged: ## Run spellcheck workflow against staged code
	@echo "Running spellcheck workflow against staged/working code..."
	act -W .github/workflows/spellcheck.yaml --rm --bind

act-lint-staged: ## Run super-linter on ONLY staged files using exact GitHub CI configuration
	@echo "Running super-linter on STAGED files only..."
	@echo "Note: Uses exact GitHub CI environment variables from .github/workflows/linter.yaml"
	@STAGED_FILES=$$(git diff --cached --name-only); \
	if [ -z "$$STAGED_FILES" ]; then \
		echo "No staged files found. Nothing to lint."; \
		exit 0; \
	fi; \
	echo "Staged files to lint:"; \
	echo "$$STAGED_FILES"; \
	echo "Checking for super-linter image..."; \
	if ! docker images ghcr.io/super-linter/super-linter:slim-latest | grep -q slim-latest; then \
		echo "Super-linter image not found locally. Pre-pulling..."; \
		echo "This may take 3-5 minutes for first download (~400-800MB)"; \
		docker pull ghcr.io/super-linter/super-linter:slim-latest || echo "Pull failed, continuing anyway..."; \
	else \
		echo "✓ Super-linter image found locally"; \
	fi; \
	echo "Running super-linter on staged files only..."; \
	docker run --rm \
		-e DEFAULT_BRANCH=main \
		-e LOG_LEVEL=WARN \
		-e SHELLCHECK_OPTS="-e SC1091 -e 2086" \
		-e VALIDATE_ALL_CODEBASE=false \
		-e FILTER_REGEX_EXCLUDE="^(.venv/|.claude/|.git/|.github/|.vscode/|samples/|tests/|src/).*" \
		-e VALIDATE_PYTHON_BLACK=false \
		-e VALIDATE_PYTHON_FLAKE8=false \
		-e VALIDATE_PYTHON_ISORT=false \
		-e VALIDATE_PYTHON_MYPY=false \
		-e VALIDATE_PYTHON_PYLINT=false \
		-e VALIDATE_CHECKOV=false \
		-e VALIDATE_NATURAL_LANGUAGE=false \
		-e MARKDOWN_CONFIG_FILE=".markdownlint.json" \
		-e VALIDATE_MARKDOWN_PRETTIER=false \
		-e VALIDATE_JAVASCRIPT_PRETTIER=false \
		-e VALIDATE_JSON_PRETTIER=false \
		-e VALIDATE_YAML_PRETTIER=false \
		-e VALIDATE_GIT_COMMITLINT=false \
		-e VALIDATE_GITHUB_ACTIONS_ZIZMOR=false \
		-e VALIDATE_JSCPD=false \
		-e VALIDATE_BIOME_FORMAT=false \
		-e VALIDATE_BIOME_LINT=false \
		-e VALIDATE_GITHUB_ACTIONS=false \
		-e VALIDATE_PYTHON_RUFF_FORMAT=false \
		-e VALIDATE_PYTHON_RUFF=false \
		-e RUN_LOCAL=true \
		-v $$(pwd):/tmp/lint \
		ghcr.io/super-linter/super-linter:slim-latest

act-lint-staged-debug: ## Run linter workflow against staged code with maximum debugging
	@echo "Running linter workflow with MAXIMUM debugging enabled..."
	@echo "This will show sensitive information including tokens!"
	@echo "Checking for super-linter image..."
	@if ! docker images ghcr.io/super-linter/super-linter:slim-v8.1.0 | grep -q slim-v8.1.0; then \
		echo "Super-linter image not found locally. Pre-pulling to avoid timeout..."; \
		echo "This may take 3-5 minutes for first download (~400-800MB)"; \
		docker pull ghcr.io/super-linter/super-linter:slim-v8.1.0 || echo "Pull failed, continuing anyway..."; \
	else \
		echo "✓ Super-linter image found locally"; \
	fi
	@echo "Setting up mock GitHub PR event for local act environment..."
	@if ! command -v gh >/dev/null 2>&1; then \
		echo "Error: GitHub CLI (gh) is required for super-linter local testing"; \
		echo "Install with: https://cli.github.com/"; \
		exit 1; \
	fi
	@if ! gh auth status >/dev/null 2>&1; then \
		echo "Error: GitHub CLI not authenticated. Run 'gh auth login' first"; \
		exit 1; \
	fi
	@echo "✓ GitHub CLI authenticated, getting token..."
	@GITHUB_TOKEN=$$(gh auth token); \
	HEAD_SHA=$$(git rev-parse HEAD); \
	BASE_SHA=$$(git rev-parse HEAD~1); \
	echo "Debug: HEAD_SHA=$$HEAD_SHA BASE_SHA=$$BASE_SHA"; \
	echo "Debug: Token length=$$(echo $$GITHUB_TOKEN | wc -c)"; \
	echo "{\"pull_request\":{\"number\":1,\"commits\":1,\"base\":{\"ref\":\"main\",\"sha\":\"$$BASE_SHA\"},\"head\":{\"ref\":\"ci-testing-setup\",\"sha\":\"$$HEAD_SHA\"}},\"number\":1}" > /tmp/mock-pr-event.json; \
	echo "Debug: Event file contents:"; \
	cat /tmp/mock-pr-event.json; \
	echo ""; \
	echo "Debug: Running act command with all debugging enabled..."; \
	act -W .github/workflows/linter.yaml --rm --bind --eventpath /tmp/mock-pr-event.json \
		--env GITHUB_TOKEN="$$GITHUB_TOKEN" \
		--env GITHUB_EVENT_NAME=pull_request \
		--env LOG_LEVEL=TRACE \
		--env ACTIONS_STEP_DEBUG=true \
		--env ACTIONS_RUNNER_DEBUG=true \
		--env CREATE_LOG_FILE=true \
		--env ENABLE_GITHUB_ACTIONS_GROUP_TITLE=true \
		--verbose \
		--insecure-secrets

act-conventional-commits: ## Run conventional commits workflow against committed code
	@echo "Skipping conventional commits check (GitHub-specific, not useful for local development)"
	@echo "✓ This workflow only validates PR titles in GitHub CI environment"

act-conventional-commits-staged: ## Run conventional commits workflow against staged code
	@echo "Skipping conventional commits check (GitHub-specific, not useful for local development)"
	@echo "✓ This workflow only validates PR titles in GitHub CI environment"

act-docs: ## Run docs workflow against committed code
	@echo "Running docs workflow against committed code..."
	act -W .github/workflows/docs.yml --rm

act-docs-staged: ## Run docs workflow against staged code
	@echo "Running docs workflow against staged/working code..."
	act -W .github/workflows/docs.yml --rm --bind

act-test-staged: ## Run test workflow against staged code
	@echo "Running test workflow against staged/working code..."
	act -W .github/workflows/test.yml --rm --bind

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

