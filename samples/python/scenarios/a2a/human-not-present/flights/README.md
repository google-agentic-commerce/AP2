# Agent Payments Protocol Sample: Human-Not-Present Flight Booking with Hallucination Check

This sample demonstrates a human-not-present transaction where an autonomous AI agent is prevented from making an incorrect purchase due to a "hallucination".

## Scenario

A user wants to book a flight to Paris for under 200 GBP. They interact with a shopping agent to create and digitally sign an `IntentMandate` that authorizes the agent to perform this task autonomously. The user then "steps away."

The shopping agent, simulating an AI hallucination, first attempts to book a flight to the wrong destination (Dublin). The remote merchant agent receives this request, validates it against the user's signed `IntentMandate`, detects the mismatch, and **blocks the transaction**.

The shopping agent then corrects itself and attempts to book the correct flight to Paris, which the merchant agent validates and approves.

This flow highlights a core security feature of AP2: ensuring an agent's actions strictly adhere to the user's cryptographically-signed intent, providing a safeguard against model errors or unpredictable behavior.

## Key Actors

* **Flight Shopping Agent:** A conversational ADK agent that interacts with the user, creates the `IntentMandate`, and attempts the purchases.
* **Flight Merchant Agent:** An A2A server-based agent that receives purchase requests and rigorously validates them against the signed `IntentMandate`.

## Executing the Example

### Setup

Ensure you have obtained a Google API key from [Google AI Studio](https://aistudio.google.com/apikey) and set it as an environment variable:
`export GOOGLE_API_KEY=your_key`

### Automated Execution

This will run the entire scenario automatically. From the root of the repository, run the following command:

```sh
bash samples/python/scenarios/a2a/human-not-present/flights/run.sh
```

### Interactive CLI Execution

This provides an interactive command-line interface to chat with the flight booking agent.

**1. Run the CLI:**

From the root of the repository, run the following command:

```sh
python samples/python/scenarios/a2a/human-not-present/flights/run_cli.py
```

**2. Interact with the Agent:**

You can then interact with the agent. For example, tell the agent your desired flight:

```
You: Book a flight to Paris for under 200 GBP
```

**3. The Human-Not-Present Simulation:**

This demo simulates a **human-not-present** scenario. After you approve the `IntentMandate`, the agent will proceed autonomously without any further input from you. This mimics a situation where the user has delegated a task and is no longer actively monitoring the agent.

**4. What to Expect in the Terminal:**

* **Mandate Approval:** The agent will generate a structured `IntentMandate` based on your request and display it in the terminal. You will be prompted to approve and "sign" it by typing 'y' and pressing Enter.
* **Autonomous Execution Begins:** Once you approve, the agent will inform you it is proceeding autonomously.
* **Simulated Hallucination:** This is the core of the demo. The agent is programmed to first **deliberately attempt to book a flight to the wrong destination (Dublin)**. You will see a message indicating this attempt.
* **Transaction Blocked:** The remote merchant agent will detect that the attempted booking for Dublin violates the signed mandate (which specified Paris). You will see a **FAILURE** message in the terminal explaining that the purchase was blocked due to a destination mismatch.
* **Correct Booking:** The agent will then proceed to book the correct flight to Paris. This attempt will match the mandate.
* **Success:** You will see a **SUCCESS** message indicating the purchase was approved by the merchant.
* **Ready for Next Command:** The agent will then notify you that it has completed the tasks and is ready for your next command.

**5. What to Expect in the Logs:**

As the demo runs, the background merchant agent's activity is recorded in `.logs/flight_merchant.log`. You can open this file to see the validation process from the merchant's perspective. You will see:

* The incoming purchase request for "Dublin".
* The validation logic detecting the mismatch against the mandate's "Paris" constraint.
* The incoming purchase request for "Paris".
* The successful validation and approval.

**6. Exit the CLI:**

To end the session, type `exit` or `quit`.
