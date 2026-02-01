# AGENT.md - AI Agent Context for AP2

This document provides context for AI coding assistants (Gemini, Claude,
Cursor, etc.) working on the Agent Payments Protocol (AP2) repository.

## Tool-Specific Setup

Some AI tools look for specific filenames (e.g., `GEMINI.md`, `CLAUDE.md`).
Create a local symbolic link to use this document with your preferred tool:

```bash
# For Gemini
ln -s AGENT.md GEMINI.md

# For Claude
ln -s AGENT.md CLAUDE.md

# For other tools (Cursor, Codex, etc.)
ln -s AGENT.md <TOOL_NAME>.md
```

> **Note**: Do not commit these symbolic links to the repository.

## Project Overview

**AP2 (Agent Payments Protocol)** is an open protocol enabling secure, verifiable payments between AI agents. This repository contains reference implementations, samples, and demos.

| Field | Value |
| --- | --- |
| License | Apache 2.0 |
| Languages | Python (primary), Go, Kotlin (Android) |
| Framework | Google Agent Development Kit (ADK) |
| LLM | Gemini 2.5 Flash |

## Repository Structure

```text
AP2/
├── src/ap2/types/           # Core protocol type definitions (Pydantic models)
│   ├── mandate.py           # IntentMandate, CartMandate, PaymentMandate
│   ├── payment_request.py   # W3C PaymentRequest types
│   ├── payment_receipt.py   # Receipt types
│   └── contact_picker.py    # Contact selection types
│
├── samples/
│   ├── python/
│   │   ├── src/roles/       # Agent implementations
│   │   │   ├── shopping_agent/           # User-facing shopping assistant
│   │   │   ├── merchant_agent/           # Product catalog & cart management
│   │   │   ├── credentials_provider_agent/  # Payment method management
│   │   │   └── merchant_payment_processor_agent/  # Payment processing
│   │   └── scenarios/       # Runnable demo scenarios
│   │       └── a2a/human-present/
│   │           ├── cards/   # Card payment scenario
│   │           └── x402/    # x402 payment scenario
│   ├── go/                  # Go implementation
│   └── android/             # Android shopping assistant app
│
├── docs/                    # MkDocs documentation
└── .gemini/                 # Gemini configuration
```

## Key Concepts

### Mandate Types

The protocol uses three types of **mandates** (signed authorization documents):

| Mandate | Signer | Purpose |
| --- | --- | --- |
| `IntentMandate` | User | Expresses user's purchase intent and constraints |
| `CartMandate` | Merchant | Guarantees cart contents and price (time-limited) |
| `PaymentMandate` | User | Authorizes specific payment for the cart |

### Agent Roles

| Agent | Port | Responsibility |
| --- | --- | --- |
| Shopping Agent | 8000 | Orchestrates user shopping flow, delegates to sub-agents |
| Merchant Agent | 8001 | Provides product catalog, creates CartMandates |
| Credentials Provider | 8002 | Manages user payment methods (wallet) |
| Payment Processor | 8003 | Processes payments on behalf of merchant |

### Protocol Flow (Human-Present)

```text
1. User → Shopping Agent: "I want to buy red shoes"
2. Shopping Agent → Merchant Agent: Search products
3. Merchant Agent → Shopping Agent: Return CartMandate (signed)
4. User confirms cart
5. Shopping Agent → Credentials Provider: Get payment methods
6. User selects payment method
7. Shopping Agent creates PaymentMandate (user signs)
8. Shopping Agent → Payment Processor: Process payment
9. Payment complete → Receipt generated
```

---

## Code Style Requirements

### Python (.ruff.toml)

**CRITICAL**: All Python code MUST follow Google Python Style Guide.

| Rule | Value |
| --- | --- |
| Line length | **80 characters** (hard limit) |
| Indentation | **4 spaces** |
| Target Python | **3.12+** |
| Quote style | **Single quotes** for strings |
| Docstrings | **Double quotes**, Google style |
| Imports | **Absolute only** (no relative imports) |

#### String Formatting

```python
# CORRECT
message = 'Hello, world'
name = 'AP2'

# WRONG
message = "Hello, world"  # Use single quotes
```

#### Docstrings (Google Style)

```python
def create_mandate(user_id: str, amount: float) -> PaymentMandate:
    """Creates a new payment mandate.

    Args:
        user_id: The unique identifier for the user.
        amount: The payment amount in USD.

    Returns:
        A new PaymentMandate instance.

    Raises:
        ValueError: If amount is negative.
    """
```

#### Imports

```python
# CORRECT - Absolute imports
from ap2.types.mandate import IntentMandate
from common.retrying_llm_agent import RetryingLlmAgent

# WRONG - Relative imports are banned
from .mandate import IntentMandate
from ..common import utils
```

#### Type Hints

```python
# Required for function signatures
def process_payment(
    mandate: PaymentMandate,
    timeout: int = 30,
) -> PaymentReceipt:
    ...
```

