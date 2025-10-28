# Agent Payments Protocol (AP2) - Go Implementation

This directory contains Go implementations of AP2-compliant agents, demonstrating how to build backend services for the Agent Payments Protocol using Go.

## Overview

The Go samples focus on backend agent infrastructure, providing implementations of:

*   **Merchant Agent:** Handles catalog searches and cart creation
*   **Credentials Provider Agent:** Manages payment credentials and user wallets
*   **Merchant Payment Processor Agent:** Processes payments and handles authorization

Unlike the Python samples which include complete end-to-end flows with Shopping Agents and web UIs, these Go samples demonstrate the backend services that merchants, payment processors, and credential providers would deploy.

## Prerequisites

*   Go 1.21 or higher
*   Make
*   Google API key from [Google AI Studio](https://aistudio.google.com/apikey)

## Quick Start

### 1. Set up your API key

```sh
export GOOGLE_API_KEY=your_key
```

Or create a `.env` file in this directory:

```sh
echo "GOOGLE_API_KEY=your_key" > .env
```

### 2. Run the sample

```sh
# From the repository root
bash samples/go/scenarios/a2a/human-present/cards/run.sh
```

This will start all three backend agents on ports 8001-8003.

## Project Structure

```
samples/go/
├── cmd/                          # Agent entry points
│   ├── merchant_agent/
│   ├── credentials_provider_agent/
│   └── merchant_payment_processor_agent/
├── pkg/
│   ├── ap2/                      # AP2 protocol types
│   │   └── types/               # Mandate and data structures
│   ├── common/                   # Shared utilities
│   │   ├── base_executor.go     # Base agent execution
│   │   ├── message_builder.go   # A2A message construction
│   │   ├── server.go            # HTTP/JSON-RPC server
│   │   └── function_resolver.go # Tool/function handling
│   └── roles/                   # Agent implementations
│       ├── merchant_agent/
│       ├── credentials_provider_agent/
│       └── merchant_payment_processor_agent/
└── scenarios/
    └── a2a/human-present/cards/  # Runnable scenario
        ├── README.md             # Detailed documentation
        └── run.sh               # Convenience script
```

## Available Commands

```sh
# Install dependencies
go mod download

# Build all agents
make build

# Run tests
make test

# Format code
make fmt

# Run individual agents (after building)
./bin/merchant_agent
./bin/credentials_provider_agent
./bin/merchant_payment_processor_agent
```

## Scenarios

### Human-Present Card Payments

Located in `scenarios/a2a/human-present/cards/`, this scenario demonstrates:

*   A2A protocol implementation in Go
*   Card payment support with DPAN tokens
*   OTP challenge flows
*   Full mandate lifecycle (Intent → Cart → Payment)

See the [scenario README](scenarios/a2a/human-present/cards/README.md) for detailed instructions.

## Interacting with the Agents

These agents expose HTTP/JSON-RPC endpoints that can be called by Shopping Agents or tested directly with cURL:

```sh
# Get agent info
curl -X POST http://localhost:8001/a2a/merchant_agent \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"agent.info","params":{},"id":1}'

# Search catalog
curl -X POST http://localhost:8001/a2a/merchant_agent \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"agent.invoke",
    "params":{
      "skill":"search_catalog",
      "input":{"shopping_intent":"{\"product_type\":\"coffee maker\"}"}
    },
    "id":2
  }'
```

For more examples, see the [scenario README](scenarios/a2a/human-present/cards/README.md).

## Key Features

### Type Safety

Go's static typing provides compile-time guarantees for AP2 protocol structures:

```go
type PaymentRequest struct {
    CartMandate    *CartMandate    `json:"cart_mandate"`
    PaymentMandate *PaymentMandate `json:"payment_mandate"`
    // ...
}
```

### Concurrent Request Handling

Built on Go's efficient concurrency model for handling multiple agent requests:

```go
server := common.NewServer(config.Port, executor)
server.Start()
```

### Modular Architecture

Each agent is independently deployable with clean separation of concerns:

*   `cmd/` - Entry points and initialization
*   `pkg/roles/` - Agent-specific business logic
*   `pkg/common/` - Shared infrastructure
*   `pkg/ap2/` - Protocol types and mandates

## Differences from Python Samples

| Feature | Python Samples | Go Samples |
|---------|----------------|------------|
| Shopping Agent | ✅ Included | ❌ Not included |
| Backend Agents | ✅ Included | ✅ Included |
| Web UI | ✅ Included | ❌ Not included |
| Purpose | End-to-end demos | Backend infrastructure |
| Framework | ADK + Gemini | Standard library + Gemini |

## Integration

These Go agents can be integrated with:

1. **Python Shopping Agents:** Configure Python samples to call these Go endpoints
2. **Custom Shopping Agents:** Build your own shopping agent in any language
3. **Testing Tools:** Use cURL or Postman for direct agent testing

For a complete shopping flow example, see the [Python human-present cards sample](../python/scenarios/a2a/human-present/cards/README.md).

## Development

### Adding a New Agent

1. Create agent entry point in `cmd/your_agent/`
2. Implement executor in `pkg/roles/your_agent/`
3. Define agent.json with capabilities and skills
4. Update Makefile to include new binary

### Running Tests

```sh
make test
```

### Code Quality

The project uses:

*   Go's built-in testing framework
*   Standard Go formatting (`gofmt`)
*   Static type checking

## Resources

*   [AP2 Protocol Documentation](../../README.md)
*   [Scenario-Specific README](scenarios/a2a/human-present/cards/README.md)
*   [Python Sample Comparison](../python/scenarios/a2a/human-present/cards/README.md)

## License

Copyright 2025 Google LLC. Licensed under the Apache License, Version 2.0.
