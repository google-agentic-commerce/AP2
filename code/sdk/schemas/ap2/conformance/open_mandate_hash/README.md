# AP2 `open_mandate_hash` Conformance Vectors — v0

Conformance vectors for the `open_mandate_hash` derivation rule for
`open_checkout_mandate.json`. Any AP2 implementation that derives
`open_mandate_hash` MUST reproduce these vectors byte-for-byte.

## Derivation rule

```text
open_mandate_hash = SHA-256(JCS_RFC8785(unsigned_open_checkout_mandate_body))
```

**Lowercase hex output.**

The hash input is the mandate **claims object**, not the JWS compact form.
Re-encoding the JWS envelope MUST NOT change `open_mandate_hash`.

## Vectors

`vectors-v0.json` — 12 vectors anchored to
`code/sdk/schemas/ap2/open_checkout_mandate.json` at schema commit
`e3d9cafa7311d90612c7f908ae9b8821ddc8735a`.

Each vector is structured as:

```json
{
  "vector_id": "ap2-omh-v0-<name>",
  "mandate_body": { ... },
  "jws_compact": "<optional: JWS compact serialization carrying the claims>",
  "expected_jcs_bytes_b64": "<standard base64 of RFC 8785 canonical bytes>",
  "expected_open_mandate_hash": "sha256:<lowercase-hex>",
  "expectation": "reference | same_hash_as:<id> | different_hash_from:<id>"
}
```

| Vector | Pair invariant | Tests |
| --- | --- | --- |
| `ap2-omh-v0-baseline-001` | reference | Canonical baseline |
| `ap2-omh-v0-object-key-order-002` | `same_hash_as:ap2-omh-v0-baseline-001` | JCS sorts object members |
| `ap2-omh-v0-array-order-003` | `different_hash_from:ap2-omh-v0-baseline-001` | Arrays are order-significant |
| `ap2-omh-v0-optional-fields-004` | `different_hash_from:ap2-omh-v0-baseline-001` | Presence ≠ absence |
| `ap2-omh-v0-currency-minor-unit-005` | canonical form | Integer minor units only |
| `ap2-omh-v0-unicode-nfc-006a` | `different_hash_from:ap2-omh-v0-unicode-nfd-006b` | No Unicode normalization |
| `ap2-omh-v0-unicode-nfd-006b` | `different_hash_from:ap2-omh-v0-unicode-nfc-006a` | No Unicode normalization |
| `ap2-omh-v0-jws-envelope-canonical-007a` | `same_hash_as:ap2-omh-v0-jws-envelope-reencoded-007b` | Hash input is the claims object, not the JWS |
| `ap2-omh-v0-jws-envelope-reencoded-007b` | `same_hash_as:ap2-omh-v0-baseline-001` | JWS re-encoding never changes the hash |
| `ap2-omh-v0-control-chars-008` | canonical form | JCS string escaping (sec 3.2.2.2) |
| `ap2-omh-v0-non-bmp-009` | canonical form | Non-BMP code points as literal UTF-8 |
| `ap2-omh-v0-integer-boundary-010` | canonical form | Integer exactness bound (2^53 - 1) |

The array-order and Unicode pairs catch the divergences most commonly seen
in practice: implementations that sort arrays or NFC-normalize strings will
fail the corresponding pair invariant immediately.

The 007 pair exercises the headline rule directly. Both vectors carry the
same claims object inside two byte-for-byte different JWS envelopes
(different protected headers, canonical vs non-canonical payload encoding,
different signatures) and MUST produce the same `open_mandate_hash` as the
baseline. Runners base64url-decode the `jws_compact` payload, parse it,
re-canonicalize, and require the same hash as from `mandate_body`. The
envelope signatures are real Ed25519 signatures under the RFC 8037
appendix A.1 test key (whose public half is the `cnf.jwk` used throughout
these vectors); runners do not verify signatures.

## Reproduce locally

