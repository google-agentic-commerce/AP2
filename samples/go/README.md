# Agent Payments Protocol (AP2) - Go Backend Agents

Production-ready Go implementations of AP2-compliant backend agents for the Agent Payments Protocol.

## Overview

This directory contains Go implementations of backend agents for the Agent Payments Protocol, demonstrating how to build AP2 services using Go. These agents implement the merchant-side, payment processing, and credentials provider roles in an AP2 transaction flow.

**What's included:**
- ✅ **Merchant Agent** - Product catalog and cart management
- ✅ **Credentials Provider Agent** - Payment credentials and wallet management
- ✅ **Merchant Payment Processor Agent** - Payment processing and authorization
- ❌ **Shopping Agent** - Not included (use [Python implementation](../python))

This design showcases **language-agnostic interoperability** - the Python Shopping Agent seamlessly communicates with these Go backend services, demonstrating that the AP2 protocol works across language boundaries.

## Quick Start

### Prerequisites

*   Go 1.21 or higher
*   Make
*   Google API key from [Google AI Studio](https://aistudio.google.com/apikey)

### 1. Configure API Key

```sh
export GOOGLE_API_KEY=your_key
```

Or create `.env` file:
```sh
echo "GOOGLE_API_KEY=your_key" > .env
```

### 2. Run the Agents

```sh
# From repository root
bash samples/go/scenarios/a2a/human-present/cards/run.sh
```

This starts three backend agents:
- **Merchant Agent**: `http://localhost:8001/a2a/merchant_agent`
- **Credentials Provider**: `http://localhost:8002/a2a/credentials_provider_agent`
- **Payment Processor**: `http://localhost:8003/a2a/merchant_payment_processor_agent`

## Complete Shopping Experience

To experience the full end-to-end shopping flow, use the **Python Shopping Agent** with these Go backend agents.

### Cross-Language Integration (Recommended)

**1. Start Go backend agents** (as shown above)

**2. Configure Python Shopping Agent** to use Go backends (in a separate terminal):

Edit `samples/python/src/roles/shopping_agent/remote_agents.py`:
```python
merchant_agent_client = PaymentRemoteA2aClient(
    name="merchant_agent",
    base_url="http://localhost:8001/a2a/merchant_agent",  # Go agent
    required_extensions={EXTENSION_URI},
)

credentials_provider_client = PaymentRemoteA2aClient(
    name="credentials_provider",
    base_url="http://localhost:8002/a2a/credentials_provider_agent",  # Go agent
    required_extensions={EXTENSION_URI},
)
```

**3. Start Python Shopping Agent:**

```sh
uv run --package ap2-samples adk web samples/python/src/roles
```

**4. Open browser** to `http://localhost:8000` and start shopping!

Now you have:
- **Frontend**: Python Shopping Agent with ADK web UI
- **Backend**: Go merchant, credentials, and payment processor agents

This demonstrates true protocol interoperability across languages.

## Project Structure

```
samples/go/
├── cmd/                                  # Agent entry points
│   ├── merchant_agent/
│   ├── credentials_provider_agent/
│   └── merchant_payment_processor_agent/
├── pkg/
│   ├── ap2/types/                       # AP2 protocol types
│   │   ├── mandate.go
│   │   ├── payment_request.go
│   │   └── contact_address.go
│   ├── common/                          # Shared infrastructure
│   │   ├── base_executor.go            # Base agent executor
│   │   ├── message_builder.go          # A2A message builder
│   │   ├── server.go                   # HTTP/JSON-RPC server
│   │   ├── function_resolver.go        # Skill/tool dispatcher
│   │   └── http_client.go              # A2A protocol client
│   └── roles/                           # Agent implementations
│       ├── merchant_agent/
│       │   ├── agent.json              # Capabilities & skills
│       │   ├── executor.go             # Business logic
│       │   ├── tools.go                # Agent tools
│       │   └── storage.go              # Product catalog
│       ├── credentials_provider_agent/
│       │   ├── agent.json
│       │   └── executor.go
│       └── merchant_payment_processor_agent/
│           ├── agent.json
│           └── executor.go
└── scenarios/a2a/human-present/cards/
    ├── README.md                        # Detailed documentation
    └── run.sh                           # Start all agents script
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

## Testing the Agents

### Option 1: Python Shopping Agent (Recommended)

See [Complete Shopping Experience](#complete-shopping-experience) above.

### Option 2: Direct HTTP Calls

Test agents directly with cURL:

```sh
# Get agent capabilities
curl -X POST http://localhost:8001/a2a/merchant_agent \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"agent.info","params":{},"id":1}'

# Search product catalog
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

# Get payment methods
curl -X POST http://localhost:8002/a2a/credentials_provider_agent \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "method":"agent.invoke",
    "params":{"skill":"get_payment_method"},
    "id":3
  }'
