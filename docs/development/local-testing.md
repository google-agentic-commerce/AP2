# Local Testing Guide

This guide explains how to set up and run tests locally for the AP2 project, including how to test against your fork and run the same CI tests that GitHub runs.

## Quick Start

### Prerequisites

- Python 3.11 or higher
- [uv](https://astral.sh/uv/) package manager
- [act](https://github.com/nektos/act) for local GitHub Actions (optional)

### Setup

```bash
# Clone and enter the repository
git clone https://github.com/your-username/AP2.git
cd AP2

# Set up development environment
make setup
make install
```

## Testing Commands

### Local Testing (Fast)

These commands run tests directly using pytest:

```bash
# Run all tests
make test

# Run specific test suites
make test-unit          # Unit tests only
make test-integration   # Integration tests only
make test-scenarios     # Scenario tests only
make test-all          # All tests including slow ones
make test-cov          # Tests with coverage report
```

### Complete CI Testing (Locally-Useful Workflows)

```bash
# Recommended: Run locally-useful CI checks that match GitHub exactly
make ci-check-staged    # Test staged code before commit (locally-useful workflows)
make ci-check          # Test committed code (matches GitHub CI exactly)

# Individual CI workflows (add -staged for staged code)
make act-test[-staged]                    # Test workflow (3.11, 3.12, scenarios, lint)
make act-lint[-staged]                    # Lint Code Base workflow
make act-spellcheck[-staged]              # Check Spelling workflow
make act-docs[-staged]                    # Docs Build and Deploy workflow

# GitHub-specific workflows (skipped locally)
make act-conventional-commits[-staged]    # Conventional Commits workflow (GitHub-only)

# Quick local tools (not CI workflows)
make lint               # Run ruff linting only
make format            # Auto-format code
make check             # Check formatting without changes
```

### GitHub CI Workflow Mapping

Our local commands map to GitHub CI jobs with focus on locally-useful workflows:

#### Locally-Useful Workflows (Included in `ci-check`)

| GitHub CI Job | Local Command | Description | Status |
|---------------|---------------|-------------|---------|
| **Test / Test Suite (3.11)** | `make act-test[-staged]` | Python 3.11 test suite | ✅ Full support |
| **Test / Test Suite (3.12)** | `make act-test[-staged]` | Python 3.12 test suite | ✅ Full support |
| **Test / Scenario Tests** | `make act-test[-staged]` | End-to-end scenario tests | ✅ Full support |
| **Test / Lint and Format Check** | `make act-test[-staged]` | Ruff linting and formatting | ✅ Full support |
| **Check Spelling / spellcheck** | `make act-spellcheck[-staged]` | Spell checking with cspell | ✅ Full support |
| **Lint Code Base / Lint Code Base** | `make act-lint[-staged]` | Super-linter code analysis | ✅ Full support |
| **Docs Build and Deploy / build_and_deploy** | `make act-docs[-staged]` | MkDocs documentation build | ✅ Full support |

#### GitHub-Specific Workflows (Skipped Locally)

| GitHub CI Job | Local Command | Description | Status |
|---------------|---------------|-------------|---------|
| **Conventional Commits / Validate PR Title** | `make act-conventional-commits[-staged]` | PR title validation | ⚠️ Skipped (see below) |

### Why Conventional Commits is Skipped Locally

The **Conventional Commits** workflow is designed specifically for GitHub's PR environment and cannot run effectively in local development:

**Technical Limitations:**

- **Requires GitHub API access**: The workflow validates PR titles using GitHub's API
- **PR context dependency**: Needs pull request metadata that doesn't exist locally
- **GitHub token requirements**: Requires authenticated GitHub API access
- **Event-driven**: Triggered by GitHub PR events, not local git operations

**Local Testing Challenges:**

- No PR title to validate when testing staged/committed code locally
- GitHub API authentication complexity in local environment
- Workflow designed for GitHub's hosted runner environment
- Dependencies on GitHub-specific environment variables and contexts

**Workaround Implemented:**

- Command exists but displays informative skip message
- Explains that validation only applies to PR titles in GitHub CI
- Maintains command consistency while avoiding false failures
- Developers can still run the command to understand its purpose

**Alternative:**

- PR title validation happens automatically when creating PRs on GitHub
- Local commits use standard git commit message guidelines
- Focus on locally-actionable tests that improve code quality before pushing

### Act Setup and Utilities

```bash
# One-time setup
make act-install       # Install act for local GitHub Actions

# Utilities
make act-all           # Run all workflows (committed code only)
make act-clean         # Clean up act containers
```

## Fork Testing

When you have a pull request with test changes, you can test against your fork to ensure your new tests work correctly:

### Basic Fork Testing

```bash
# Test your fork's test workflow
make act-test-fork REPO=github.com/yourusername/AP2

# Test your fork's linting
make act-lint-fork REPO=github.com/yourusername/AP2

# Test your fork's documentation
make act-docs-fork REPO=github.com/yourusername/AP2

# Run all workflows against your fork
make act-all-fork REPO=github.com/yourusername/AP2
```

### Example Workflow

When working on a feature that adds new tests:

1. **Develop locally:**

   ```bash
   # Work on your feature and tests
   make test-unit        # Quick feedback loop
   ```

2. **Test against main repository:**

   ```bash
   # Ensure you don't break existing CI
   make act-test         # Run current CI tests locally
   ```

3. **Push to your fork and test:**

   ```bash
   git push origin feature-branch

   # Test your fork's CI with your new tests
   make act-test-fork REPO=github.com/yourusername/AP2
   ```

4. **Create pull request** knowing both old and new tests pass

## Scenarios

The project includes end-to-end scenarios that demonstrate the AP2 protocol:

```bash
# Set your Google API key (required for scenarios)
export GOOGLE_API_KEY=your_key_here

# Run specific scenarios
make scenarios-cards   # Human-present cards scenario
make scenarios-x402    # Human-present x402 scenario (when available)
```

## Documentation

```bash
# Build and serve documentation locally
make docs              # Build docs
make serve-docs        # Serve at http://localhost:8000
```

## Troubleshooting

### Common Issues

**"No module named 'a2a'" error:**

- Ensure you ran `make install` which installs all workspace dependencies
- The command should be `uv sync --package ap2-samples --extra test`

**Act fails with authentication errors:**

- This is normal for some GitHub Actions
- Use `make act-clean` to clean up and try again
- Act runs in containers, so some GitHub-specific features may not work locally

**Python version compatibility:**

- This project requires Python 3.11+ due to modern type annotations
- Use `python --version` to check your version

### Getting Help

1. **Check the logs:** Most commands have verbose output
2. **Clean environment:** Try `make clean` and `make install`
3. **Check dependencies:** Ensure `uv` and `act` are installed correctly

## Architecture Notes

### Testing Strategy

- **Unit tests** (`tests/unit/`): Test individual AP2 protocol types and utilities
- **Integration tests** (`tests/integration/`): Test agent imports and tool integration
- **Scenario tests** (`tests/scenarios/`): Test that sample scenarios can be imported and run

### CI Philosophy

Our CI uses a **staged enforcement approach**:

1. **Warning phase**: Linting issues are reported but don't fail CI
2. **Enforcement phase**: Once codebase is clean, linting will fail CI
3. **Real dependencies**: Integration tests use actual a2a-sdk, not mocks

This allows us to establish robust testing infrastructure while the project evolves.

### Complete Local-CI Parity

Our testing infrastructure provides **comprehensive GitHub CI coverage** for locally-useful workflows:

- **7 of 8 GitHub CI workflows** with full local support
- **1 GitHub-specific workflow** appropriately skipped with clear reasoning
- **Identical workflow files** used locally and in CI via act
- **Same dependencies and environments** via Docker containers
- **Pre-commit and post-commit testing** options available
- **Zero environment differences** between local and CI testing for supported workflows

This approach eliminates "works on my machine" problems while focusing on actionable local testing. GitHub-specific workflows (like PR title validation) run automatically in the GitHub environment where they're designed to operate.

### Critical: Local Testing Workflow

**Recommended Workflow (Test Locally-Useful CI Jobs Before Commit):**

1. **Make your changes and stage them** (`git add`)
2. **Run `make ci-check-staged`** to test 7 locally-useful GitHub CI workflows against staged code
3. **Fix any issues found**
4. **Commit your changes** (`git commit`)
5. **Run `make ci-check`** to verify committed code matches GitHub CI exactly
6. **Only push after all locally-actionable CI checks pass**

**Alternative Workflow (Test After Commit):**

1. **Stage and commit your changes**
2. **Run `make ci-check` to test exact code state that GitHub will test**
3. **Fix issues with additional commits if needed**
4. **Push after local tests pass**

**Key Commands:**

- `make ci-check-staged` - Tests 7 locally-useful GitHub CI workflows against staged/working code
- `make ci-check` - Tests 7 locally-useful GitHub CI workflows against committed code (matches useful GitHub CI exactly)

**Individual Workflow Commands:**

- `make act-test-staged` - Test workflow (covers 4 GitHub jobs: Test Suite 3.11, 3.12, Scenarios, Lint & Format)
- `make act-spellcheck-staged` - Spellcheck workflow
- `make act-lint-staged` - Lint Code Base workflow
- `make act-docs-staged` - Docs Build and Deploy workflow
- `make act-conventional-commits-staged` - Conventional Commits workflow (GitHub-only, skipped locally)

This ensures our local testing covers all actionable GitHub CI workflows while giving flexibility to test before committing. GitHub-specific workflows run automatically in their intended environment.