### Shell Scripts (.editorconfig)

| Rule | Value |
| --- | --- |
| Indentation | **2 spaces** |
| Shebang | `#!/bin/bash` |
| Error handling | `set -e` at script start |

### Markdown (.prettierrc, .markdownlint.json)

| Rule | Value |
| --- | --- |
| Line length | **80 characters** (prose wrap) |
| Indentation | **4 spaces** for lists |
| End of line | **LF** (Unix style) |
| Inline HTML | Allowed (MD033 disabled) |

---

## CI/CD Pipeline Checks

All PRs must pass these automated checks:

### 1. Conventional Commits (Required)

PR titles MUST follow semantic format:

```text
feat: add new payment method support
fix: resolve cart expiry calculation bug
docs: update API documentation
refactor: simplify mandate validation logic
test: add unit tests for PaymentProcessor
chore: update dependencies
```

**Valid types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

### 2. Linter Checks (Super-Linter)

| Language | Linter | Config |
| --- | --- | --- |
| Python | ruff | `.ruff.toml` |
| Markdown | markdownlint | `.github/linters/.markdownlint.json` |
| Shell | shellcheck | Enabled with SC1091, SC2086 ignored |
| YAML | yamllint | Default |

### 3. Spell Check (cspell)

- Configuration: `.cspell.json`
- Custom dictionary: `.cspell/custom-words.txt`
- Add new technical terms to custom-words.txt if needed

---

## Development Setup

### Prerequisites

