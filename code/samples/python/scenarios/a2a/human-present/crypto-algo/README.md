<!-- cspell:words Algorand algorand ALGOVOI AlgoVoi algod ASA microalgos testnet mainnet Pera Defly USDt -->

# Agent Payments Protocol Sample: Human Present Purchases with On-Chain Algorand USDC

This sample demonstrates the A2A `ap2-extension` for a human-present transaction
where the buyer settles with on-chain USDC on Algorand (or native ALGO for
micropayments). It mirrors the existing `x402` scenario but uses Algorand
settlement semantics, specifically the transaction **note field**, to bind the
settling transaction to a specific AP2 `PaymentMandate`.

**Note:** This sample pairs with the separate `crypto-solana` human-present
scenario. Together they cover non-EVM settlement on Algorand and Solana as a
complement to the EVM-focused `x402` path.

## What this sample includes (and what it does not)

This directory ships two things: this document and a `run.sh` launcher. The
launcher starts the standard AP2 sample roles (Merchant, Credentials Provider,
Merchant Payment Processor, and the Shopping Agent) with
`PAYMENT_METHOD=CRYPTO_ALGO` exported so downstream code can branch on it.

The bundled sample role code does **not** itself implement the
`CRYPTO_ALGO` settlement path end to end. Verifying an on-chain Algorand
transfer, resolving the note binding, and returning a `PaymentReceipt` require
an **external, AP2-aware facilitator** that understands Algorand settlement.
The sections below describe the intended flow and the note-binding contract so
that a facilitator (AlgoVoi Cloud is one example, but any Algorand-aware AP2
facilitator works) can be plugged in. Treat this scenario as a reference design
plus a launcher, not as a self-contained end-to-end demonstration.

## Scenario

Human-present flows are commerce flows where the user is present to confirm
purchase details. The user signs the `PaymentMandate`, giving all parties high
confidence in the transaction.

The Algorand variant adds one additional primitive on top of the standard AP2
mandate chain:

### Note-field binding

Algorand transactions carry an arbitrary **note field** (up to 1024 bytes).
Unlike Solana, no side-channel `reference` account is needed, because the note
travels inside the settling transaction itself. This scenario uses a compact
binding tag:

1. When the Merchant Agent assembles the `CartMandate`, it derives a short
   binding token from the canonical cart contents.
2. The token is placed in the payment request note field, prefixed so it is
   easy to identify on chain:

   ```text
   av:<token>
   ```

   The token is truncated to 20 characters, so the whole tag is roughly 23
   bytes. Algorand allows up to 1024 note bytes, so this stays well within the
   field with generous headroom, and it keeps the tag cheap to index.
3. The payment request is expressed as an ARC-26 Algorand URI so any compatible
   wallet (Pera, Defly, and others) can construct the transfer:

   ```text
   algorand://<recipient>
     ?amount=<amount>
     &asset=<USDC_asset_id>
     &note=av:<token>
   ```

4. The buyer signs and broadcasts the ASA transfer. The note rides along inside
   the same transaction.
5. After settlement, the facilitator (invoked by the Merchant Payment Processor
   Agent) fetches the confirmed transaction and checks that the note carries the
   expected `av:` binding tag and that the recipient, amount, and asset id match
   the AP2 `PaymentMandate`.

### MPP rejection behavior

The Merchant Payment Processor (MPP) Agent treats the note binding as a hard
gate. If the settling transaction's note does not carry the expected `av:`
tag for this cart, or if the recipient, amount, or asset id disagree with the
signed `PaymentMandate`, the MPP **rejects** the payment rather than issuing a
`PaymentReceipt`. This gives a cryptographic consistency check between what the
user signed off chain and what actually settled on chain, without trusting the
buyer to self-report a transaction id.

## Key Actors

This sample consists of:

- **Shopping Agent:** The main orchestrator that handles the user's shopping
  request and delegates to specialist agents.
