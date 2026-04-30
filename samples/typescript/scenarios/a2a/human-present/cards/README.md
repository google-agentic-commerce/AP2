# TypeScript Sample: Human-Present Card Payment (A2A)

This scenario demonstrates the A2A `ap2-extension` for a human-present
transaction using a card as the payment method, implemented entirely in
TypeScript.

## Scenario

Human-Present flows refer to all commerce flows where the user is present to
confirm the details of what is being purchased and what payment method is to be
used. The user attesting to the details of the purchase allows all parties to
have high confidence of the transaction.

The IntentMandate is leveraged to share the appropriate information with
Merchant Agents. All Human-Present purchases will have a user-signed
PaymentMandate authorizing the purchase.

## Agents Implemented

All four roles are implemented in TypeScript:

- **Shopping Agent** (`http://localhost:8001`)
    - Root orchestrator running on the ADK web UI.
    - Coordinates `shopper`, `shipping_collector`, and `payment_collector`
      sub_agents.
- **Merchant Agent** (`http://localhost:8004/a2a/merchant_agent`)
    - Handles product catalog queries and creates signed CartMandates.
- **Credentials Provider** (`http://localhost:8002/a2a/credentials_provider`)
    - Manages payment credentials and provides DPAN tokens.
- **Merchant Payment Processor** (`http://localhost:8003/a2a/merchant_payment_processor_agent`)
    - Authorizes payments and runs the OTP challenge.

## What This Sample Demonstrates

1. **AP2 Protocol Features**
    - Complete mandate lifecycle (Intent → Cart → Payment → Receipt)
    - Card payment with DPAN tokens
    - OTP challenge during payment authorization
    - W3C Verifiable Credential signing of mandates
2. **TypeScript Patterns**
    - Zod schemas mirroring the AP2 types
    - ADK `LlmAgent` orchestration with `FunctionTool`s
    - A2A request/response handling via `@a2a-js/sdk`

## Setup

### Prerequisites

- Node.js 18+
- npm

### Configure credentials

Obtain a Google API key from
[Google AI Studio](https://aistudio.google.com/apikey), then create a `.env`
file in `samples/typescript/`:

```sh
cp samples/typescript/.env.example samples/typescript/.env
# Edit samples/typescript/.env and fill in GOOGLE_API_KEY
```

Alternatively, configure Vertex AI by setting `GOOGLE_GENAI_USE_VERTEXAI=true`
along with `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION`.

### Install dependencies

```sh
cd samples/typescript
npm install
```

## Execution

### Option 1: Run everything with one command

```sh
bash samples/typescript/scenarios/a2a/human-present/cards/run.sh
```

This starts the three backend agents and the Shopping Agent web UI.

### Option 2: Run each agent in its own terminal

```sh
# Terminal 1: Merchant Agent (port 8004)
npx tsx src/roles/merchant/server.ts

# Terminal 2: Credentials Provider (port 8002)
npx tsx src/roles/credentials-provider/server.ts

# Terminal 3: Payment Processor (port 8003)
npx tsx src/roles/payment-processor/server.ts

# Terminal 4: Shopping Agent A2A server (port 8001)
npx tsx src/roles/shopping/server.ts

# Terminal 5: ADK web UI (port 3001)
npx adk web src/roles/shopping --host localhost -p 3001
```

Then open the ADK web UI at <http://localhost:3001> and select the
`shopping_agent`.

## Interacting with the Shopping Agent

1. **Initial request**: Type something like _"I want to buy running shoes."_
2. **Product search**: The Shopping Agent delegates to the Merchant Agent,
   which returns CartMandate options.
3. **Product selection**: Choose one of the offered carts.
4. **Shipping address**: The `shipping_collector` sub_agent prompts for an
   address; the cart is then re-signed by the merchant.
5. **Payment method**: The `payment_collector` sub_agent fetches available
   payment methods from the Credentials Provider.
6. **OTP challenge**: The Payment Processor issues an OTP challenge that you
   complete in the chat.
7. **Receipt**: A signed `PaymentReceipt` is returned and displayed.

## Smoke Tests

After the agents are running, you can run end-to-end smoke tests:

```sh
npm run test:e2e
```
