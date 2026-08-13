<!--
 Copyright 2025 Google LLC
 Licensed under the Apache License, Version 2.0 (the "License").
-->

# `common/vi` — Verifiable Intent integration

TypeScript replication of the official Python reference flow
(`verifiable_intent/python/examples`), wired into the AP2 sample. It is a thin,
per-role facade over the [`verifiable-intent-js`](https://www.npmjs.com/package/verifiable-intent-js)
library that produces a cryptographic, layered SD-JWT delegation chain so a
merchant and a payment network can independently prove an autonomous agent
purchased **exactly what the human authorized**.

## The layer model

A chain of signed credentials, each one binding the **next** signer's key
(`cnf.jwk`, RFC 7800) and the **previous** document's hash (`sd_hash`):

| Layer | Signed by | Says | VI call |
|---|---|---|---|
| **L1** issuer credential | Credentials Provider | "this card belongs to the user" + binds the **user** key | `issueIssuerCredential` → `createLayer1` |
| **L2** user mandate | User | "I authorize **this agent** within these limits" + constraints | `createUserMandate{Autonomous,Immediate}` |
| **L3a** payment (→ network) | Agent | "pay $X to merchant M for txn T" | `createLayer3Payment` |
| **L3b** checkout (→ merchant) | Agent | "here is the final checkout JWT" | `createLayer3Checkout` |

Two modes: **autonomous** (Human-Not-Present — L1→L2→split-L3, the agent acts
later within the mandate) and **immediate** (Human-Present — L1→L2 with final
values, no L3). Amounts are always **minor units (cents)**.

## AP2 role → layer mapping

```
 Credentials Provider     User / shopping-agent-v2        Shopping Agent
   = Issuer (L1)            = User mandate (L2)            = Agent (L3 split)
        │                          │                             │
        │ L1 (binds user key)      │ L2 (binds agent key,        │ L3a → network
        └────────────────────────► │      constraints) ────────► │ L3b → merchant
                                                                  │
   merchant-agent-mcp  ── verifyCheckoutChain (L1→L2→L3b, aud-pinned) ◄── L3b
   credentials-provider-mcp ── verifyPaymentChainAndConstraints (L1→L2→L3a) ◄── L3a
```

## Cross-role file contract (TEMP_DB)

The agent persists serialized SD-JWTs; the MCP servers read them back by id:

| File | Written by | Read by |
|---|---|---|
| `l1.sdjwt`, `l2.sdjwt` | `assembleAndSignMandates` | merchant, CP |
| `<chk>.sdjwt`, `<chk>.l2.sdjwt` | `createMandateFulfillment` (merchant view) | merchant `complete_checkout` |
| `<pay>.sdjwt`, `<pay>.l2.sdjwt` | `createMandateFulfillment` (network view) | CP `issue_payment_credential` |
| `<name>_key.jwk.json` | `loadOrCreateViKey` | every role |

## Public API (`flow.ts`)

- `issueIssuerCredential(params) → l1Serialized`
- `createUserMandateAutonomous(params) → l2Serialized`
- `createUserMandateImmediate(params) → l2Serialized`
- `createAgentFulfillment(params) → { l3PaymentSerialized, l3CheckoutSerialized, l2PaymentSerialized, l2CheckoutSerialized }`
- `verifyCheckoutChain(params) → ChainVerificationResult`  *(merchant; pin `expectedL3CheckoutAud`)*
- `verifyPaymentChainAndConstraints(params) → { valid, errors, result, constraints }`  *(network; pin `expectedL3PaymentAud`)*
- `createImmediateUserAuthorization(params) → userAuthorization`  *(v1 shopping agent; AP2 major units → VI minor, envelope `{ l1, l2 }`, L2 aud = `NETWORK_AUD`)*
- `verifyImmediateUserAuthorization(params) → { valid, errors, result }`  *(v1 merchant payment processor; pins L2 aud, cross-checks amount/currency/payee vs the AP2 PaymentMandate)*

The v1 (human-present) flow has no L3: `signMandatesOnUserDevice` signs an
immediate chain (L1 from the shared `issuer` key, L2 from the `user` key, bound
to `cartMandate.merchantAuthorization` via the checkout hash) into
`paymentMandate.userAuthorization`; `merchant-payment-processor-agent` verifies
it before the OTP challenge / payment execution.

Plus `fixtures.ts` (scenario data + `MERCHANT_AUD`/`NETWORK_AUD`), `keys.ts`
(file-backed JWK key store), `checkout-jwt.ts` (merchant checkout JWS).

## Security properties (enforced + tested)

Verified in `test/unit/vi-*.test.ts` (37 of 39 unit tests cover this module;
`src/common/vi` ≈96% stmts / 91% funcs):

- **Issuer trust** — chain fails closed without the issuer key; wrong key rejected.
- **Delegation binding** — only the `cnf`-bound agent key can sign a valid L3
  (an impostor key, even with a matching `kid`, is rejected).
- **Layer binding** — `sd_hash` ties L2→L1 and L3→L2; a tampered mandate fails.
- **Audience binding** — verifiers pin `aud`, rejecting a presentation addressed
  to a different party.
- **Spend cap** — amount at-cap allowed, one minor unit over / wrong currency rejected.
- **Freshness** — expired L3 (exp ≤ iat+3600) rejected.

## Known gaps (need a live e2e session to fix + verify)

See `../../../BACKLOG.md`: payment-token↔checkout binding, replay/nonce dedup,
and full e2e validation of the item-id consent fix. These involve the running
MCP/A2A servers and a Gemini key, so they can't be exercised by the unit suite.
