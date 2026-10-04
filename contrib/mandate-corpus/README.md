# AP2 Mandate Conformance Corpus

Signed AP2 mandate fixtures for validating independent implementations, plus a
reproducer for a defect found in the AP2 Python SDK.

Validated 2026-10-04 against `google-agentic-commerce/AP2` at that HEAD.

---

## 1 · The gap this closes

There is **no** `fixture`, `corpus`, `vector` or `conformance` directory
anywhere in `google-agentic-commerce/AP2`:

```console
find . -type d \( -name "*fixture*" -o -name "*corpus*" -o -name "*vector*" \
                    -o -name "*conformance*" \)
→ (empty)
```python

The Python SDK can sign mandates (`sd_jwt.create`, `kb_sd_jwt.create`), but
nobody publishes signed fixtures.

That is why the positive test in `Universal-Commerce-Protocol/conformance` has
to be skipped. From PR #115:

> "A real positive needs a signed SD-JWT+kb mandate fixture and a signing
> model, which this PR does not attempt."

**Who needs it:** AP2 implementations in **other languages** — the Go sample
(`code/samples/go`), TypeScript, and PHP
(`agentic-commerce-alliance/ucp-php-sdk`). They need a byte-level reference to
conform against, not somebody else's test code.

### Why this is a blocker, not a nicety

Measured across the AP2 ecosystem on 2026-10-04:

| language | lines | signing/verification crypto | mandate support |
|---|---|---|---|
| **Python** (this repo) | 8 863 | 20 modules | works |
| **Go** (`code/samples/go`) | 2 258 | **0** | none — `FakeJWT` |
| **PHP** (`ucp-php-sdk`) | 39 194 | present | PR #90, **unmerged since 2026-07-15** |

The Go sample hardcodes a token:

```python
code/samples/go/pkg/roles/merchant_agent/tools.go:31
FakeJWT = "eyJhbGciOiJSUz1NiIsImtpZIwMjQwOTA..."
```bash

There are **zero** files in the Go sample that perform real signing or
verification.

The consequence: **Python is currently the only language that can verify an
AP2 mandate.** Any other implementation has nothing to test against — it cannot
produce a valid mandate and cannot check one. Signed fixtures are the only
thing that unblocks them, which is what this corpus provides.

---

## 2 · Contents

```text
tools/generate_fixtures.py    signed fixture generator
tools/verify_fixtures.py      reference verifier (portable to other languages)
tools/negative_vectors.py     negative vectors + positive control
tools/poc_aud_not_enforced.py reproducer for the defect in §3
vectors/*.json                3 signed vectors + index.json
```text

### Vectors

| id | what it pins down |
|----|-------------------|
| `open-payment-mandate-card-basic` | baseline mandate, 100 USD, `cnf` = agent key |
| `open-payment-mandate-debit-large` | amount boundaries (50 000 minor units) |
| `open-payment-mandate-nonusd` | **non-USD (BRL)** — catches implementations that silently normalise everything to dollars |

---

## 3 · Defect found: `expected_aud` is not enforced

**Impact:** audience (recipient) check bypass. **Severity:** medium.

`verify_chain` documents:

> "index i (KB-SD-JWT): verified with the previous hop's `cnf.jwk` via
> `kb_sd_jwt.verify`, **enforcing `expected_aud` / `expected_nonce` on the
> terminal hop when provided**"

But `kb_sd_jwt.verify` only calls `common.verify_expected_claims` when
`typ in TYP_TERMINAL`:

```python
TYP_TERMINAL     = ['kb+sd-jwt',    'kb-sd-jwt']
TYP_INTERMEDIATE = ['kb+sd-jwt+kb', 'kb-sd-jwt+kb']
```text

A token whose `typ` is `kb+sd-jwt+kb` — which the SDK itself produces whenever
the payload carries a `cnf` claim — lands in `TYP_INTERMEDIATE`. The
`aud`/`nonce` check therefore **never runs**, even though the caller explicitly
passed `expected_aud`. There is no warning.

