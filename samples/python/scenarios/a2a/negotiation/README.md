# AP2-Haggle Sample: Real-time Negotiation Between Buyer and Seller Agents

This sample demonstrates the [AP2-Haggle extension](../../../../../docs/haggle-extension.md) —
a multi-round, multi-axis bargain between a Claude-powered shopping agent and
a Claude-powered merchant agent. The two sides exchange unsigned `Offer`s
until they converge on an acceptable deal, at which point the merchant seals
the agreement into a standard AP2 `CartMandate` and the flow hands off to the
baseline AP2 payment path (credentials provider → payment processor →
receipt) unchanged.

## What this sample shows

* **Extensible terms.** The negotiation is not price-only. The shopper can
  state hard `required_terms` (e.g. `{"refundable": true}`), ideal
  `target_terms` (price + warranty + delivery window), and a walk-away
  ceiling. Claude on both sides can introduce any additional dimension —
  bundle composition, contract duration, loyalty-tier discounts, extended
  payment-net terms — without any protocol change.
* **Structured persuasion.** Each Offer carries a list of `Argument`s with
  a `type` tag and structured payload (competitor quotes, cost floors,
  bulk thresholds, loyalty history). The counter-party's negotiator LLM
  evaluates these concretely, not rhetorically.
* **Unsigned offers, signed cart.** Only the terminal accepted Offer
  becomes a merchant-authorized `CartMandate`. Intermediate rounds carry
  plain `CartContents` with no merchant JWT.
* **A2A extension via new URI + DataPart keys.** Wire format: new
  extension URI `https://github.com/ap2haggle/ap2/extensions/haggle/v0.1`
  and new keys `ap2.haggle.NegotiationConstraints`, `ap2.haggle.Offer`,
  `ap2.haggle.NegotiationOutcome`, layered on top of the existing AP2 A2A
  extension.

## Key actors

Identical to the baseline AP2 samples — negotiation only adds logic inside
the shopper and the merchant:

* **Shopping Agent** (port 8000 web UI). ADK + Gemini orchestrator. Gains a
  new `negotiate_purchase` tool that drives the multi-round loop and a new
  `negotiator` sub-agent that runs on Claude.
* **Merchant Agent** (port 8001). Gains a new `negotiate_workflow` executor
  tool and a new `seller_strategist` sub-agent that runs on Claude. Reads
  optional inventory config from `$HAGGLE_MERCHANT_CONFIG`.
* **Credentials Provider Agent** (port 8002). Unchanged.
* **Merchant Payment Processor Agent** (port 8003). Unchanged.

## Setup

You need two API keys:

