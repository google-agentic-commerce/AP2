# Go Samples for the Agent Payments Protocol AP2

This directory contains Go samples demonstrating how to build AP2 backend
agents.

## Overview

These samples showcase Go implementations of AP2-compliant backend agents:

- **Merchant Agent** - Product catalog and cart management
- **Credentials Provider Agent** - Payment credentials and wallet management
- **Merchant Payment Processor Agent** - Payment processing and authorization

**Note**: These samples focus on backend agents. For a Shopping Agent, use the
[Python implementation](../python) which seamlessly interoperates with these
Go backends, demonstrating the protocol's language-agnostic design.

## Getting Started

- **Explore Scenarios**: To understand what these samples can do, see the
  [scenarios](./scenarios) directory for detailed examples.
- **Review the Code**: Dive into the implementation by reviewing the code in
  the [pkg](./pkg) and [cmd](./cmd) directories.
- **All Samples**: Return to the main [samples](..) directory to see examples
  in other languages.

### Prerequisites

- Go 1.21 or higher
- Make
- Google API key from [Google AI Studio](https://aistudio.google.com/apikey)

### Quick Start

```sh
# Set API key
export GOOGLE_API_KEY=your_key

# Install dependencies
go mod download

# Build agents
make build

# Run scenario (see scenarios directory for specific instructions)
bash scenarios/a2a/human-present/cards/run.sh
```

(Note: Each scenario has a run.sh script that handles setup automatically.)

## Why Go for Backend Agents?

Go is exceptionally well-suited for building AP2 backend services:

- **Type Safety**: Compile-time validation of protocol structures
- **Performance**: Fast response times and low resource usage
- **Concurrency**: Efficient handling of concurrent requests
- **Deployment**: Single binary with no runtime dependencies

## Project Structure

```text
samples/go/
├── cmd/                 # Agent entry points
├── pkg/
│   ├── ap2/types/      # AP2 protocol types
│   ├── common/         # Shared infrastructure
│   └── roles/          # Agent implementations
└── scenarios/          # Runnable examples
```

## Development

```sh
# Run tests
make test

# Format code
make fmt

# Build all agents
make build
```

See individual [scenarios](./scenarios) for detailed documentation.
