# AGENT.md

This file provides an overview of the AP2 repository for AI agents and
automated contributors.

## Project Description

AP2 (Agent Payments Protocol) is an open protocol designed to enable AI agents
to securely interoperate and complete payments autonomously. It defines data
structures and flows for agentic commerce, where AI agents act on behalf of
users to browse, negotiate, and pay for goods and services.

The protocol can be implemented as an extension of the
[Agent2Agent (A2A) protocol](https://a2a-protocol.org/) or Model Context
Protocol (MCP).

## Repository Structure

```
AP2/
├── src/ap2/types/          # Core protocol type definitions (Python/Pydantic)
│   ├── mandate.py          # IntentMandate, CartMandate, PaymentMandate
│   ├── payment_request.py  # PaymentRequest, PaymentResponse (W3C-based)
│   ├── payment_receipt.py  # Payment receipt types
│   └── contact_picker.py   # Contact picker types
├── samples/
│   ├── python/
│   │   ├── scenarios/      # Runnable demo scenarios
│   │   │   └── a2a/
│   │   │       └── human-present/
│   │   │           ├── cards/
│   │   │           └── x402/
│   │   └── src/
│   │       ├── roles/      # Agent implementations by role
│   │       │   ├── shopping_agent/
│   │       │   ├── merchant_agent/
│   │       │   ├── merchant_payment_processor_agent/
│   │       │   └── credentials_provider_agent/
│   │       └── common/     # Shared utilities (A2A helpers, config, server)
│   ├── android/            # Android-based shopping assistant samples
│   └── go/                 # Go-based samples
├── docs/
│   ├── specification.md    # Full protocol specification
│   ├── glossary.md         # Term definitions
│   ├── faq.md
│   ├── roadmap.md
│   └── topics/             # Additional documentation topics
├── scripts/
│   └── format.sh           # Code formatting script
├── pyproject.toml          # Python package config (uv workspace)
├── mkdocs.yml              # Documentation site config
├── CONTRIBUTING.md          # Contribution guidelines and CLA info
├── CODE_OF_CONDUCT.md
├── SECURITY.md
└── LICENSE                  # Apache 2.0
```

## Key Concepts

### Mandates

Mandates are the core data structures that capture user intent, cart details,
and payment authorization. They flow through the protocol in sequence:

1. **IntentMandate** -- Captures the user's purchase intent in natural language,
   along with constraints such as allowed merchants, SKUs, refundability, and
   expiry. Defined in `src/ap2/types/mandate.py`.

2. **CartMandate** -- A merchant-signed cart containing items, prices (via W3C
   `PaymentRequest`), and expiry. The merchant's digital signature guarantees
   authenticity and price integrity.

3. **PaymentMandate** -- Contains the user's payment authorization, linking to
   the cart and including a verifiable credential (e.g., SD-JWT-VC) signed by
   the user.

### Roles

The protocol defines four key agent roles (implemented in
`samples/python/src/roles/`):

- **Shopping Agent (User Agent)** -- Interacts with the user, understands their
  needs, and coordinates the purchase flow.
- **Merchant Agent** -- Represents the seller, presents products, and negotiates
  the cart.
- **Merchant Payment Processor (MPP)** -- Constructs and sends transaction
  authorization messages to the payment ecosystem.
- **Credentials Provider (CP)** -- A secure entity (e.g., digital wallet) that
  manages the user's payment and identity credentials.

### Payment Flows

- **Human-Present (HP)** -- The user is actively involved, confirming intent
  and authorizing payment in real time. This is the primary flow supported in
  v0.1.
- **Human-Not-Present (HNP)** -- The agent acts autonomously based on
  pre-authorized mandates. Planned for v1.x.

## Running Samples

### Prerequisites

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) package
  manager
- A Google API key (from [AI Studio](http://aistudio.google.com/apikey)) or
  Vertex AI credentials

### Running a Scenario

```sh
# From the repository root:
export GOOGLE_API_KEY='your_key'
bash samples/python/scenarios/a2a/human-present/cards/run.sh
```

Each scenario directory contains a `README.md` with specific instructions and
a `run.sh` script.

### Installing the AP2 Types Package

```sh
uv pip install git+https://github.com/google-agentic-commerce/AP2.git@main
```

## Coding Conventions

- **Python version**: 3.10+
- **Type definitions**: Use [Pydantic](https://docs.pydantic.dev/) `BaseModel`
  with `Field` descriptors for all protocol types.
- **Formatting**: Run `bash scripts/format.sh --all` to format the codebase.
  This uses `ruff` for Python linting/formatting, `markdownlint` for Markdown,
  and `shfmt` for shell scripts.
- **Imports**: Use absolute imports (e.g., `from ap2.types.mandate import ...`).
- **License headers**: All source files must include the Apache 2.0 license
  header (see any file in `src/ap2/types/` for the template).
- **Package management**: The project uses `uv` workspaces. The root
  `pyproject.toml` defines the `ap2` types package; samples are a workspace
  member at `samples/python`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for full details. Key points:

- Sign the [Google CLA](https://cla.developers.google.com/) before
  contributing.
- All submissions require review via GitHub pull requests.
- Follow [Google's Open Source Community Guidelines](https://opensource.google/conduct/).