* `GOOGLE_API_KEY` — used by the ADK orchestrator (Gemini, same as baseline
  AP2 samples). Get one from
  [Google AI Studio](https://aistudio.google.com/apikey).
* `ANTHROPIC_API_KEY` — used by both negotiator sub-agents (Claude). Get one
  from [console.anthropic.com](https://console.anthropic.com/).

Declare both in `.env` at the repo root:

```sh
echo "GOOGLE_API_KEY=your_gemini_key" >> .env
echo "ANTHROPIC_API_KEY=your_claude_key" >> .env
```

Optional overrides:

* `HAGGLE_CLAUDE_MODEL` — Anthropic model id, default `claude-sonnet-4-6`.
* `HAGGLE_MERCHANT_CONFIG` — path to a JSON inventory config. The sample's
  `run.sh` points this at [`config/inventory.json`](config/inventory.json).

## Execute

From the repo root:

```sh
bash samples/python/scenarios/a2a/negotiation/run.sh
```

This boots all four services and serves the ADK dev UI at
<http://0.0.0.0:8000>. Select `shopping_agent` from the agent dropdown.

Or run each agent in its own terminal:

```sh
# Terminal 1 (merchant, with haggle inventory config)
HAGGLE_MERCHANT_CONFIG=$(pwd)/samples/python/scenarios/a2a/negotiation/config/inventory.json \
  uv run --package ap2-samples python -m roles.merchant_agent

# Terminal 2
uv run --package ap2-samples python -m roles.credentials_provider_agent

# Terminal 3
uv run --package ap2-samples python -m roles.merchant_payment_processor_agent

# Terminal 4 (shopping UI)
uv run --package ap2-samples adk web samples/python/src/roles
```

## Try the interaction

A prompt that will trigger the negotiation path:

> I want to buy a developer laptop. My target is $900 including shipping, my
> absolute ceiling is $1050. I need at least a 24-month warranty and
> delivery within a week. Refundable only. RivalStore is listing the same
> model for $1150 — use that as leverage. Let's negotiate, cooperatively.

What happens:

1. The root agent delegates to `shopper` to build an `IntentMandate`
   ("a developer laptop, refundable"). No price is stored inside the
   IntentMandate — budget lives in the negotiation constraints instead.
2. The root agent calls the `negotiate_purchase` tool with
   `target_price=900`, `max_price=1050`, `preferred_warranty_months=24`,
   `preferred_delivery_days=7`, `required_terms_json='{"refundable": true}'`,
   `style="cooperative"`, `strategy_hint` echoing the RivalStore lever.
3. The tool opens the negotiation by sending the IntentMandate plus a
   `NegotiationConstraints` DataPart to the merchant.
4. The merchant's `seller_strategist` (Claude) emits an opening Offer
   around $1050–$1100 with quality + cost-floor arguments.
5. The shopper's `negotiator` (Claude) evaluates and counters at ~$890
   with competitor comparison + returning-customer arguments.
6. 2–3 more rounds converge on a deal inside `walk_away_terms`, the
   merchant seals a signed `CartMandate` and returns a
   `NegotiationOutcome(status="accepted")`.
7. Control returns to the root agent, which continues with the standard
   AP2 path — shipping address, payment method, signed payment mandate,
   issuer authorization, receipt. None of that code changed.

### Try the failure paths

* **Walk-away**: set `max_price` below the merchant's cost floor (for the
  seeded laptop item: $820). Claude on the merchant side will hit its
  floor and the shopper will abandon.
* **Rounds exhausted**: ask for `max_rounds=1` and an aggressive target.
  Expect `status="rejected"` after a single exchange that fails to
  converge.
* **Required-term violation**: ask for `{"refundable": true, "currency": "EUR"}`
  and watch the merchant either accommodate or walk.

## Wire-level verification

The `watch.log` file in `.logs/` captures every A2A request and response
with full message bodies. Look for:

* Opening request carries **two** DataParts: `ap2.mandates.IntentMandate`
  **and** `ap2.haggle.NegotiationConstraints`.
* Mid-negotiation Offers embed a plain `CartContents`, with **no**
  `merchant_authorization` field — they are unsigned.
* Final accepted outcome carries a `NegotiationOutcome` **and** a top-level
  `ap2.mandates.CartMandate` DataPart (for baseline-AP2 scanners) whose
  `merchant_authorization` is the placeholder demo JWT.

## Files

| Path | Purpose |
|---|---|
| [`src/ap2/types/negotiation.py`](../../../../../src/ap2/types/negotiation.py) | Pydantic schemas — `NegotiationConstraints`, `Offer`, `Argument`, `NegotiationOutcome`. |
| [`docs/haggle-extension.md`](../../../../../docs/haggle-extension.md) | A2A extension spec — URI, DataPart keys, example messages. |
| [`docs/topics/life-of-a-negotiation.md`](../../../../../docs/topics/life-of-a-negotiation.md) | Narrative walkthrough of the flow. |
| [`samples/python/src/common/haggle_utils.py`](../../../src/common/haggle_utils.py) | Message builders / DataPart extractors / `seal_offer_as_cart_mandate`. |
| [`samples/python/src/common/claude_negotiator.py`](../../../src/common/claude_negotiator.py) | Shared Claude tool-use engine used by both sides. |
| [`samples/python/src/roles/shopping_agent/subagents/negotiator/decide.py`](../../../src/roles/shopping_agent/subagents/negotiator/decide.py) | Shopper-side Claude system prompt + context rendering. |
| [`samples/python/src/roles/shopping_agent/tools.py`](../../../src/roles/shopping_agent/tools.py) | `negotiate_purchase` tool — multi-round loop driver. |
| [`samples/python/src/roles/merchant_agent/sub_agents/seller_strategist_agent.py`](../../../src/roles/merchant_agent/sub_agents/seller_strategist_agent.py) | Merchant-side Claude system prompt + context rendering. |
| [`samples/python/src/roles/merchant_agent/negotiation_workflow.py`](../../../src/roles/merchant_agent/negotiation_workflow.py) | Server-side tool — opening / counter / accept handlers. |
| [`config/inventory.json`](config/inventory.json) | Seeded cost floors, competitor prices, loyalty tier. |
