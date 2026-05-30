# Payment Evidence Frame

A Payment Evidence Frame (PEF) is a transport-agnostic envelope that wraps
any AP2 payment lifecycle receipt under a named `claim_type`, a deterministic
`frame_id`, and an optional transport-layer signature. It is designed to be
composable: agents pass `frame_id` values by reference across task boundaries
without re-transmitting the full inner receipt, while consumers can verify
receipt integrity from `receipt_hash` before deserialising the receipt body.

The normative wire format is specified in IETF Internet-Draft
[`draft-hopley-x402-payment-evidence-frame`](https://datatracker.ietf.org/doc/draft-hopley-x402-payment-evidence-frame/).

## Overview

Individual AP2 payment lifecycle receipts carry their own semantics but share
no common envelope. A downstream relying party consuming a mix of receipt
types must parse each receipt body to determine what lifecycle event it
represents, cannot reference a receipt stably across systems without
transmitting its full content, and has no integrity check short of full
deserialisation.

The PEF solves these three gaps:

1. **`claim_type`** -- a taxonomy label that identifies the lifecycle event
   without parsing the inner receipt body.
2. **`frame_id`** -- a stable, content-addressed cross-system identifier
   derived from the JCS canonical form of the frame, excluding `frame_id`
   and `signature` from the preimage.
3. **`receipt_hash`** -- an integrity check over the inner receipt computed
   from `sha256:` of its JCS canonical form, enabling integrity verification
   without deserialising the receipt.

The PEF does not redefine the inner receipt formats. Each receipt format
remains normatively specified by its own I-D or AP2 sub-document.

## claim_type Taxonomy

The `claim_type` field is a closed enumeration. Each value maps to exactly
one `receipt_format` string and one fixed set of status values within that
format.

| `claim_type` | `receipt_format` | Status values |
| :--- | :--- | :--- |
| `payment_admission` | `compliance-receipt-v1` | `ALLOW` / `REFER` / `DENY` |
| `payment_settlement` | `settlement-attestation-v1` | `SETTLED` / `PENDING_FINALITY` / `REVERSED` |
| `payment_cancellation` | `cancellation-receipt-v1` | `USER_REQUESTED` / `MERCHANT_REQUESTED` / `COMPLIANCE_TERMINATED` / `EXPIRED` |
| `payment_refund` | `refund-receipt-v1` | `FULL` / `PARTIAL` / `REJECTED` |
| `composite_verdict` | `composite-trust-query-v1` | `TRUSTED` / `PROVISIONAL` / `INSUFFICIENT_EVIDENCE` / `UNTRUSTED` |

The enumeration is **closed by design**. A PEF carrying an unrecognised
`claim_type` MUST be rejected by conforming consumers. Any extension
constitutes a normative successor format.

## Frame Fields

The PEF is a JSON object canonicalised under RFC 8785 (JCS). All fields are
REQUIRED except `signature`.

| Field | Type | Description |
| :---- | :--- | :---------- |
| `pef_version` | string | Fixed `"1"` for this version of the format. |
| `claim_type` | string | Closed enum; see taxonomy table above. |
| `receipt_format` | string | Closed mapping from `claim_type`; see taxonomy table above. |
| `receipt` | object | Inner receipt embedded verbatim as a JSON object. |
| `receipt_hash` | string | `sha256:<hex>` of the JCS canonical bytes of `receipt`. |
| `frame_id` | string | `sha256:<hex>` of the JCS canonical bytes of the frame with `frame_id` and `signature` excluded from the preimage. |
| `frame_provider_did` | string | DID URI identifying the party that constructed the frame. |
| `frame_timestamp_ms` | integer | Unix epoch milliseconds at which the frame was constructed. |
| `canon_version` | string | In-band canonicalisation pin. Fixed `urn:x402:canonicalisation:jcs-rfc8785-v1` for this version. |
| `signature` | string | OPTIONAL. RFC 9421 HTTP Message Signature string over the frame. Adding `signature` to an existing frame does NOT change `frame_id`. |

## frame_id Derivation

To derive `frame_id`:

1. Construct the frame object with all fields present except `frame_id` and
   `signature`.
2. Compute the RFC 8785 (JCS) canonical byte string of that object. Field
   names are sorted lexicographically; string values are Unicode-normalised
   per JCS section 3.2.3.
3. Compute `sha256` of the canonical bytes.
4. Encode as `sha256:<lowercase-hex>`.
5. Set `frame_id` to this value.

The `frame_id` field itself and the `signature` field are both excluded from
the preimage. This ensures that:

- `frame_id` is computable before signing.
- Adding a `signature` to a previously unsigned frame does not change the
  `frame_id`.

## receipt_hash Derivation

To derive `receipt_hash`:

1. Take the `receipt` object as embedded in the frame.
2. Compute the RFC 8785 (JCS) canonical byte string of the `receipt` object
   in isolation.
3. Compute `sha256` of those canonical bytes.
4. Encode as `sha256:<lowercase-hex>`.

A consumer verifying `receipt_hash` MUST re-canonicalise the embedded
`receipt` independently and compare the resulting hash before treating the
receipt as authentic.

## frame_id Stability

`frame_id` is stable across the following operations:

- Adding a `signature` field to an unsigned frame -- `signature` is excluded
  from the preimage.
- Re-serialising the frame -- JCS canonicalisation is deterministic.
- Transmitting the frame across different transports -- the frame is
  transport-agnostic.

`frame_id` changes if any other field changes, including `frame_timestamp_ms`
or any field of the embedded `receipt`.

## Usage in AP2 Flows

In an AP2 flow, agents pass `frame_id` values by reference across task
boundaries. A Shopping Agent that has received and verified a PEF MAY
communicate the `frame_id` to a downstream party without retransmitting the
full frame. The downstream party can then request the full frame from the
frame provider by `frame_id` if needed.

Typical flow:

```text
Facilitator                Shopping Agent                Merchant
    |                            |                           |
    |--- PEF (payment_admission) -->|                         |
    |                            |-- frame_id only ---------->|
    |                            |                           |
    |                            |<-- request frame by id ---|
    |<-- request frame by id ----|                           |
    |--- full PEF -------------->|-- full PEF -------------->|
```

The `claim_type` field allows a receiving agent to determine the lifecycle
event class without parsing the inner receipt. A Shopping Agent MAY apply
routing logic based on `claim_type` alone before deciding whether to
deserialise the `receipt` body.

## Example

The following is a live frame from the production AP2-compliant gateway,
representing a `payment_admission` event (compliance screening outcome
`ALLOW`):

```json
{
  "canon_version": "urn:x402:canonicalisation:jcs-rfc8785-v1",
  "claim_type": "payment_admission",
  "frame_id": "sha256:9badca886409ed26d09adfe6ce133a53100909dd4544d4ad160e130b6a755f29",
  "frame_provider_did": "did:key:z6MkgExzvcpvxrghf4Q3285xqSdenhRZHcP6wc5UvY6VVaz5",
  "frame_timestamp_ms": 1780143974835,
  "pef_version": "1",
  "receipt": {
    "canon_version": "jcs-rfc8785-v1",
    "jurisdiction_flags": ["UK", "EU"],
    "payer_ref": "sha256:e0f023d54479255752bac099d0565984b5884afec0f1a1ebe27e0eaf70a205ba",
    "screen_provider_did": "did:key:z6MkgExzvcpvxrghf4Q3285xqSdenhRZHcP6wc5UvY6VVaz5",
    "screen_result": "ALLOW",
    "screen_timestamp_ms": 1780143974835
  },
  "receipt_format": "compliance-receipt-v1",
  "receipt_hash": "sha256:bc7a68b64925b8a76109d35e89cca4c7ae04073fa686844975a5b5f4410afa27"
}
```

Note that the frame is unsigned (`signature` absent). A signed frame would
carry an additional `signature` field. The `frame_id` would remain
unchanged.

## Reference Implementation

Two reference implementations are published under Apache 2.0:

- Python: [`algovoi-pef`](https://pypi.org/project/algovoi-pef/) on PyPI
- TypeScript: [`@algovoi/pef`](https://www.npmjs.com/package/@algovoi/pef) on npm

Both packages implement `frame_id` derivation, `receipt_hash` derivation, and
RFC 9421 signature verification against the canonical preimage.

## Normative Reference

- [`draft-hopley-x402-payment-evidence-frame`](https://datatracker.ietf.org/doc/draft-hopley-x402-payment-evidence-frame/)
  -- normative wire format, field definitions, and closed enumerations.
- RFC 8785 -- JSON Canonicalisation Scheme (JCS), used for canonical
  preimage derivation.
- RFC 9421 -- HTTP Message Signatures, used for the optional `signature`
  field.
- [`draft-hopley-x402-canonicalisation-jcs-v1`](https://datatracker.ietf.org/doc/draft-hopley-x402-canonicalisation-jcs-v1/)
  -- canonicalisation pin URI `urn:x402:canonicalisation:jcs-rfc8785-v1`.

## Security and Privacy Considerations

See the AP2 [Security and Privacy Considerations](security_and_privacy_considerations.md)
document. The PEF adds the following considerations:

- A consumer MUST verify `receipt_hash` by re-canonicalising the embedded
  `receipt` independently. Accepting `receipt_hash` without re-deriving it
  allows a malicious framer to substitute a different receipt body.
- `frame_id` stability is predicated on deterministic JCS canonicalisation.
  Consumers MUST use a conforming RFC 8785 implementation when re-deriving
  `frame_id` for verification.
- The `frame_provider_did` field is informational within the unsigned frame.
  If the `signature` field is present, consumers SHOULD verify it before
  treating `frame_provider_did` as authoritative.
- The embedded `receipt` may carry personal data (for example, `payer_ref`).
  Transport of PEF frames MUST use a confidential channel when the `receipt`
  contains personally identifiable information or payment reference data.
