# AP2-Haggle Extension

!!! info

    This is an [Agent2Agent (A2A) extension](https://a2a-protocol.org/latest/topics/extensions/)
    that layers **real-time, multi-round negotiation** between buyer and seller
    agents on top of the base [Agent Payments Protocol (AP2)](./a2a-extension.md).

    `v0.1-alpha`

AP2's three-mandate core (Intent / Cart / Payment) supports only one-shot cart
selection. The upstream roadmap explicitly names real-time buyer/seller
negotiation as long-term vision. This extension fills that gap while leaving
the payment path unchanged: negotiation terminates with a standard merchant-
signed `CartMandate`, so downstream credentials providers and payment
processors need no awareness of haggling.

## Extension URI

The URI for this extension is
`https://github.com/ap2haggle/ap2/extensions/haggle/v0.1`.

Agents that support the AP2-Haggle extension MUST use this URI. Support for
the base AP2 extension URI is also required — the haggle extension is
additive, not a replacement.

## Relationship to base AP2

The haggle extension defines three new data types and the messages that carry
them:

- `NegotiationConstraints` — buyer-side policy attached to an `IntentMandate`.
- `Offer` — a non-binding proposal exchanged in each round.
- `NegotiationOutcome` — terminal state of the negotiation thread, which (on
  acceptance) embeds a standard AP2 `CartMandate`.

Intermediate `Offer`s are **not** signed. The only signed artifact in a
negotiation is the final `CartMandate`, produced by the merchant when both
sides converge. This preserves AP2's existing non-repudiation semantics.

## Agent AP2-Haggle Role

The haggle extension does not introduce new AP2 roles. Every agent
participating in negotiation MUST already perform at least one of the base
AP2 roles (`merchant`, `shopper`, `credentials-provider`,
`payment-processor`).

In practice, the haggle flow only involves the `merchant` and `shopper`
roles — the `credentials-provider` and `payment-processor` see nothing new,
because negotiation completes before payment begins.

## AgentCard Extension Object

Agents that support the haggle extension MUST advertise it in their
AgentCard capabilities list. The extension is declared **alongside** the base
AP2 extension — not in place of it.

The `params` used in the `AgentExtension` MUST adhere to the following JSON
schema:

```json
{
  "type": "object",
  "name": "HaggleExtensionParameters",
  "description": "Parameters for the AP2-Haggle A2A extension.",
  "properties": {
    "supports_negotiation": {
      "type": "boolean",
      "description": "Whether this agent is willing to engage in negotiation."
    },
    "negotiable_axes": {
      "type": "array",
      "description": "Optional hint: well-known term keys this agent understands. Open set — receivers SHOULD treat unknown keys as pass-through and fall back to `Argument.summary`.",
      "items": { "type": "string" },
      "example": ["price", "delivery_days", "warranty_months", "bundle_skus"]
    },
    "max_rounds_hint": {
      "type": "integer",
      "description": "Optional hint: rounds this agent prefers to cap at. Each negotiation's effective max is carried per-call in NegotiationConstraints."
    }
  },
  "required": ["supports_negotiation"]
}
```

The following listing shows an AgentCard declaring both base AP2 and
haggle support for a merchant:

```json
{
  "name": "Haggle-Aware Merchant",
  "description": "Sells goods. Willing to negotiate price, delivery, and warranty.",
  "capabilities": {
    "extensions": [
      {
        "uri": "https://github.com/google-agentic-commerce/ap2/v1",
        "description": "Supports the Agent Payments Protocol.",
        "required": true
      },
      {
        "uri": "https://github.com/ap2haggle/ap2/extensions/haggle/v0.1",
        "description": "Supports real-time negotiation over price, delivery and warranty.",
        "required": false,
        "params": {
          "supports_negotiation": true,
          "negotiable_axes": ["price", "delivery_days", "warranty_months", "bundle_skus"],
          "max_rounds_hint": 8
        }
      }
    ]
  }
}
```

A shopping agent that *may* but not *must* negotiate SHOULD leave the
haggle extension `"required": false`. A merchant that cannot serve
non-negotiation traffic MAY set it to `true`, but this is rarely desirable.

## Haggle Data Type Containers

The following sections describe how the three haggle data types are
encapsulated as A2A message/artifact parts. All three reuse the `contextId`
of the opening A2A Message as the negotiation thread identifier.

### NegotiationConstraints on IntentMandate Message

A shopping agent that wants to open a negotiation MUST send an IntentMandate
Message that includes **both** the base AP2 `ap2.mandates.IntentMandate`
DataPart **and** an additional DataPart keyed `ap2.haggle.NegotiationConstraints`.

Presence of the `NegotiationConstraints` DataPart is the signal to the
merchant that this is a negotiation, not a one-shot cart request.

The Message MAY also contain a `risk_data` DataPart as in the base protocol.

Example:

```json
{
  "messageId": "d2a9…",
  "contextId": "ctx_neg_laptop_4711",
  "taskId": "task_neg_laptop_4711",
  "role": "user",
  "parts": [
    {
      "kind": "data",
      "data": {
        "ap2.mandates.IntentMandate": {
          "user_cart_confirmation_required": true,
          "natural_language_description": "A mid-range laptop for software development.",
          "merchants": null,
          "skus": null,
          "requires_refundability": true,
          "intent_expiry": "2026-04-25T15:00:00Z"
        }
      }
    },
    {
      "kind": "data",
      "data": {
        "ap2.haggle.NegotiationConstraints": {
          "max_rounds": 6,
          "deadline": "2026-04-24T18:00:00Z",
          "target_terms": {
            "price": 850.0,
            "currency": "USD",
            "warranty_months": 24,
            "delivery_days": 5
          },
          "walk_away_terms": {
            "price": 1000.0,
            "warranty_months": 18,
            "delivery_days": 7
          },
          "required_terms": {
            "currency": "USD",
            "refundable": true
          },
          "strategy_hint": "Open at $850. Invoke returning-customer discount and competitor comparison as levers.",
          "style": "cooperative"
        }
      }
    }
  ]
}
```

See `target_terms` / `walk_away_terms` / `required_terms` semantics in the
`NegotiationConstraints` Pydantic docstring — they are intentionally open
dicts so that services, contracts, and B2B deals can be negotiated with the
same schema.

### Offer Message

Either side MAY produce an Offer. An Offer Message is an A2A `Message` profile:

- MUST contain a DataPart with key `ap2.haggle.Offer` whose value adheres to
  the `Offer` schema.
- MUST preserve the negotiation `contextId` from the opening IntentMandate.
- MAY contain a `TextPart` carrying free-text commentary.

Intermediate Offers are **not** cryptographically signed. The embedded
`cart_contents` is a plain `CartContents`, not a `CartMandate`.

```json
{
  "messageId": "e0ad…",
  "contextId": "ctx_neg_laptop_4711",
  "taskId": "task_neg_laptop_4711",
  "role": "agent",
  "parts": [
    {
      "kind": "data",
      "data": {
        "ap2.haggle.Offer": {
          "offer_id": "offer_r0_merchant",
          "round_number": 0,
          "proposer_role": "merchant",
          "cart_contents": { "…": "standard AP2 CartContents" },
          "terms": {
            "price": 1200.0,
            "currency": "USD",
            "warranty_months": 12,
            "delivery_days": 7
          },
          "arguments": [
            {
              "type": "quality_guarantee",
              "summary": "Premium 7nm CPU, tested to MIL-STD-810H.",
              "payload": { "certification": "MIL-STD-810H" },
              "confidence": 0.9
            },
            {
              "type": "cost_floor",
              "summary": "Our wholesale cost is $960; $1200 leaves 20% margin.",
              "payload": { "wholesale": 960.0 },
              "confidence": 0.7
            }
          ],
          "expires_at": "2026-04-24T17:05:00Z",
          "parent_offer_id": null,
          "status": "proposed",
          "timestamp": "2026-04-24T17:00:00Z"
        }
      }
    }
  ]
}
```

A counter-offer is identical in shape, with `parent_offer_id` pointing to the
Offer being countered and `round_number` incremented.

### NegotiationOutcome Message

When a negotiation reaches a terminal state, the side that detects the
terminal condition MUST emit a `NegotiationOutcome` Message:

- MUST contain a DataPart with key `ap2.haggle.NegotiationOutcome` whose
  value adheres to the `NegotiationOutcome` schema.
- When `status == "accepted"`, the `final_cart_mandate` field MUST contain a
  fully-signed standard AP2 `CartMandate` produced by the merchant. The
  Message MAY additionally carry that CartMandate as a top-level
  `ap2.mandates.CartMandate` DataPart, so that any existing AP2 client code
  that scans for CartMandates still picks it up without haggle awareness.

```json
{
  "messageId": "c1ff…",
  "contextId": "ctx_neg_laptop_4711",
  "role": "agent",
  "parts": [
    {
      "kind": "data",
      "data": {
        "ap2.haggle.NegotiationOutcome": {
          "negotiation_id": "ctx_neg_laptop_4711",
          "status": "accepted",
          "accepted_offer_id": "offer_r3_shopper",
          "final_cart_mandate": { "…": "merchant-signed CartMandate" },
          "rounds_used": 3,
          "summary": "Converged on $1050 / 24mo warranty / 5-day delivery after 3 rounds."
        }
      }
    },
    {
      "kind": "data",
      "data": {
        "ap2.mandates.CartMandate": { "…": "same CartMandate, exposed at top level" }
      }
    }
  ]
}
```

### Terminal statuses

| status | When the negotiator emits it |
|---|---|
| `accepted` | Both sides converged on an Offer. `final_cart_mandate` is populated and signed. |
| `rejected` | `max_rounds` exhausted without convergence. No CartMandate. |
| `expired` | `deadline` passed. No CartMandate. |
| `abandoned` | One side explicitly walked away (offer violated a walk-away or required term). No CartMandate. |

## Flow

```
Shopper                                Merchant
  │                                        │
  │  IntentMandate + NegotiationConstraints │
  │ ─────────────────────────────────────▶ │
  │                                        │
  │  Offer (round 0, unsigned)             │
  │ ◀───────────────────────────────────── │
  │                                        │
  │  Offer (round 1, counter)              │
  │ ─────────────────────────────────────▶ │
  │                                        │
  │   … up to max_rounds / deadline …      │
  │                                        │
  │  NegotiationOutcome (accepted) +       │
  │  signed CartMandate                    │
  │ ◀───────────────────────────────────── │
  │                                        │
  │  >>> existing AP2 payment flow unchanged
```

## Security and trust notes

- Intermediate Offers are unsigned. A receiving agent MUST NOT take any
  binding action on an Offer alone. Only the terminal `CartMandate` carries
  merchant authorization.
- `expires_at` on each Offer SHOULD be short-lived (seconds to low minutes)
  to limit replay opportunity.
- Either side MAY abandon a negotiation at any time by emitting
  `NegotiationOutcome(status="abandoned")`.
- The merchant SHOULD validate that the accepted Offer's `terms` match the
  embedded `cart_contents.payment_request` before signing. The two
  representations are expected to agree; divergence is a protocol error.
- `NegotiationConstraints` expresses the buyer's private policy. A merchant
  that receives it MUST NOT echo `walk_away_terms` or `required_terms` back
  to the shopper — the contents are privileged shopper-side data.

## Extensibility

The schema is designed so that new negotiation dimensions — contract
duration, SLA tiers, reference customers, rebates — can be added without
bumping the extension URI:

- `Offer.terms` is an open dict.
- `NegotiationConstraints.{target_terms, walk_away_terms, required_terms}`
  are open dicts.
- `Argument.type` is an open string; `Argument.payload` is an open dict.

Implementations that need to converge on a specific key set (e.g. within a
single enterprise) SHOULD document their well-known keys out-of-band. The
protocol itself remains agnostic.
