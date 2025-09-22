# Agent Payments Protocol Sample: Human-Not-Present Flight Booking with Hallucination Check

This sample demonstrates a human-not-present transaction where an autonomous AI agent is prevented from making an incorrect purchase due to a "hallucination".

## Scenario

A user wants to book a flight to Paris for under 200 GBP. They interact with a shopping agent to create and digitally sign an `IntentMandate` that authorizes the agent to perform this task autonomously. The user then "steps away."

The shopping agent, simulating an AI hallucination, first attempts to book a flight to the wrong destination (Dublin). The remote merchant agent receives this request, validates it against the user's signed `IntentMandate`, detects the mismatch, and **blocks the transaction**.

The shopping agent then corrects itself and attempts to book the correct flight to Paris, which the merchant agent validates and approves.

This flow highlights a core security feature of AP2: ensuring an agent's actions strictly adhere to the user's cryptographically-signed intent, providing a safeguard against model errors or unpredictable behavior.

## Key Actors

*   **Flight Shopping Agent:** A conversational ADK agent that interacts with the user, creates the `IntentMandate`, and attempts the purchases.
*   **Flight Merchant Agent:** An A2A server-based agent that receives purchase requests and rigorously validates them against the signed `IntentMandate`.

## Executing the Example

### Setup

Ensure you have obtained a Google API key from [Google AI Studio](https://aistudio.google.com/apikey) and set it as an environment variable:
`export GOOGLE_API_KEY=your_key`

### Execution

From the root of the repository, run the following command:

```sh
bash samples/python/scenarios/a2a/human-not-present/flights/run.sh
