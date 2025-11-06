# Go Samples for the Agent Payments Protocol AP2

This directory contains Go samples demonstrating how to build AP2
agents.

## Available Scenarios

Currently, one scenario is available:

- **[Human-Present Card Payment](./scenarios/a2a/human-present/cards/README.md)**
    - Complete card payment flow with Go agents and Python Shopping
      Agent

See the [scenario README](./scenarios/a2a/human-present/cards/README.md) for
detailed setup and usage instructions.

## Why Go for Backend Agents?

Go can be exceptionally well-suited for building AP2 backend services:

- **Type Safety**: Compile-time validation of protocol structures
- **Performance**: Fast response times and low resource usage
- **Concurrency**: Efficient handling of concurrent requests
- **Deployment**: Single binary with no runtime dependencies

## Project Structure

```text
samples/go/
├── cmd/                               # Agent entry points
├── pkg/
│   ├── ap2/types/                    # AP2 protocol types
│   ├── common/                       # Shared infrastructure
│   └── roles/                        # Agent implementations
└── scenarios/                        # Runnable examples
    └── a2a/
        └── human-present/
            └── cards/                # Card payment scenario
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

## License

Copyright 2025 Google LLC. Licensed under the Apache License, Version 2.0.
