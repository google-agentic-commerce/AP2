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

### Code Quality

```bash
# Check code quality
make lint               # Run ruff linting
make format            # Auto-format code
make check             # Check formatting without changes
```

### Local CI Testing (Complete)

These commands run the exact same GitHub Actions workflows locally using `act`:

```bash
# Install act (one-time setup)
make act-install

# Run individual workflows
make act-test          # Run test workflow locally
make act-lint          # Run linter workflow locally
make act-docs          # Run docs workflow locally
make act-spellcheck    # Run spellcheck workflow locally

# Run all workflows
make act-all           # Run all workflows locally

# Clean up containers
make act-clean         # Remove act containers
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

### Local-CI Parity

The Makefile commands ensure that:
- `make test` runs the same tests as GitHub Actions
- `make act-test` runs the exact same workflow as the CI
- No environment differences between local and CI testing

This prevents the "works on my machine" problem and ensures reliable CI results.