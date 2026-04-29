# Python Samples for the Agent Payments Protocol (AP2)

Python reference implementations of the AP2 roles (merchant, credentials
provider, payment processor, shopping agent) and end-to-end scenarios that
tie them together.

All paths below are relative to the repository root.

## Layout

- [`scenarios/`](./scenarios) — runnable end-to-end flows. Each scenario has a
  `run.sh` (or `run_*.sh`) that brings up every agent/server it needs.
- [`src/roles/`](./src/roles) — the individual role implementations used by
  those scenarios.
- [`src/common/`](./src/common) — shared utilities (A2A client, message
  builders, server bootstrap, etc.).

For samples in other languages, see [`../go/`](../go) and
[`../android/`](../android). Test certificates used across the samples live
in [`../certs/`](../certs).

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- A Google API key from [Google AI Studio](https://aistudio.google.com/apikey),
  or Vertex AI ADC (`GOOGLE_GENAI_USE_VERTEXAI=true`).

## Configuration

Create a `.env` file at the repository root with at least your API key:

```
GOOGLE_API_KEY=<your_api_key>
```

Some scenarios (e.g. `shopping_agent_v2`) read additional variables from a
local `.env` inside their role directory — see the scenario's own README
when applicable. For example:

```
GOOGLE_API_KEY=<your_api_key>
AGENT_MODEL=gemini-3.1-flash-lite-preview
```

## Running a scenario

Pick a scenario and run its script from the repository root. Each script
creates/updates the `uv` virtual environment and starts every agent it
needs.

Human-present (interactive, browser-based shopping agent):

```bash
./code/samples/python/scenarios/a2a/human-present/cards/run.sh
./code/samples/python/scenarios/a2a/human-present/cards/run.sh --payment-method x402
```

Human-not-present (automated / recurring flows):

```bash
./code/samples/python/scenarios/a2a/human-not-present/cards/run.sh
./code/samples/python/scenarios/a2a/human-not-present/x402/run.sh
```

See the README inside each scenario directory for a walkthrough of the
flow and the expected interactions.