Three runner scripts are included. Each reads `vectors-v0.json` and verifies
all 12 vectors and 5 pair invariants independently, including the JWS
payload re-derivation for the 007 envelope pair:

| Runner | Language | Library |
| --- | --- | --- |
| `runner_python.py` | Python | `rfc8785@0.1.4` (Trail of Bits) |
| `runner_node.js` | JavaScript | `canonicalize@3.0.0` (Erdtman + Rundgren) |
| `runner_go.go` | Go | `gowebpki/jcs v1.0.1` |

```bash
# Python
pip install rfc8785==0.1.4
python runner_python.py vectors-v0.json

# Node.js
npm install canonicalize@3.0.0
node runner_node.js vectors-v0.json

# Go
go run runner_go.go vectors-v0.json

```

## Cross-implementation validation

All 6 independent implementations produce byte-identical results for the
original 7 vectors (001 through 006b) and their 4 pair invariants. Five
different authors, four author sets, independently attested.

| Implementation | Language | Library | Vectors | Pair invariants |
| --- | --- | --- | --- | --- |
| `rfc8785@0.1.4` | Python | Trail of Bits | 7/7 ✓ | 4/4 ✓ |
| `canonicalize@3.0.0` | JavaScript | Erdtman + Rundgren (RFC 8785 author) | 7/7 ✓ | 4/4 ✓ |
| `gowebpki/jcs v1.0.1` | Go | @amavashev (AP2 maintainer) | 7/7 ✓ | 4/4 ✓ |
| `cyberphone/json-canonicalization` | Java | Rundgren (RFC 8785 reference impl) | 7/7 ✓ | 4/4 ✓ |
| `serde_jcs 0.2.0` | Rust | @seritalien / Vauban | 7/7 ✓ | 4/4 ✓ |
| `rfc8785` (corrected) | Python | Crest Systems (@andysalvo) | 7/7 ✓ | 4/4 ✓ |

Full validation history: [AP2 issue #265](https://github.com/google-agentic-commerce/AP2/issues/265)

Vectors 007a through 010 were added later (JWS envelope invariance and
edge coverage) and are verified by the three in-tree runners above;
independent attestations for the additions are welcome on issue #265.

## Known implementation hazards

- **Hashing the JWS instead of the claims** — Do not hash the JWS compact
  string or the raw payload bytes. The hash input is the parsed claims
  object after RFC 8785 canonicalization; any JWS re-encoding (new header,
  new payload serialization, new signature) leaves `open_mandate_hash`
  unchanged. The 007a/007b pair catches this.

- **`json.dumps()` non-ASCII escaping** — Python's `json.dumps()` escapes
  non-ASCII characters as `\uXXXX`. RFC 8785 requires literal UTF-8 bytes
  for printable codepoints above U+007F, including non-BMP code points
  (no surrogate-pair escapes). Use the `rfc8785` library instead.
  This will cause failures on vectors 006a, 006b and 009.

- **Control-character escaping** — RFC 8785 sec 3.2.2.2 mandates the
  two-character escapes (`\b \f \n \r \t \" \\`) and lowercase `\u00xx`
  for the remaining characters below U+0020. Emitting a `\u000a`-style
  escape for line feed, or uppercase hex like `\u001F`, diverges.
  Vector 008 catches this.

- **Integers beyond 2^53 - 1** — RFC 8785 number serialization follows
  ES6: integer values are exact only through 2^53 - 1. AP2 integer claims
  MUST stay within that bound. Vector 010 pins the boundary.

- **Array sorting** — Do not sort arrays before hashing. JCS preserves
  array element order. Vector 003 catches this.

- **Unicode normalization** — Do not NFC-normalize strings before hashing.
  RFC 8785 makes no Unicode normalization. Vectors 006a/006b catch this.

- **Float/decimal prices** — `item.price` and `amount.amount` are integers
  in the currency minor unit. `10.50` MUST be encoded as `1050`. Vector
  005 catches this.
