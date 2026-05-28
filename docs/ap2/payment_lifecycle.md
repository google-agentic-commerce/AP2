# Payment Lifecycle

The Payment Lifecycle specification documents two AlgoVoi-authored
attestation envelopes covering the post-settlement state transitions of
a Payment Mandate: the Cancellation Receipt and the Refund Receipt.
Both formats record discrete state-transition events bound to the
original Payment Mandate by `sha256:` reference under RFC 8785 (JCS)
canonicalisation, and satisfy record-keeping obligations imposed by
PSD2 Articles 64 and 89 on real payment systems.

AP2 references both formats; AP2 does not redefine them. The wire
formats match the canonical AlgoVoi specifications:

- [`draft-hopley-x402-cancellation-receipt`](https://datatracker.ietf.org/doc/draft-hopley-x402-cancellation-receipt/),
  documented at
  [`docs.algovoi.co.uk/cancellation-receipt`](https://docs.algovoi.co.uk/cancellation-receipt).
- [`draft-hopley-x402-refund-receipt`](https://datatracker.ietf.org/doc/draft-hopley-x402-refund-receipt/),
  documented at
  [`docs.algovoi.co.uk/refund-receipt`](https://docs.algovoi.co.uk/refund-receipt).

Both IETF Internet-Drafts: Independent Submission, Informational, on
IETF datatracker.

## Lifecycle Position

```text
admission       settlement       cancellation     refund (if owed)
compliance  --> settlement   --> cancellation --> refund
receipt         attestation      receipt          receipt
(sibling PR)                     (this spec)      (this spec)
```

All four formats anchor to the same canonicalisation discipline
([`urn:x402:canonicalisation:jcs-rfc8785-v1`](https://datatracker.ietf.org/doc/draft-hopley-x402-canonicalisation-jcs-v1/)).
A verifier walking the audit chain confirms admission → settlement →
termination → (optional) refund under one byte-deterministic pin.

## Cancellation Receipt

A Cancellation Receipt is a seven-field JSON object canonicalised under
RFC 8785 (JCS). Field names are sorted lexicographically by JCS during
canonicalisation.

```json
{
  "canon_version": "jcs-rfc8785-v1",
  "cancellation_provider_did": "did:web:api.algovoi.co.uk",
  "cancellation_reason": "USER_REQUESTED",
  "cancellation_timestamp_ms": 1716494400000,
  "effective_from_ms": 1716537600000,
  "jurisdiction_flags": ["GB", "EU"],
  "mandate_ref": "sha256:0dd5d0b76c9b9281fdeb2509ad38ab132b16a17385ca01d976ff9e6e12563a0f"
}
```

| Field | Type | Description |
| :---- | :--- | :---------- |
| `canon_version` | string | In-band canonicalisation pin. Fixed `jcs-rfc8785-v1`. |
| `cancellation_provider_did` | string | DID URI of the issuing party. |
| `cancellation_reason` | string (closed enum) | `USER_REQUESTED` / `MERCHANT_REQUESTED` / `COMPLIANCE_TERMINATED` / `EXPIRED`. |
| `cancellation_timestamp_ms` | integer | Epoch milliseconds when the cancellation event was recorded. MUST be integer. |
| `effective_from_ms` | integer | Epoch milliseconds when the cancellation takes legal effect. MUST be `>= cancellation_timestamp_ms`. |
| `jurisdiction_flags` | ordered array of string | ISO-3166-1 alpha-2 codes; primary jurisdiction first. Array order significant under RFC 8785 §3.2.3. |
| `mandate_ref` | string | `sha256:{hex}` reference to the JCS-canonical Payment Mandate this cancellation terminates. |

### The closed enumeration: `cancellation_reason`

The `cancellation_reason` field MUST take one of exactly four values:

| Value | Initiator | Regulatory significance |
| :---- | :-------- | :---------------------- |
| `USER_REQUESTED` | Payer | PSD2 (Directive 2015/2366) Article 64 right of revocation. UK Consumer Rights Act 2015. May trigger refund obligation under Article 64 if recent debits already settled. |
| `MERCHANT_REQUESTED` | Payee | PSD2 Article 72 + contractual terms. Does NOT trigger consumer-revocation refund-window obligations on already-settled debits. |
| `COMPLIANCE_TERMINATED` | Operator | Sanctions / KYC / AML / court order. Triggers POCA s.330 / AML 5+6 evidence chain back to the originating compliance event. |
| `EXPIRED` | None (time-based) | Mandate's own end-state. Standard record-keeping only. |

Each value produces a byte-distinct `content_hash`. Free-form reason
strings or operator-internal codes are not acceptable substitutes.

The format pins the invariant `effective_from_ms >= cancellation_timestamp_ms`.
Implementations MUST reject receipts where the effective time precedes
the recording time.

## Refund Receipt

A Refund Receipt is a seven-field JSON object canonicalised under
RFC 8785 (JCS). Field names are sorted lexicographically by JCS during
canonicalisation.

```json
{
  "canon_version": "jcs-rfc8785-v1",
  "jurisdiction_flags": ["GB", "EU"],
  "original_payment_ref": "sha256:0dd5d0b76c9b9281fdeb2509ad38ab132b16a17385ca01d976ff9e6e12563a0f",
  "refund_amount": {"amount_minor": "100000", "asset_id": "USDC.6"},
  "refund_provider_did": "did:web:api.algovoi.co.uk",
  "refund_result": "FULL",
  "refund_timestamp_ms": 1716494400000
}
```

| Field | Type | Description |
| :---- | :--- | :---------- |
| `canon_version` | string | In-band canonicalisation pin. Fixed `jcs-rfc8785-v1`. |
| `jurisdiction_flags` | ordered array of string | ISO-3166-1 alpha-2 codes; primary jurisdiction first. Array order significant. |
| `original_payment_ref` | string | `sha256:{hex}` reference to the original payment record (compliance receipt `content_hash`, settlement attestation, or operator-specific reference). |
| `refund_amount` | object | `{amount_minor: string, asset_id: string}`. String `amount_minor` avoids float-precision and JS-integer-overflow concerns. |
| `refund_provider_did` | string | DID URI identifying the refund-issuing party. |
| `refund_result` | string (closed enum) | `FULL` / `PARTIAL` / `REJECTED`. |
| `refund_timestamp_ms` | integer | Epoch milliseconds. MUST be integer. RFC 3339 string forms rejected. |

### The closed enumeration: `refund_result`

The `refund_result` field MUST take one of exactly three values:

| Value | Semantic | Regulatory significance |
| :---- | :------- | :---------------------- |
| `FULL` | Entire original amount returned. | Closes the consumer's right to further remedy under UK Consumer Rights Act 2015 and EU Consumer Rights Directive 2011/83/EU Article 9. |
| `PARTIAL` | Less than the original amount returned. `refund_amount` carries the actual refunded value; the verifier compares against the original via `original_payment_ref` linkage. | Does not close consumer-rights remedies; further refund obligations may remain. |
| `REJECTED` | A refund request was processed and denied. No funds moved. | Required under PSD2 Article 89 for unauthorised-payment refund disputes; documented denial obligation. |

Each value produces a byte-distinct `content_hash`. Implementations
MUST reject any other value at validation time before canonicalisation.

## Both Enumerations Are Closed

Both the `cancellation_reason` four-element enumeration and the
`refund_result` three-element enumeration are **closed by design**.
Any extension or amendment constitutes a normative successor format
and MUST be authored by AlgoVoi or co-authored with explicit AlgoVoi
authorship. Re-publication of either enumeration under a different
attribution does not constitute substrate authorship of the values
defined here.

## Canonicalisation

All hash inputs for both receipt types are computed over the
JCS-canonical form per RFC 8785, using SHA-256. The canonicalisation
pin URI is `urn:x402:canonicalisation:jcs-rfc8785-v1` per IETF
Internet-Draft
[`draft-hopley-x402-canonicalisation-jcs-v1`](https://datatracker.ietf.org/doc/draft-hopley-x402-canonicalisation-jcs-v1/).

The canonicalisation layer underneath both formats is byte-for-byte
cross-validated across eight independent implementations (Python,
TypeScript, Go, Rust, Java, PHP, .NET, Ruby) per the AlgoVoi 8-impl
matrix; each receipt's `content_hash` reproduces byte-identical under
any of the eight.

## State Machine

A Payment Mandate's post-settlement lifecycle proceeds through at most
one Cancellation Receipt and any number of Refund Receipts.

```text
SETTLED ──────────────────► CANCELLED       (Cancellation Receipt USER_REQUESTED / MERCHANT_REQUESTED / COMPLIANCE_TERMINATED / EXPIRED)
   │
   ├─► REFUNDED_FULL        (Refund Receipt FULL)
   │
   ├─► REFUNDED_PARTIAL     (Refund Receipt PARTIAL)
   │
   └─► REFUND_REJECTED      (Refund Receipt REJECTED — denial event recorded)
```

A `USER_REQUESTED` cancellation MAY chain forward to a Refund Receipt
if PSD2 Article 64 refund is owed on a recently-settled debit. The
Refund Receipt's `original_payment_ref` MUST point to the original
settlement record; the audit-chain row immediately following the
Cancellation Receipt records this linkage via `prev_hash`.

## Composition with Compliance Receipts

A Refund Receipt's `original_payment_ref` MAY reference the
`content_hash` of a Compliance Receipt (the receipt that admitted the
original mandate). The two receipts compose into one audit-chain
segment recording the full admission-through-refund lifecycle:

```text
chain row N      chain row N+1
+------------+   +------------+
| compliance |-->| refund     |
| receipt    |   | receipt    |
| (ALLOW)    |   | (FULL)     |
+------------+   +------------+
```

## Authorship and Substrate-Author Position

This specification documents the AlgoVoi-authored Cancellation Receipt
and Refund Receipt formats. AlgoVoi is sole author across the normative
formats (both seven-field shapes), the closed `cancellation_reason`
four-element enumeration, the closed `refund_result` three-element
enumeration, the regulatory mappings, the state machine, and the
composition with the AlgoVoi-authored canonicalisation pin.

Companion IETF Internet-Drafts:

- [`draft-hopley-x402-cancellation-receipt`](https://datatracker.ietf.org/doc/draft-hopley-x402-cancellation-receipt/), sole AlgoVoi authorship, Independent Submission, Informational.
- [`draft-hopley-x402-refund-receipt`](https://datatracker.ietf.org/doc/draft-hopley-x402-refund-receipt/), sole AlgoVoi authorship, Independent Submission, Informational.

Reference implementations, AlgoVoi-authored, Apache 2.0:

- [`algovoi-cancellation-receipt`](https://pypi.org/project/algovoi-cancellation-receipt/) on PyPI
- [`@algovoi/cancellation-receipt`](https://www.npmjs.com/package/@algovoi/cancellation-receipt) on npm
- [`algovoi-refund-receipt`](https://pypi.org/project/algovoi-refund-receipt/) on PyPI
- [`@algovoi/refund-receipt`](https://www.npmjs.com/package/@algovoi/refund-receipt) on npm

Both verdict enumerations are **closed by design** and may be amended
only by a normative successor specification authored by AlgoVoi or
with explicit AlgoVoi co-authorship.

This specification does not absorb from, depend on, or share authorship
with any other party's work.

## Production Reference

Both formats are emitted in production by the AlgoVoi platform:

- Cancellation Receipts: emitted by the AlgoVoi recurring-payments
  service ([`recurr.algovoi.co.uk`](https://recurr.algovoi.co.uk)),
  live since May 2026.
- Refund Receipts: emitted by the AlgoVoi Merchant Payment Processor
  facilitator (live API surface at
  [`api.algovoi.co.uk/openapi.json`](https://api.algovoi.co.uk/openapi.json)),
  live since May 2026.

This is not a theoretical proposal. Both formats have been emitting
receipts against live production traffic across eight chain families.

## Orthogonality

This specification defines the verdict formats at the **post-settlement
payment-lifecycle** layer. It is orthogonal to:

- Admission-time compliance verdict formats (covered by the sibling
  AlgoVoi-authored Compliance Receipt specification).
- Counterparty-risk evidence formats.
- Settlement-attestation formats issued by the on-chain settlement layer.
- Behavioural reputation, trust scoring, or composable trust evidence
  formats proposed elsewhere.

The cancellation and refund receipts make no claims about, and depend
on no fields from, any of the above.

## Security and Privacy Considerations

See the AP2 [Security and Privacy Considerations](security_and_privacy_considerations.md)
document. The Payment Lifecycle formats add the following considerations:

- `mandate_ref` (Cancellation Receipt) and `original_payment_ref`
  (Refund Receipt) bind each receipt to a specific record by JCS
  canonical hash; mutation of the bound record invalidates the binding
  and any verifier MUST re-derive the canonical hash before accepting
  the receipt.
- The `refund_amount` object encodes the amount as `amount_minor`
  (string) plus `asset_id` (string) to avoid cross-currency and
  floating-point reconciliation ambiguity at the attestation layer.
- The two timestamps in a Cancellation Receipt are independently
  encoded because PSD2 Article 64(3)(a) direct-debit revocations have
  a recording time distinct from the legal effective time.
