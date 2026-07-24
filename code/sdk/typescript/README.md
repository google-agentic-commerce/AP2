# @ap2-protocol/sdk

TypeScript types and [Zod](https://zod.dev) validation for [Agent Payments
Protocol](https://ap2-protocol.org) (AP2) mandates and receipts, generated
directly from the canonical [JSON Schemas](../schemas/ap2) — the same source
of truth the [Python SDK](../python) is generated from (`ap2/sdk/generated`).

This package addresses the "provide a generated ... TypeScript library that
mirrors the AP2 mandate models with validation (e.g. zod)" half of #67. It
does not yet cover the Python SDK's higher-level `ap2.sdk` helpers (SD-JWT
signing/verification, mandate chain builders, JWT key handling) — see
[Scope](#scope) below.

## Install

```sh
npm install @ap2-protocol/sdk
```

## Usage

```ts
import { PaymentMandateSchema } from '@ap2-protocol/sdk';

const result = PaymentMandateSchema.safeParse({
  transaction_id: 'tx_1',
  payee: { id: 's-1', name: 'Shop' },
  payment_amount: { amount: 1000, currency: 'USD' },
  payment_instrument: { id: 'pi-1', type: 'credit' },
});

if (result.success) {
  // result.data is a fully typed PaymentMandate
} else {
  console.error(result.error.issues);
}
```

Every schema exports both a Zod validator (`FooSchema`) and its inferred
TypeScript type (`Foo`):

- `PaymentMandateSchema` / `PaymentMandate`
- `CheckoutMandateSchema` / `CheckoutMandate`
- `OpenPaymentMandateSchema` / `OpenPaymentMandate`
- `OpenCheckoutMandateSchema` / `OpenCheckoutMandate`
- `PaymentReceiptSchema` / `PaymentReceipt`
- `CheckoutReceiptSchema` / `CheckoutReceipt`
- `AmountSchema`, `MerchantSchema`, `PispSchema`, `PaymentInstrumentSchema`,
  `JwkSchema`, `ItemSchema`, `ReceiptStatusSchema` (shared types)

## Regenerating

The schemas under `src/generated/` are generated, not hand-written:

```sh
npm run generate
```

This reads every schema in [`code/sdk/schemas/ap2`](../schemas/ap2) and
[`code/sdk/schemas/ap2/types`](../schemas/ap2/types), dereferences their
`$ref`s, and emits a matching Zod schema + type per file. Run it whenever the
JSON Schemas change, then commit the regenerated output alongside your schema
change — same workflow as `code/sdk/schemas/generate.py` on the Python side.

## Known limitations

- **`contains` is not enforced.** `open_checkout_mandate.json` and
  `open_payment_mandate.json` each use `contains` to require "at least one
  array element matching a specific alternative" (e.g. an open checkout
  mandate's `constraints` must include a `checkout.line_items` entry). The
  underlying [`json-schema-to-zod`](https://github.com/StefanTerdell/json-schema-to-zod)
  generator doesn't support `contains`, so it's silently dropped — arrays
  missing that element currently validate. Flagging rather than
  hand-patching generated output; a proper fix means extending the generator
  to emit a `.refine()` for `contains`, which needs its own review.
- **No compile-time narrowing on `oneOf`-branch schemas** (`PaymentReceipt`,
  `CheckoutReceipt`, `OpenPaymentMandate.constraints` entries). These are
  generated as `z.object(...).and(z.any().superRefine(...))`, and Zod/TS
  collapse `T & any` to `any`, so `z.infer` doesn't narrow by the `status` or
  `type` discriminator. Runtime validation is correct and covered by tests;
  only static typing is coarser than the other schemas.

## Scope

This PR ships the mandate/receipt **type and validation layer** — the part of
#67 explicitly asking for TS types "with validation (e.g. zod)". It
deliberately does not port `ap2.sdk`'s SD-JWT signing/verification, mandate
chain builders (`payment_mandate_chain.py`, `checkout_mandate_chain.py`), or
JWT/JWK helpers — that's cryptography-sensitive code that deserves its own
focused PR and review rather than being bundled in behind a types package.

It's also unrelated to `code/samples/typescript` (PR #144): that's a sample
application (Genkit + A2A agents) with its own inline, non-reusable schema
definitions. This package is the standalone, publishable library #67 asks
for; the sample could migrate to depend on it in a follow-up.
