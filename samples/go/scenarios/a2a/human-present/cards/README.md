# Agent Payments Protocol Go Sample: Backend Agent Infrastructure

This sample demonstrates Go implementations of backend agents for the AP2 protocol in a human present transaction using a card as the payment method.

## Overview

This Go sample provides production-ready backend agent infrastructure for the Agent Payments Protocol. It showcases how to build AP2-compliant services in Go, focusing on the backend components typically operated by merchants, payment processors, and credential providers.

The sample includes three backend agents but does **not** include a Shopping Agent. This design choice demonstrates the protocol's **language-agnostic interoperability** - the Python Shopping Agent can seamlessly communicate with these Go backend services.

## Agents Implemented

*   **Merchant Agent** (`http://localhost:8001`)
    - Handles product catalog queries
    - Creates and manages cart mandates
    - Exposes `search_catalog` skill for shopping intents
    - Supports AP2 and Sample Card Network extensions

*   **Credentials Provider Agent** (`http://localhost:8002`)
    - Manages user payment credentials and wallet
    - Provides payment method details
    - Supplies tokenized (DPAN) card information
    - Handles payment authorization

*   **Merchant Payment Processor Agent** (`http://localhost:8003`)
    - Processes payments on behalf of merchants
    - Implements OTP challenge mechanism
    - Handles payment authorization and settlement

## What This Sample Demonstrates

1. **Production-Quality Go Implementation**
   - Full A2A JSON-RPC protocol implementation
   - Type-safe mandate and message structures
   - Concurrent request handling
   - Proper error handling and validation

2. **Language-Agnostic Protocol**
   - Go backend agents work seamlessly with Python Shopping Agent
   - Demonstrates true interoperability across languages
   - Shows protocol is implementation-independent

3. **AP2 Protocol Features**
   - Complete mandate lifecycle (Intent → Cart → Payment)
   - Card payment support with DPAN tokens
   - OTP challenge flows
   - Extension mechanism (AP2 + payment method extensions)

4. **Backend Service Patterns**
   - Modular, independently deployable services
   - Clean separation of concerns
   - Go's strengths for backend services (concurrency, type safety, performance)

## Running the Sample

### Prerequisites

