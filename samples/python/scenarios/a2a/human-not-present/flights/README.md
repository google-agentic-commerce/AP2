# Agent Payments Protocol Sample: Human-Not-Present Flight Booking with Hallucination Check

This sample demonstrates a human-not-present transaction where an autonomous AI agent is prevented from making an incorrect purchase due to a “hallucination”.

## Scenario

A user wants to book a flight to Paris for under 200 GBP. They interact with a shopping agent to create and digitally sign an `IntentMandate` that authorizes the agent to perform this task autonomously. The user then “steps away.”

The shopping agent, simulating an AI hallucination, first attempts to book a flight to the wrong destination (Dublin). The remote merchant agent receives this request, validates it against the user’s signed `IntentMandate`, detects the mismatch, and **blocks the transaction**.

The shopping agent then corrects itself and attempts to book the correct flight to Paris, which the merchant agent validates and approves.

This flow highlights a core security feature of AP2: ensuring an agent’s actions strictly adhere to the user’s cryptographically-signed intent, providing a safeguard against model errors or unpredictable behavior.

## Key Actors

* **Flight Shopping Agent:** A conversational ADK agent that interacts with the user, creates the `IntentMandate`, and attempts purchases.
* **Flight Merchant Agent:** An A2A server-based agent that receives purchase requests and rigorously validates them against the signed `IntentMandate`.

> **Agent lifecycle:** The merchant agent is started and stopped **by `run_cli.py`**. Do not start it separately.

## Requirements

1. A Google API key from [Google AI Studio](https://aistudio.google.com/apikey).
2. Unix-like shell (macOS/Linux or WSL) for the helper script.

Export your key:

```sh
export GOOGLE_API_KEY=your_key
```

## How to Run

### Option 1 — Automated (recommended)

Runs setup and then launches the CLI, letting the CLI manage the merchant agent lifecycle.

From the **repo root**:

```sh
bash samples/python/scenarios/a2a/human-not-present/flights/run.sh
```

### Option 2 — Interactive (direct CLI)

Run the CLI directly (if your environment is already set up):

```sh
python samples/python/scenarios/a2a/human-not-present/flights/run_cli.py
```

`run_cli.py` will:

* start the **Flight Merchant Agent** in the background,
* log its output to `.logs/flight_merchant.log`,
* run the shopping agent conversation,
* shut the merchant agent down on exit.

## What You’ll See

1. **Mandate Approval**
   The agent generates a structured `IntentMandate` based on your request and shows it in the terminal. You’ll be prompted to approve and “sign” it by typing `y`.

2. **Autonomous Execution Begins**
   After approval, the agent announces it will proceed autonomously (human-not-present).

3. **Simulated Hallucination**
   The agent deliberately attempts to book a flight to **Dublin** first. This should be **blocked**.

4. **Block & Explanation**
   The merchant agent validates the request against the mandate (which specifies **Paris**) and returns a clear **FAILURE** message due to destination mismatch.

5. **Correct Attempt**
   The agent then retries with **Paris** under the price cap. This is **approved**.

6. **Completion**
   You’ll see a **SUCCESS** message and the agent will be ready for your next command.

## Logs

`run_cli.py` writes the merchant agent’s logs to:

```
.logs/flight_merchant.log
```

Open this file to see:

* the incoming Dublin request and the mismatch detection,
* the subsequent Paris request and successful validation.

## Exiting

Type `exit` or `quit` in the CLI to end the session. The CLI will stop the merchant agent automatically.

## Troubleshooting

* **API key not set:** Ensure `GOOGLE_API_KEY` is exported in your shell.
* **Port already in use:** If you previously launched a merchant agent manually, stop it before running this demo, since the CLI will start its own instance.
