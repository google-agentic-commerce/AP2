# HTTP Message Signing

AP2 payment flows use HTTP as the transport layer for mandate exchange,
checkout initiation, and payment proof submission. This section documents
the AlgoVoi-authored binding of RFC 9421 (HTTP Message Signatures) and
RFC 9530 (Digest Fields for HTTP) to AP2 payment mandate HTTP exchanges,
providing transport-layer cryptographic signing of AP2 mandate requests
and responses.

The normative binding is the AlgoVoi-authored `rfc9421-x402-binding-v1`
extension, documented at
[`docs.algovoi.co.uk/rfc9421-binding-v1`](https://docs.algovoi.co.uk/rfc9421-binding-v1).
Reference implementations:

- [`algovoi-rfc9421-verifier`](https://pypi.org/project/algovoi-rfc9421-verifier/) on PyPI
- [`@algovoi/rfc9421-verifier`](https://www.npmjs.com/package/@algovoi/rfc9421-verifier) on npm

Both packages are published under Apache 2.0.

## Usage

An AP2 participant that adopts HTTP Message Signing attaches RFC 9421
`Signature-Input` and `Signature` headers to AP2 mandate requests and
responses. The receiving party verifies the signature before processing
the mandate body.

HTTP Message Signing is complementary to the payload-level canonicalisation
provided by the AlgoVoi canonicalisation pin (`urn:x402:canonicalisation:jcs-rfc8785-v1`):
JCS canonicalises the mandate body for hash-bound content-addressing;
RFC 9421 signs the HTTP envelope carrying that body. The two operate at
distinct layers and compose without conflict.

## Covered Components

For AP2 mandate requests (checkout initiation, payment proof submission),
the minimum normative covered component set is:

| Component | Source | Rationale |
| :-------- | :----- | :-------- |
| `@method` | HTTP method | Binds the signature to the HTTP method. |
| `@authority` | HTTP authority | Binds the signature to the target origin. |
| `@path` | HTTP path | Binds the signature to the resource path. |
| `content-digest` | RFC 9530 Content-Digest of the body | Binds the signature to the integrity of the mandate body. |

Implementations MAY additionally cover RFC 9421 derived components per
their security policy. The minimum set above is normative for AP2
adoption of this binding.

## Content-Digest Discipline

Implementations MUST emit `Content-Digest` using `sha-256` (RFC 9530
mandatory baseline) and SHOULD emit `sha-512` for bodies at or above
4096 bytes. Verifiers MUST accept both. Verifiers MUST NOT silently skip
an unrecognised digest algorithm; they MUST treat it as if no usable
digest were present and reject the message.

## Multi-hop Proxy-chain Survival

AP2 deployments that route mandate requests through intermediary hops
(e.g. Network-layer proxies, Merchant Payment Processors acting as
intermediaries) MUST preserve the original `Signature` and `Signature-Input`
headers end-to-end. Intermediaries that modify the covered components
invalidate the original signature; such modifications MUST NOT occur without
producing a new, independently-verifiable signature from the intermediary.

The AlgoVoi proxy-chain conformance fixture at
[`chopmob-cloud/algovoi-jcs-conformance-vectors`](https://github.com/chopmob-cloud/algovoi-jcs-conformance-vectors)
(corpus `rfc9421_proxy_chain_v0`) provides byte-level reference digests
for the signing base and signature across a two-hop proxy chain.

## Canonicalisation Interaction

When the AP2 mandate body is also canonicalised under
`urn:x402:canonicalisation:jcs-rfc8785-v1`, the `content-digest` covered
component binds the RFC 9421 transport-layer signature to the specific
JCS-canonical byte sequence of the mandate. This allows a verifier to
confirm both:

1. The HTTP message was signed by the declared key (RFC 9421 layer).
2. The mandate body is the exact canonical form the signer intended (JCS layer).

## Authorship

This binding is AlgoVoi-authored. The underlying RFC 9421 and RFC 9530
standards are IETF publications independent of AlgoVoi.

## Orthogonality

HTTP Message Signing operates at the transport layer. It is orthogonal to:

- Payload canonicalisation (JCS; operates on the mandate body, not the
  HTTP envelope carrying it).
- Compliance Receipt and Settlement Attestation (payload-layer attestations
  that reference canonical mandate hashes, not HTTP headers).
- Agent identity registration (the agent card `signatureSchemes` field
  declares supported algorithms; this section specifies the per-request
  signing act, not the identity registration).

## Security and Privacy Considerations

See the AP2 [Security and Privacy Considerations](security_and_privacy_considerations.md)
document. HTTP Message Signing adds the following:

- The `created` RFC 9421 parameter SHOULD be included on payment proof
  submissions to provide a signed timestamp; verifiers SHOULD reject
  signatures with `created` values outside an acceptable clock-skew window.
- Keyid resolution MUST follow an out-of-band discipline agreed between
  AP2 participants; the `keyid` parameter does not itself constitute
  proof of identity without that discipline.
- Content-Digest verification MUST precede signature acceptance; a
  signature over a body whose Content-Digest does not match the actual
  body MUST be rejected regardless of signature validity.