- **Merchant Agent:** Handles product queries, assembles the `CartMandate`, and
  derives the `av:` note binding token for the payment request.
- **Merchant Payment Processor Agent:** Takes payments on behalf of the
  merchant and, in the Algorand flow, delegates verification of the on-chain
  ASA transfer (note binding, recipient, amount, asset id) to an external
  facilitator.
- **Credentials Provider Agent:** Holds the user's payment credentials, in this
  flow the Algorand address and optional asset preferences.

## Mandate Chain

The AP2 mandate chain is unchanged by the Algorand variant:

```text
IntentMandate  ==>  CartMandate  ==>  PaymentMandate
     (user)             (merchant)       (user-signed)
                                                |
                                                v
                              ARC-26 Algorand URI (note-bound)
                                                |
                                                v
                             ASA transfer + note=av:<token>
                                                |
                                                v
                          facilitator verifies note + amount + asset
                                                |
                                                v
                                   PaymentReceipt
```

## Payment Method

This scenario sets `PAYMENT_METHOD=CRYPTO_ALGO` at startup. Downstream agents
treat it as a non-card, non-x402 payment flow and route through the
Algorand-aware credentials provider and facilitator path.

## Assets Supported

| Asset | Algorand ASA ID | Decimals |
| --- | --- | --- |
| USDC (Algorand mainnet) | `31566704` | 6 |
| USDt (Algorand mainnet) | `312769` | 6 |
| USDC (Algorand testnet) | `10458941` | 6 |
| Native ALGO | (none, base unit is microalgos) | 6 |

The ARC-26 URI carries the `asset` id, so supporting additional ASAs is a
configuration concern on the Merchant Agent and does not require protocol
changes. Native ALGO transfers omit the `asset` parameter and are denominated
in microalgos.

## Running the sample

```bash
# From the repository root:
export GOOGLE_API_KEY="..."                 # or GOOGLE_GENAI_USE_VERTEXAI=true

# Optional: point the flow at an Algorand-aware AP2 facilitator.
# AlgoVoi Cloud is one example; any facilitator that verifies Algorand
# settlement and the av: note binding works. If you do not configure one,
# the launcher still starts the agents, but on-chain verification will be
# a no-op until a facilitator is wired in.
# export ALGOVOI_API_KEY="..."              # example facilitator credential
# export ALGORAND_RPC_URL="https://..."     # algod endpoint (mainnet/testnet)

./code/samples/python/scenarios/a2a/human-present/crypto-algo/run.sh
```

The sample script starts the Merchant, Credentials Provider, and Merchant
Payment Processor agents locally, then launches the Shopping Agent via the ADK
web UI. You can drive the shopping conversation through mandate creation. To
complete on-chain settlement and receive a `PaymentReceipt`, connect an
external Algorand-aware facilitator as described above.

## Why note-field binding matters for AP2

AP2 mandates are already cryptographically signed, but they describe intent and
authorization, not the on-chain settlement event itself. The `av:` note tag is
the link that ties a specific Algorand transaction to a specific `CartMandate`
deterministically, inside the settling transaction, without trusting the buyer
to self-report a transaction id. For agent-initiated commerce, where the buyer
may be an AI agent and the merchant may be another AI agent, this mechanical
binding removes an otherwise social trust layer.

## Reference implementations

- Any Algorand-aware AP2 facilitator that can (a) fetch the confirmed
  transaction from an algod or indexer endpoint, (b) check the note carries the
  expected `av:` binding tag, and (c) confirm the asset id, amount, and
  recipient match the signed `PaymentMandate`. AlgoVoi Cloud is one example
  implementation of such a facilitator.
- [ARC-26 Algorand URI scheme](https://arc.algorand.foundation/ARCs/arc-0026)
  for the canonical payment request URI format.
- [Algorand Standard Assets (ASA)](https://developer.algorand.org/docs/get-details/asa/)
  for asset transfer mechanics.