*   Go 1.21 or higher
*   Make
*   Google API key from [Google AI Studio](https://aistudio.google.com/apikey)

### Quick Start

1. **Set up your API key:**

   ```sh
   export GOOGLE_API_KEY=your_key
   ```

   Or create a `.env` file in `samples/go/`:
   ```sh
   echo "GOOGLE_API_KEY=your_key" > samples/go/.env
   ```

2. **Run all backend agents:**

   ```sh
   # From repository root
   bash samples/go/scenarios/a2a/human-present/cards/run.sh
   ```

   This starts all three backend agents:
   - Merchant Agent on port 8001
   - Credentials Provider on port 8002
   - Payment Processor on port 8003

### Manual Build and Run

```sh
cd samples/go

# Install dependencies
go mod download

# Build all agents
make build

# Run individual agents (in separate terminals)
./bin/merchant_agent
./bin/credentials_provider_agent
./bin/merchant_payment_processor_agent
```

## Complete Shopping Flow

To experience the full end-to-end shopping flow with these Go backend agents, use the Python Shopping Agent.

### Option 1: Python Shopping Agent + Go Backends (Recommended)

This demonstrates **cross-language interoperability** - the strength of the AP2 protocol.

1. **Start the Go backend agents** (as shown above)

2. **Configure Python Shopping Agent** to use Go backends:

   Edit `samples/python/src/roles/shopping_agent/remote_agents.py`:
   ```python
   merchant_agent_client = PaymentRemoteA2aClient(
       name="merchant_agent",
       base_url="http://localhost:8001/a2a/merchant_agent",  # Go agent!
       required_extensions={EXTENSION_URI},
   )

   credentials_provider_client = PaymentRemoteA2aClient(
       name="credentials_provider",
       base_url="http://localhost:8002/a2a/credentials_provider_agent",  # Go agent!
       required_extensions={EXTENSION_URI},
   )
   ```

3. **Start the Python Shopping Agent:**

   ```sh
   # From repository root
   cd samples/python
   uv run --package ap2-samples adk web samples/python/src/roles
   ```

4. **Open browser** to `http://localhost:8000` and shop!

   You'll now have:
   - **Shopping Agent**: Python (with ADK web UI)
   - **Backend Agents**: Go (merchant, credentials, payment processor)

This setup demonstrates the protocol working across language boundaries.

### Option 2: Direct API Testing

Test the Go agents directly with HTTP requests:

**Get merchant agent info:**
```sh
curl -X POST http://localhost:8001/a2a/merchant_agent \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "agent.info",
    "params": {},
    "id": 1
  }'
```

**Search for products:**
```sh
curl -X POST http://localhost:8001/a2a/merchant_agent \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "agent.invoke",
    "params": {
      "skill": "search_catalog",
      "input": {
        "shopping_intent": "{\"product_type\": \"coffee maker\"}"
      }
    },
    "id": 2
  }'
```

**Get payment methods:**
```sh
curl -X POST http://localhost:8002/a2a/credentials_provider_agent \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "agent.invoke",
    "params": {
      "skill": "get_payment_method"
    },
    "id": 3
  }'
```

## Project Structure

```
samples/go/
├── cmd/                                  # Agent entry points
│   ├── merchant_agent/main.go
│   ├── credentials_provider_agent/main.go
│   └── merchant_payment_processor_agent/main.go
├── pkg/
│   ├── ap2/types/                       # AP2 protocol types
│   │   ├── mandate.go                   # Mandate structures
│   │   ├── payment_request.go
│   │   └── contact_address.go
│   ├── common/                          # Shared infrastructure
│   │   ├── base_executor.go            # Base agent execution
│   │   ├── message_builder.go          # A2A message construction
│   │   ├── server.go                   # HTTP/JSON-RPC server
│   │   └── function_resolver.go        # Tool/skill handling
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
    ├── README.md                        # This file
    └── run.sh                           # Start all agents
```

## Development

### Running Tests

```sh
cd samples/go
make test
```

### Code Formatting

```sh
make fmt
```

### Adding a New Backend Agent

1. Create entry point in `cmd/your_agent/main.go`
2. Implement executor in `pkg/roles/your_agent/executor.go`
3. Define `agent.json` with capabilities and skills
4. Add build target to `Makefile`
5. Update `run.sh` to start the new agent

## Why Go for Backend Agents?

Go is an excellent choice for building AP2 backend agents:

- **Type Safety**: Compile-time guarantees for protocol structures
- **Concurrency**: Efficient handling of multiple agent requests
- **Performance**: Fast startup, low memory footprint
- **Deployment**: Single binary, easy containerization
- **Maintainability**: Clean, readable code

## Comparison with Python Sample

| Feature | Python Sample | Go Sample |
|---------|--------------|-----------|
| **Shopping Agent** | ✅ Full ADK-powered agent with UI | ❌ Not included (use Python version) |
| **Backend Agents** | ✅ Python implementations | ✅ Go implementations |
| **Purpose** | Complete end-to-end demo | Production backend infrastructure |
| **Best For** | Learning full AP2 flow | Building production services |
| **Interoperability** | Can call any A2A backend | Works with any A2A shopping agent |

## Integration Scenarios

These Go backend agents support multiple integration patterns:

1. **Hybrid Stack**: Python Shopping Agent → Go Backends (demonstrated above)
2. **Full Go Stack**: Build your own Go Shopping Agent → Go Backends
3. **Polyglot**: Any language Shopping Agent → Go Backends
4. **Microservices**: Deploy each Go agent independently

## Stopping the Agents

If you used `run.sh`, press `Ctrl+C` to stop all agents.

If running manually, stop each process individually.

## Next Steps

- **Experience the full flow**: Use Python Shopping Agent with these Go backends
- **Explore the code**: See how AP2 protocol is implemented in Go
- **Build your own**: Use these as reference for your own AP2 agents
- **Deploy**: Containerize and deploy these production-ready services

## Resources

- [AP2 Protocol Documentation](../../../../README.md)
- [Python Sample (with Shopping Agent)](../../../../python/scenarios/a2a/human-present/cards/README.md)
- [Go Implementation Guide](../../README.md)

## License

Copyright 2025 Google LLC. Licensed under the Apache License, Version 2.0.
