# Go Sample: Human-Present Card Payment (A2A)

This scenario demonstrates a human-present card payment flow using Go agents.

**What's included:**

- Merchant Agent - product catalog and cart management
- Credentials Provider - payment credentials and wallet
- Payment Processor - payment processing and OTP challenges

**Note:** This sample focuses on agents in Go. Use the Python
Shopping Agent to interact with these agents.

## Agents Implemented

- **Merchant Agent** (`http://localhost:8001/a2a/merchant_agent`)
    - Handles product catalog queries
    - Creates and manages cart mandates
    - Exposes `search_catalog` skill for shopping intents
    - Supports AP2 and Sample Card Network extensions

- **Credentials Provider Agent**
  (`http://localhost:8002/a2a/credentials_provider`)
    - Manages user payment credentials and wallet
    - Provides payment method details
    - Supplies tokenized (DPAN) card information
    - Handles payment authorization

- **Merchant Payment Processor Agent**
  (`http://localhost:8003/a2a/merchant_payment_processor_agent`)
    - Processes payments on behalf of merchants
    - Implements OTP challenge mechanism
    - Handles payment authorization and settlement

## What This Sample Demonstrates

1. **AP2 Protocol Features**
    - Complete mandate lifecycle (Intent → Cart → Payment)
    - Card payment support with DPAN tokens
    - OTP challenge flows
    - Extension mechanism (AP2 + payment method extensions)

2. **Backend Service Patterns**
    - Modular, independently deployable services
    - Clean separation of concerns
    - Go's strengths for backend services (concurrency, type safety,
      performance)

3. **Language-Agnostic Protocol**
    - Go backend agents work seamlessly with Python Shopping Agent
    - Demonstrates true interoperability across languages
    - Shows protocol is implementation-independent

## Running the Sample

### Prerequisites

- Go 1.21 or higher
- Make
- Google API key from [Google AI Studio](https://aistudio.google.com/apikey)

### Quick Start

1. **Set up your API key:**

   ```sh
   export GOOGLE_API_KEY=your_key
   ```

   Or create a `.env` file in `samples/go/`:

   ```sh
   echo "GOOGLE_API_KEY=your_key" > samples/go/.env
   ```

2. **Run all `go` agents:**

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

To demonstrate the full end-to-end shopping workflow using the Go agents, we
can leverage the Python Shopping Agent.

### Python Shopping Agent + `go` Agents

This demonstrates **cross-language interoperability**.

1. **Start the Go backend agents** (see [Quick Start](#quick-start))

2. **Start the Python Shopping Agent in a separate terminal:**

   ```sh
   # From repository root
   uv run --package ap2-samples adk web samples/python/src/roles
   ```

   The Python Shopping Agent is pre-configured to connect with the Go backends
   in `samples/python/src/roles/shopping_agent/remote_agents.py`:

   ```python
   merchant_agent_client = PaymentRemoteA2aClient(
       name="merchant_agent",
       base_url="http://localhost:8001/a2a/merchant_agent",  # Go agent
       required_extensions={EXTENSION_URI},
   )

   credentials_provider_client = PaymentRemoteA2aClient(
       name="credentials_provider",
       base_url="http://localhost:8002/a2a/credentials_provider",  # Go agent
       required_extensions={EXTENSION_URI},
   )
   ```

3. **Open browser** to `http://localhost:8000` and shop!

   You'll now have:

   - **Shopping Agent**: Python (with ADK web UI)
   - **Backend Agents**: Go (merchant, credentials, payment processor)

   To try it out:
   - Select "Shopping Agent" from the top-left dropdown
   - Ask: "Hello, I'd like to buy a pair of red running shoes."
   - Follow the conversation to complete the purchase flow

### Direct API Testing

You can test the Go agents directly with HTTP requests:

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
curl -X POST http://localhost:8002/a2a/credentials_provider \
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

```text
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

## Stopping the Agents

If you used `run.sh`, press `Ctrl+C` to stop all agents.

If running manually, stop each process individually.

## Next Steps

- **Experience the full flow**: Use Python Shopping Agent with these Go backends
- **Explore the code**: See how AP2 protocol is implemented in Go
- **Build your own**: Use these as reference for your own AP2 agents

## Resources

- [AP2 Protocol Documentation](../../../../README.md)
- [Python Sample (with Shopping Agent)](../../../../python/scenarios/a2a/human-present/cards/README.md)
- [Go Implementation Guide](../../README.md)

## License

Copyright 2025 Google LLC. Licensed under the Apache License, Version 2.0.
