# Agent Payments Protocol Go Sample: Backend Agent Infrastructure

This sample demonstrates Go implementations of backend agents for the AP2 protocol in a human present transaction using a card as the payment method.

## Scenario

This Go sample provides backend agent infrastructure without a shopping agent frontend. It demonstrates how to implement AP2-compliant agents in Go, showcasing the protocol's server-side components.

Unlike the Python samples which include a complete end-to-end flow with a Shopping Agent UI, this sample focuses on the backend agents that would typically be operated by merchants, payment processors, and credential providers.

## Key Actors

This sample implements three backend agents:

*   **Merchant Agent:** Handles product catalog queries and creates cart mandates. Exposes a `search_catalog` skill that accepts shopping intents and returns product results.
*   **Merchant Payment Processor Agent:** Processes payments on behalf of the merchant. Implements OTP challenges for additional security verification.
*   **Credentials Provider Agent:** Manages user payment credentials and wallet information. Provides payment method details including tokenized (DPAN) cards.

**Note:** This sample does NOT include a Shopping Agent. To see a complete shopping flow, refer to the [Python human-present cards sample](../../../../python/scenarios/a2a/human-present/cards/README.md) which includes all actors including the Shopping Agent with a web UI.

## Key Features

**1. A2A Protocol Implementation in Go**

*   Full implementation of the A2A JSON-RPC protocol in Go
*   Support for AP2 extensions and payment method extensions
*   Structured mandate handling (IntentMandate, CartMandate, PaymentMandate)

**2. Card Purchase Support with DPAN**

*   The merchant agent advertises support for card purchases through its agent card
*   The credentials provider supplies tokenized (DPAN) card information

**3. OTP Challenge Flow**

*   The merchant payment processor agent implements an OTP challenge mechanism
*   Demonstrates secure payment authorization patterns

## Executing the Example

### Prerequisites

*   Go 1.21 or higher
*   Make

### Setup

Ensure you have obtained a Google API key from [Google AI Studio](https://aistudio.google.com/apikey). Then declare the GOOGLE_API_KEY variable in one of two ways:

*   Option 1: Declare it as an environment variable:
    ```sh
    export GOOGLE_API_KEY=your_key
    ```

*   Option 2: Put it into an .env file in the `samples/go` directory:
    ```sh
    echo "GOOGLE_API_KEY=your_key" > samples/go/.env
    ```

### Running the Agents

From the repository root, you can run all agents with a single command:

```sh
bash samples/go/scenarios/a2a/human-present/cards/run.sh
```

This script will:
1. Install Go dependencies
2. Build all agent binaries
3. Start all three agents in the background
4. Display the running agent endpoints

The agents will be available at:
*   **Merchant Agent:** http://localhost:8001/a2a/merchant_agent
*   **Credentials Provider Agent:** http://localhost:8002/a2a/credentials_provider_agent
*   **Merchant Payment Processor Agent:** http://localhost:8003/a2a/merchant_payment_processor_agent

To stop all agents, press `Ctrl+C`.

### Building Manually

Alternatively, you can build and run agents manually from the `samples/go` directory:

```sh
cd samples/go

# Install dependencies
go mod download

# Build all agents
make build

# Run individual agents
./bin/merchant_agent
./bin/credentials_provider_agent
./bin/merchant_payment_processor_agent
```

## Interacting with the Agents

Since this sample does not include a Shopping Agent or UI, you can interact with the agents directly via HTTP requests or by integrating them with your own shopping agent implementation.

### Testing with cURL

You can test the agents using cURL or any HTTP client. Here are example requests:

**1. Query the Merchant Agent's capabilities:**

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

**2. Search the catalog:**

```sh
curl -X POST http://localhost:8001/a2a/merchant_agent \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "agent.invoke",
    "params": {
      "skill": "search_catalog",
      "input": {
        "shopping_intent": "{\"product_type\": \"coffee maker\", \"quantity\": 1}"
      }
    },
    "id": 2
  }'
```

**3. Get payment methods from the Credentials Provider:**

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

### Integration with Shopping Agents

These backend agents are designed to be called by a Shopping Agent (like those in the Python samples). The typical flow would be:

1. Shopping Agent receives user intent
2. Shopping Agent calls Merchant Agent's `search_catalog` skill
3. Merchant Agent returns CartMandate(s)
4. Shopping Agent queries Credentials Provider for payment methods
5. User selects payment method and confirms purchase
6. Shopping Agent sends PaymentMandate to Merchant Payment Processor
7. Payment Processor may challenge with OTP
8. Payment is completed and receipt is issued

For a complete working example of this flow, see the [Python human-present cards sample](../../../../python/scenarios/a2a/human-present/cards/README.md).

## What This Sample Demonstrates

This Go implementation showcases:

1. **Language Portability:** The AP2 protocol can be implemented in any language, not just Python. This demonstrates Go as a viable option for building AP2 agents.

2. **Backend Agent Architecture:** Focuses on the server-side infrastructure that merchants, payment processors, and credential providers would deploy.

3. **A2A Protocol Compliance:** Full implementation of:
   - JSON-RPC 2.0 transport
   - Agent discovery and capabilities
   - Skill invocation patterns
   - AP2 extensions and mandate handling

4. **Modularity:** Each agent is a standalone service that can be deployed independently, demonstrating the distributed nature of the AP2 ecosystem.

5. **Production Patterns:** Uses Go's strengths for building robust backend services:
   - Type-safe mandate and message structures
   - Concurrent request handling
   - Clean separation of concerns

## Development

### Project Structure

```
samples/go/
├── cmd/                          # Agent entry points
│   ├── merchant_agent/
│   ├── credentials_provider_agent/
│   └── merchant_payment_processor_agent/
├── pkg/
│   ├── ap2/                      # AP2 protocol types
│   │   └── types/
│   ├── common/                   # Shared utilities
│   │   ├── base_executor.go     # Base agent execution
│   │   ├── message_builder.go   # A2A message construction
│   │   └── server.go            # HTTP/JSON-RPC server
│   └── roles/                   # Agent implementations
│       ├── merchant_agent/
│       ├── credentials_provider_agent/
│       └── merchant_payment_processor_agent/
└── scenarios/
    └── a2a/human-present/cards/
        └── run.sh               # Convenience script
```

### Running Tests

```sh
cd samples/go
make test
```

### Code Formatting

```sh
cd samples/go
make fmt
```

## Differences from Python Sample

| Feature | Python Sample | Go Sample |
|---------|--------------|-----------|
| Shopping Agent | ✅ Included with web UI | ❌ Not included |
| Backend Agents | ✅ Included | ✅ Included |
| End-to-End Flow | ✅ Complete user journey | ❌ Backend only |
| Primary Purpose | Demonstrate complete flow | Demonstrate backend implementation |
| Interaction Method | Web browser UI | HTTP/JSON-RPC API calls |

## Next Steps

To see these agents in action with a complete shopping flow:

1. Run the [Python human-present cards sample](../../../../python/scenarios/a2a/human-present/cards/README.md)
2. Configure the Python Shopping Agent to call these Go backend agents instead of the Python ones
3. Experience the full end-to-end flow with Go-powered backend services

## License

Copyright 2025 Google LLC. Licensed under the Apache License, Version 2.0.