```

## Why Go for Backend Agents?

Go is exceptionally well-suited for building AP2 backend services:

| Feature | Benefit for AP2 |
|---------|-----------------|
| **Type Safety** | Compile-time validation of mandate structures |
| **Concurrency** | Efficient handling of concurrent A2A requests |
| **Performance** | Fast response times, low resource usage |
| **Single Binary** | Easy deployment, no dependencies |
| **Tooling** | Excellent testing, profiling, and debugging tools |

## What This Sample Demonstrates

### 1. Production-Quality Implementation

- Full A2A JSON-RPC protocol support
- Proper error handling and validation
- Type-safe mandate processing
- Concurrent request handling
- Clean architecture and separation of concerns

### 2. Language-Agnostic Protocol

- Go backend agents + Python shopping agent = seamless interoperability
- Protocol implementation is language-independent
- Any compliant agent can communicate with any other

### 3. AP2 Protocol Features

- **Mandate Lifecycle**: Intent → Cart → Payment flow
- **Payment Methods**: Card payments with DPAN tokenization
- **Security**: OTP challenges, signed mandates
- **Extensions**: AP2 base protocol + payment method extensions

### 4. Go-Specific Strengths

- Type-safe protocol structures
- High-performance JSON processing
- Efficient concurrent operations
- Production-ready error handling

## Scenarios

### Human-Present Card Payments

Location: `scenarios/a2a/human-present/cards/`

Demonstrates:
- A2A protocol implementation in Go
- Card payment with DPAN tokens
- OTP challenge flows
- Complete mandate lifecycle

See [scenario README](scenarios/a2a/human-present/cards/README.md) for detailed instructions.

## Development

### Running Tests

```sh
make test
```

### Code Quality

The project follows Go best practices:
- Built-in testing framework
- Standard formatting (`gofmt`)
- Static type checking
- Vendor dependencies management

### Adding a New Backend Agent

1. Create entry point: `cmd/new_agent/main.go`
2. Implement executor: `pkg/roles/new_agent/executor.go`
3. Define capabilities: `pkg/roles/new_agent/agent.json`
4. Add to Makefile: `make build` target
5. Update run script: `scenarios/.../run.sh`

## Architecture Decisions

### Why No Shopping Agent in Go?

**Short answer**: The Python Shopping Agent works perfectly with these Go backends, demonstrating true interoperability.

**Detailed reasoning**:

1. **Focus on Backend Excellence**: These agents showcase Go's strengths for backend services
2. **Avoid Framework Duplication**: Python has ADK (Agent Development Kit); reimplementing it in Go adds little value
3. **Demonstrate Interoperability**: Cross-language integration proves the protocol is truly language-agnostic
4. **Production Use Case**: Most production deployments will have shopping agents in user-facing languages (Python, JavaScript, Kotlin) calling backend services in Go/Java/Rust

### Design Patterns

- **Base Executor Pattern**: Common agent behavior abstraction
- **Dependency Injection**: Clean testable architecture
- **Message Builder**: Fluent API for A2A protocol messages
- **Function Resolver**: Dynamic skill/tool dispatch

## Integration Patterns

These Go backend agents support multiple deployment scenarios:

| Pattern | Description |
|---------|-------------|
| **Hybrid** | Python/JS shopping agent → Go backends |
| **Microservices** | Each agent deployed independently |
| **Kubernetes** | Container-based orchestration |
| **Serverless** | Wrap agents in cloud functions |
| **Monolith** | All agents in single binary (for development) |

## Comparison with Python

| Aspect | Python Sample | Go Sample |
|--------|--------------|-----------|
| **Shopping Agent** | ✅ ADK-powered with web UI | ❌ Not included |
| **Backend Agents** | ✅ Full implementation | ✅ Full implementation |
| **Primary Purpose** | End-to-end learning | Production backend services |
| **Best For** | Understanding AP2 flow | Building scalable services |
| **Framework** | ADK (Agent Development Kit) | Standard library + Gemini API |
| **Deployment** | Development/demo | Production-ready |

Both samples are complete and correct - they serve different purposes.

## Resources

- [Scenario Documentation](scenarios/a2a/human-present/cards/README.md)
- [AP2 Protocol Specification](../../README.md)
- [Python Sample (with Shopping Agent)](../python/scenarios/a2a/human-present/cards/README.md)
- [A2A Protocol](https://github.com/google-agentic-commerce/a2a)

## License

Copyright 2025 Google LLC. Licensed under the Apache License, Version 2.0.
