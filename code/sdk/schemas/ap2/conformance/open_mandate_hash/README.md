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

`vectors-v0.json` — 7 vectors anchored to
`code/sdk/schemas/ap2/open_checkout_mandate.json` at schema commit
`e3d9cafa7311d90612c7f908ae9b8821ddc8735a`.

Each vector is structured as:

```json
{
  "vector_id": "ap2-omh-v0-<name>",
  "mandate_body": { ... },
  "expected_jcs_bytes_b64": "<base64 of RFC 8785 canonical bytes>",
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

The array-order and Unicode pairs catch the divergences most commonly seen
in practice: implementations that sort arrays or NFC-normalize strings will
fail the corresponding pair invariant immediately.

## Reproduce locally

Four runner scripts are included. Each reads `vectors-v0.json` and verifies
all 7 vectors and 4 pair invariants independently:

| Runner | Language | Library |
| --- | --- | --- |
| `runner_python.py` | Python | `rfc8785@0.1.4` (Trail of Bits) |
| `runner_node.js` | JavaScript | `canonicalize@3.0.0` (Erdtman + Rundgren) |
| `runner_go.go` | Go | `gowebpki/jcs v1.0.1` |
| `JcsRunner.java` | Java | `cyberphone/json-canonicalization` (RFC 8785 reference impl) |

```bash
# Python
pip install rfc8785==0.1.4
python runner_python.py vectors-v0.json

# Node.js
npm install canonicalize@3.0.0
node runner_node.js vectors-v0.json

# Go
go run runner_go.go vectors-v0.json

# Java
javac JcsRunner.java && java JcsRunner vectors-v0.json
```

## Cross-implementation validation

All 6 independent implementations produce byte-identical results for all 7 vectors
and all 4 pair invariants. Five different authors, four author sets, independently
attested.

| Implementation | Language | Library | Vectors | Pair invariants |
| --- | --- | --- | --- | --- |
| `rfc8785@0.1.4` | Python | Trail of Bits | 7/7 ✓ | 4/4 ✓ |
| `canonicalize@3.0.0` | JavaScript | Erdtman + Rundgren (RFC 8785 author) | 7/7 ✓ | 4/4 ✓ |
| `gowebpki/jcs v1.0.1` | Go | @amavashev (AP2 maintainer) | 7/7 ✓ | 4/4 ✓ |
| `cyberphone/json-canonicalization` | Java | Rundgren (RFC 8785 reference impl) | 7/7 ✓ | 4/4 ✓ |
| `serde_jcs 0.2.0` | Rust | @seritalien / Vauban | 7/7 ✓ | 4/4 ✓ |
| `rfc8785` (corrected) | Python | Crest Systems (@andysalvo) | 7/7 ✓ | 4/4 ✓ |

Full validation history: [AP2 issue #265](https://github.com/google-agentic-commerce/AP2/issues/265)

## Known implementation hazards

- **`json.dumps()` non-ASCII escaping** — Python's `json.dumps()` escapes
  non-ASCII characters as `\uXXXX`. RFC 8785 requires literal UTF-8 bytes
  for printable codepoints above U+007F. Use the `rfc8785` library instead.
  This will cause failures on vectors 006a and 006b.

- **Array sorting** — Do not sort arrays before hashing. JCS preserves
  array element order. Vector 003 catches this.

- **Unicode normalization** — Do not NFC-normalize strings before hashing.
  RFC 8785 makes no Unicode normalization. Vectors 006a/006b catch this.

- **Float/decimal prices** — `item.price` and `amount.amount` are integers
  in the currency minor unit. `10.50` MUST be encoded as `1050`. Vector
  005 catches this.