### Reproduction

```bash
.venv/bin/python tools/poc_aud_not_enforced.py
```text

```text
  hop type      : kb+sd-jwt+kb (per TYP_INTERMEDIATE)
  aud in token  : https://attacker.example/ap2
  expected_aud  : https://honest-merchant.example/ap2
  audiences do NOT match — a correct verifier must reject

  ACCEPTED a token with the wrong audience.

  VERDICT: DEFECT CONFIRMED
```text

### Consequence

A merchant relying on the audience check receives silent protection that does
not exist. Substituting `aud` passes without refusal.

### Suggested fix

In this repository (not in the PR): evaluate `expected_aud`/`expected_nonce`
against the **last** token in the chain regardless of `typ`, or widen
`TYP_TERMINAL`, or raise when `expected_aud` is supplied but the hop type is
not terminal.

I did not include a patch for this, because changing verification semantics is
a maintainer decision, not something to land alongside a fixtures PR. The
reproducer is self-contained and can be run against any revision.

---

## 4 · Self-verifying in CI

`.github/workflows/mandate-corpus.yml` runs the vectors on every PR that
touches `code/sdk/python/**` or this directory.

The point is regression detection: if a change to mandate verification silently
breaks signature checking or the `cnf` binding, the same PR goes red instead of
a customer discovering it later.

The `poc_aud_not_enforced.py` step is `continue-on-error: true` while the §3
defect is open. Remove that flag once it is fixed — the reproducer will turn
green on its own.

## 5 · An AP2 subtlety that is easy to miss

The root SD-JWT **must** carry a `cnf` naming the agent key **before** the
human signs the authorisation. Otherwise the human authorises a spending
authority nobody can ever use. The same class of defect is described
independently in `openmobilehub/credentagent` PR #189:

> "the human signed over a key that was then discarded and replaced at
> authorization: **they authorized a spending authority nobody would ever use**"

The generator handles this explicitly with `sd=DisclosureMetadata(sd_keys=[])`.
Without it, `DisclosureMetadata.from_model` hides the entire payload under
`_sd`, `cnf` becomes unreadable, and the mandate is signed but unenforceable.

---

## 6 · Usage

Run from the repository root. The SDK is this same repository, so no
separate checkout is needed:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .   # pyproject.toml is at the repository root

.venv/bin/python contrib/mandate-corpus/tools/generate_fixtures.py    # → vectors/
.venv/bin/python contrib/mandate-corpus/tools/verify_fixtures.py      # 3/3 OK
.venv/bin/python contrib/mandate-corpus/tools/negative_vectors.py     # 2 rejections, 1 xfail (§3)
.venv/bin/python contrib/mandate-corpus/tools/poc_aud_not_enforced.py # reproducer
```text

The scripts resolve `vectors/` relative to their own location, so they can
also be copied out of the repository standalone.

Expected `verify_fixtures.py` output:

```text
  OK    open-payment-mandate-card-basic.json — chain valid, cnf=agent key, amount matches reference
  OK    open-payment-mandate-debit-large.json — chain valid, cnf=agent key, amount matches reference
  OK    open-payment-mandate-nonusd.json — chain valid, cnf=agent key, amount matches reference
```text

---

## 7 · Scope and limits

- Vectors are validated **only** by the reference Python verifier from the same
  SDK. Cross-validation against an independent implementation in another
  language is the point of the proposal, not work already completed.
- Fixtures embed **test** keys. They are a conformance reference, not a
  security mechanism.
- The §3 defect is accurate for the AP2 HEAD of 2026-10-04. Re-check before
  merging; the reproducer runs against any revision.
- The negative vectors currently prove two things: signature tampering is
  caught, and a good chain is accepted. The `aud` case is `xfail` by design so
  that fixing §3 turns it green rather than silently disappearing.

---

## Licence

Apache-2.0, matching the parent repository. Independent work, no affiliation
with Google LLC.
