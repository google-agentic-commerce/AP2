# Agent Payments Protocol Sample: Human Not Present Purchases with x402

This sample demonstrates a **Human-Not-Present** transaction using payment
methods compatible with **x402**.

## Scenario

Human-Not-Present flows refer to all commerce flows where the user is **not
actively present** to confirm the details of what is being purchased at the
exact moment of the transaction. Instead, the user has pre-authorized the
transaction details and payment method (e.g., by setting up a specific intent or
agreeing to a purchase condition like a price drop).

In this scenario, the flow is triggered by a mock "price drop" or "item drop"
event from the merchant. Once the price drops to a level acceptable to the agent
(based on user intent), the Shopping Agent autonomously completes the purchase
using the pre-authorized credentials and mandates, without asking the user for
real-time confirmation.

## Key Actors

This sample consists of:

- **Shopping Agent (v2):** The main orchestrator that handles the user's
  shopping requests and acts autonomously when a trigger condition is met.
- **Merchant Agent (MCP):** An agent that handles product queries and
  advertises support for x402 purchases.
- **x402 Merchant Payment Processor Agent (MCP):** An agent that takes
  payments on behalf of the merchant.
- **x402 Credentials Provider Agent (MCP):** The holder of the user's payment
  credentials, facilitating payment between the shopping agent and the
  merchant's payment processor.

## Key Features

**1. Autonomous Purchase on Trigger**

- The flow is initiated by an external trigger (a mock price drop or item drop)
  rather than a direct user command at the moment of purchase.
- The agent evaluates the condition and proceeds with the purchase if it matches
  the user's intent.

**2. x402 Purchase Integration**

- The Merchant Agent advertises support for x402 purchases through its agent
  card and CartMandate.
- The flow uses x402 compatible payment methods and typically skips manual steps
  like OTP challenges, making it suitable for autonomous agent interactions.

## Executing the Example

### Setup

Ensure you have obtained a Google API key from
[Google AI Studio](https://aistudio.google.com/apikey). Then declare the
GOOGLE_API_KEY variable in one of two ways:

- **Option 1:** Declare it as an environment variable:
  `export GOOGLE_API_KEY=your_key`
- **Option 2:** Put it into an `.env` file at the root of your repository:
  `echo "GOOGLE_API_KEY=your_key" > .env`

### Execution

You can execute the following command to run all services (Merchant Trigger,
x402 PSP Trigger, Shopping Agent, and Web Client) in one terminal:

```sh
bash code/samples/python/scenarios/a2a/human-not-present/x402/run.sh
```

To enable blockchain broadcast simulation (if supported by the scenario), you
can pass the flag:

```sh
bash code/samples/python/scenarios/a2a/human-not-present/x402/run.sh \
  --enable_broadcast_on_chain
```

This script will start the services on the following ports:

- Agent: `8080`
- Merchant Trigger: `8081`
- x402 PSP Trigger: `8084`
- Web Client: `5173`

The script will automatically open the web client in your browser. If not, you
can open `http://localhost:5173` manually.

### Triggering the Flow

To simulate the trigger condition (e.g., a price drop), open a separate terminal
and run the following command (replace `<item_id>` and `<price>` with
appropriate test values):

```sh
curl -X POST \
  "http://localhost:8081/trigger-price-drop?item_id=<item_id>&price=<price>&stock=10"
```

Observe the web client to see the autonomous purchase in action.
