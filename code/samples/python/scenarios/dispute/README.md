# AP2 Sample: Resolving a Post-Transaction Dispute from the Mandate Chain

This sample shows what happens **after** an AP2 flow completes and the parties disagree.
It is stdlib-only and needs no API key: it reads a dispute record whose evidence is exactly
the artifacts a completed flow leaves behind and prints a determination under a published
policy (ATDRP-0.1).

## Scenario

A shopping agent completed a human-not-present purchase of 4 units under a signed Payment
Mandate; the merchant issued Success receipts; the order record shows 1 of 4 units
fulfilled and the merchant's own `estimated_delivery` window has passed with no
adjustment. The payer's agent opens a dispute on ground `performance`.

The resolver:

1. verifies the **authorization chain** the protocol defines — `payment_mandate.transaction_id`
   and both receipts' `reference` bind to the closed checkout mandate's `checkout_hash`. A
   chain that does not bind is a fraud/authorization question and is routed to the
   network (`not_eligible: authorization_chain_broken`), which is where AP2 already sends it;
2. checks the payment receipt is `Success`;
3. applies a deterministic rule per line (moot by prior refund → uphold; charge above
   mandate / execution after `exp` / mandate reuse → overturn; merchant cancel or units
   unfulfilled after the merchant's own estimate → overturn the unfulfilled share;
   instruction/cart conflict → recorded against the agent platform, merchant's charge
   stands; otherwise uphold);
4. emits a determination with per-line outcomes and amounts, the five factors considered,
   a signer-of-record slot, a fee disposition (loser pays), and a content-hash seal.

## Run

```sh
python code/samples/python/scenarios/dispute/resolve_dispute.py \
  code/samples/python/scenarios/dispute/dispute_record.json --now 2025-10-24
```

Expected: line `line_item_456` is **overturned for 7500 minor units** (3 of 4 units
unfulfilled after the estimated delivery of 2025-10-16), fee paid by the merchant. Tamper
with `payment_mandate.transaction_id` and the same command returns
`not_eligible: authorization_chain_broken` with `route: network fraud process`.

## What this is and is not

- It is a demonstration that the AP2 trail is **sufficient evidence** for a neutral third
  party to resolve non-fraud disputes without any data the protocol does not already emit.
- It names no provider and takes no position on who should run the resolver. The policy it
  applies is published separately (ATDRP-0.1) and proposed to ACP as a `dispute_resolution`
  extension.
- The seal here is a content hash; a production resolver anchors determinations on an
  append-only chain with public verification.