- Python 3.10+ (3.12 recommended)
- [`uv`](https://docs.astral.sh/uv/) package manager
- **GitHub CLI (`gh`)**: For interacting with repository issues.
- **Node.js/npm**: For running `cspell` and `markdownlint-cli2`.
- Google API Key or Vertex AI credentials

### Environment Setup

```bash
# Clone repository
git clone https://github.com/google-agentic-commerce/AP2.git
cd AP2

# Create virtual environment
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e .
uv pip install -e samples/python

# Set API key (choose one method)
export GOOGLE_API_KEY='your_key'
# OR create .env file
echo "GOOGLE_API_KEY='your_key'" > .env

# For Vertex AI instead
export GOOGLE_GENAI_USE_VERTEXAI=true
export GOOGLE_CLOUD_PROJECT='your-project-id'
```

### Running Linters Locally

The project provides a convenience script to handle all formatting and linting. **Always run this script before committing.**

```bash
# Auto-formats Python, Shell, and Markdown files and fixes linting errors
bash scripts/format.sh
```

This script uses `ruff`, `shfmt`, and `markdownlint` to enforce code style. To check for issues without applying fixes, you can run the linters individually:

```bash
# Check Python files for issues
ruff check .

# Check Markdown files for issues
npx markdownlint-cli2 "**/*.md"
```

### Running Scenarios

```bash
# Card payment scenario
bash samples/python/scenarios/a2a/human-present/cards/run.sh

# x402 payment scenario
bash samples/python/scenarios/a2a/human-present/cards/run.sh --payment-method x402

# Open browser to http://0.0.0.0:8000
```

---

## Contributing Workflow

### 1. Before Starting

- [ ] Sign [Google CLA](https://cla.developers.google.com/) (required)
- [ ] Read [CONTRIBUTING.md](CONTRIBUTING.md)
- [ ] Follow [Google Open Source Guidelines](https://opensource.google/conduct/)

### 2. Branch Naming

```bash
feat/issue-49-add-gemini-md
fix/issue-107-add-run-sh
docs/update-readme
```

### 3. Commit Message Format

```bash
# Single line for simple changes
git commit -m "feat: add GEMINI.md for AI agent context"

# Multi-line for complex changes
git commit -m "fix: resolve Pydantic serialization in session state

- Add model_dump() before storing in ctx.state
- Update documentation with workaround
- Add unit test for serialization

Fixes #129"
```

### 4. PR Checklist

```markdown
- [ ] Follow CONTRIBUTING guide
- [ ] PR title uses Conventional Commits format
- [ ] All CI checks pass (linter, spellcheck, etc.)
- [ ] Code follows Google Python Style Guide
- [ ] Documentation updated if needed
- [ ] Tests added/updated if applicable

Fixes #<issue_number>
```

### 5. Code Review

- All PRs reviewed by `@google-agentic-commerce/google-payments-swe`
- Address reviewer feedback promptly
- Squash commits if requested

---

## Common Tasks

### Adding a New Agent

1. Create directory: `samples/python/src/roles/your_agent/`
1. Create `__init__.py`, `agent.py`, `tools.py`
1. Implement agent using `RetryingLlmAgent`:

    ```python
    from common.retrying_llm_agent import RetryingLlmAgent

    agent = RetryingLlmAgent(
        max_retries=5,
        model='gemini-2.5-flash',
        name='your_agent',
        instruction="""Your agent instructions here.""",
        tools=[your_tools],
        sub_agents=[],
    )
    ```

1. Register in scenario's `run.sh`

### Modifying Mandate Types

1. Edit `src/ap2/types/mandate.py`
1. Use Pydantic `Field()` with descriptions:

    ```python
    new_field: str = Field(
        ...,
        description='Clear description of the field purpose.',
    )
    ```

1. Update dependent agents
1. Run linters and tests

### Adding Custom Words for Spellcheck

Edit `.cspell/custom-words.txt` (alphabetical order):

<!-- cspell:ignore anotherword myword -->

```text
anotherword
myword
```

---

## Important Files

| File | Purpose |
| --- | --- |
| `CONTRIBUTING.md` | Contribution requirements |
| `CODE_OF_CONDUCT.md` | Community guidelines |
| `.ruff.toml` | Python linting configuration |
| `.cspell.json` | Spellcheck configuration |
| `.prettierrc` | Markdown/JSON formatting |
| `.editorconfig` | Editor settings |
| `pyproject.toml` | Root package config |
| `samples/python/pyproject.toml` | Samples package config |

---

## Dependencies

**Note**: The lists below are for quick reference. For the most accurate and up-to-date dependency information, always consult the `pyproject.toml` files in the root and `samples/python` directories.

### Core Package (`ap2`)

See `pyproject.toml`:

```toml
dependencies = ["pydantic"]
```

### Samples Package (`ap2-samples`)

See `samples/python/pyproject.toml`:

```toml
dependencies = [
    "a2a-sdk",         # Agent-to-Agent SDK
    "absl-py",         # Common Python utilities
    "ap2",             # Local workspace package for core types
    "flask",           # Web server for agents
    "flask-cors",      # Cross-Origin Resource Sharing for Flask
    "google-adk",      # Agent Development Kit
    "google-genai",    # Gemini API client
    "httpx",           # Async HTTP client
    "requests",        # Standard HTTP client
    "x402-a2a",        # x402 Protocol Support (from git)
]
```

---

## Finding and Reviewing Issues

**This is a dynamic section. Do not rely on a static list.**

Before creating a new issue or starting work on a feature/fix, it is critical to search the upstream repository for existing issues. This avoids duplicate work and ensures your contributions are relevant.

### How to Find Issues

The upstream repository is `google-agentic-commerce/AP2`. Use the GitHub CLI (`gh`) to query it at runtime.

**1. List Open Issues:**

```bash
# List all open issues
gh issue list --repo google-agentic-commerce/AP2 --state open

# Filter for good first issues or bugs
gh issue list --repo google-agentic-commerce/AP2 --label "help wanted"
gh issue list --repo google-agentic-commerce/AP2 --label "good first issue"
gh issue list --repo google-agentic-commerce/AP2 --label "bug"
```

**2. Search by Keyword:**

Before reporting a new bug or feature, search for keywords to see if a similar issue exists.

```bash
# Search for issues related to 'mandate'
gh issue list --repo google-agentic-commerce/AP2 --search "mandate"
```

**3. View an Issue:**

To get the full context of a specific issue:

```bash
gh issue view <issue-number> --repo google-agentic-commerce/AP2 --comments
```

### Contributor Labels

Look for these labels to find issues suitable for community contribution:

| Label | Description | Contributor Fit |
| --- | --- | --- |
| `help wanted` | Community contribution welcome | Good first issues |
| `good first issue` | Newcomer-friendly issue | Ideal for getting started |
| `bug` | Something isn't working | Fix existing functionality |
| `documentation` | Documentation improvements | Low complexity |
| `type: feature request` | New feature proposals | Moderate to high complexity |
| `samples` | Related to sample implementations | Good for learning |

### Before Starting Work

1. Check if someone is already working on the issue
2. Comment on the issue to express interest
3. Wait for maintainer acknowledgment before starting
4. Read related code and understand the context
5. Follow the contribution workflow in this document

---

## Maintaining This Document

This document should be updated when significant changes occur in the
repository. Keep it current to ensure AI agents can work effectively.

### When to Update

| Change Type | Action Required |
| --- | --- |
| Repository structure changes | Update "Repository Structure" section |
| New agent roles added | Update "Agent Roles" and "Common Tasks" |
| Code style rules change | Update "Code Style Requirements" section |
| CI/CD checks modified | Update "CI/CD Pipeline Checks" section |
| New dependencies added | Update "Dependencies" section |
| New contribution rules | Update "Contributing Workflow" section |

### Update Checklist

- [ ] Verify all file paths and directory structures are accurate
- [ ] Ensure code examples follow current style guidelines
- [ ] Check that all referenced config files still exist
- [ ] Update version numbers if applicable
- [ ] Run linters on this document before committing

---

## Resources

- [AP2 Protocol Documentation](https://ap2-protocol.org/)
- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Intro Video](https://goo.gle/ap2-video)
- [DeepWiki](https://deepwiki.com/google-agentic-commerce/AP2)
