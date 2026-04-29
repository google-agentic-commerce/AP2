# Code

All source code for AP2 lives here, split by artifact.

## `sdk/` — the AP2 SDK

The primary artifact of this repository. The Python implementation is at
[`sdk/python/ap2/`](sdk/python/ap2/) and is the package exposed by the root
[`pyproject.toml`](../pyproject.toml) (installed as `import ap2`).

It contains:

- `sdk/python/ap2/models/` — Pydantic models for carts, mandates, receipts,
  and payment requests.
- `sdk/python/ap2/schemas/` — canonical JSON Schemas and the generator used
  to emit the Python models in `sdk/python/ap2/sdk/generated/`.
- `sdk/python/ap2/sdk/` — the runtime SDK: mandate wrappers, chain
  verification, SD-JWT helpers, constraints, disclosure metadata.
- `sdk/python/ap2/tests/` — unit tests for the SDK.

Future language SDKs (Go, JS, …) would live as siblings under `sdk/`.

## `samples/` — reference implementations

End-to-end scenarios that demonstrate the protocol:

- [`samples/python/`](samples/python/) — Python roles (merchant, credentials
  provider, shopping agent, payment processor) and scenarios.
- [`samples/go/`](samples/go/) — Go reference servers and scenarios.
- [`samples/android/`](samples/android/) — Android shopping assistant and the
  digital payment credentials scenario.
- [`samples/certs/`](samples/certs/) — test CA and leaf certificates used by
  the samples for SD-JWT trust verification.

## `web-client/` — demo UI

A Vite + React + TypeScript app that exercises the A2A protocol against the
sample agents.
