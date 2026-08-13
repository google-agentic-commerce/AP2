# Agent Payments Protocol Sample (TS): Human-Not-Present with a Card

This sample is a TypeScript port of the v0.2 Python HNP cards scenario.

## Scenario

In a **Human-Not-Present (HNP)** flow the user is not actively present at the
moment of purchase. The user signs an open mandate up front; the agent then
monitors for a triggering condition (price drop, item drop, etc.) and
autonomously completes the purchase when the constraint is satisfied.

This sample fires a mock price-drop event via HTTP to the merchant trigger
server. The `shopping_agent_v2` polls `check_product`, evaluates the open
mandate constraints, and — when satisfied — runs the closed-mandate / checkout
/ payment / receipt pipeline against three MCP servers without further user
input.

## Key actors

- **Shopping Agent v2** (`src/roles/shopping-agent-v2/`) — orchestrator (LLM).
  Owns three stdio MCP clients pointed at the role MCP servers below.
- **Merchant MCP** (`src/roles/merchant-agent-mcp/server.ts`) — exposes
  `search_inventory`, `check_product`, `assemble_cart`, `create_checkout`,
  `complete_checkout` over stdio.
- **Credentials Provider MCP** (`src/roles/credentials-provider-mcp/server.ts`)
  — exposes `issue_payment_credential`, `revoke_payment_credential`,
  `verify_payment_receipt`.
- **Merchant Payment Processor MCP**
  (`src/roles/merchant-payment-processor-mcp/server.ts`) — exposes
  `initiate_payment`.
- **Trigger HTTP servers** (one per MCP role) — fire external events such as
  `POST /trigger-price-drop` to drive the autonomous loop.

## Status

This is a **minimum-viable port** of the v0.2 Python `*_mcp` roles. The MCP
tool *contracts* (names, args, response shapes) are 1:1 with Python, but the
cryptographic primitives (SD-JWT mandate chain verification, ES256 signing,
disclosure-metadata canonicalization, real receipt verification) are
**stubbed**. The flow runs end-to-end and is wire-compatible with the v0.2
web-client, but it is not a production-grade implementation of AP2 v0.2.

## Setup

You need a Google API key from [Google AI Studio](https://aistudio.google.com/apikey).
Put it in a `.env` at the repository root:

```sh
echo "GOOGLE_API_KEY=your_key" > .env
```

## Execution

```sh
bash code/samples/typescript/scenarios/a2a/human-not-present/cards/run.sh
```

Ports:

- Shopping Agent v2 — `http://localhost:8080`
- Merchant trigger — `http://localhost:8081`
- Credentials Provider trigger — `http://localhost:8082`
- Payment Processor trigger — `http://localhost:8083`
- Web client — `http://localhost:5173` (only if `/tmp/ap2-v02/code/web-client`
  exists; otherwise skipped — set `WEB_CLIENT_DIR` to override)

## Driving the flow from the CLI

1. Start the stack:

   ```sh
   bash code/samples/typescript/scenarios/a2a/human-not-present/cards/run.sh
   ```

2. Send the initial intent to the shopping agent over A2A (the agent runs
   `search_inventory` and signs the open mandate):

   ```sh
   curl -X POST http://localhost:8080/a2a/shopping_agent \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": "1",
       "method": "message/send",
       "params": {
         "configuration": {"acceptedOutputModes": [], "blocking": true},
         "message": {
           "kind": "message",
           "messageId": "msg-1",
           "role": "user",
           "parts": [{"kind": "text", "text": "When does the SuperShoe drop? Size 9 women's, max $200."}]
         }
       }
     }'
   ```

3. Inspect the chosen `item_id` (printed in the response or in
   `.logs/shopping-agent-v2.log`).

4. Fire the price-drop trigger:

   ```sh
   curl -X POST "http://localhost:8081/trigger-price-drop?item_id=supershoe_size_9_0&price=150&stock=10"
   ```

5. Nudge the agent to re-check (or wait for the next poll):

   ```sh
   curl -X POST http://localhost:8080/a2a/shopping_agent \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":"2","method":"message/send","params":{"configuration":{"acceptedOutputModes":[],"blocking":true},"message":{"kind":"message","messageId":"msg-2","role":"user","parts":[{"kind":"text","text":"Check the price now."}]}}}'
   ```

   The agent should now see the drop, run the closed-mandate + checkout +
   payment pipeline, and surface a receipt.
