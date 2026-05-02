# AP2 Sample: DID-based settlement (TDIP example)

This sample demonstrates the AP2 mandate chain (`IntentMandate` →
`CartMandate` → `PaymentMandate`) running against a **DID-based
identity layer** rather than the bearer-token / opaque-account
identities used in the other samples in this directory.

The identity layer used here is **TDIP** (Tenzro Decentralized Identity
Protocol) and the DID method is `did:tenzro:`, but the same pattern
works against any DID-based stack — `did:web`, `did:key`, `did:ion`,
`did:eth`, etc. — provided the chain exposes a delegation primitive and
a settlement-proof primitive comparable to the ones used here.

## What the sample shows

1. A **principal** (human user) with DID `did:tenzro:human:alice` issues
   an `IntentMandate` authorizing an autonomous shopping agent to spend
   up to a fixed budget on a specific category of goods.
2. The **delegate** (machine agent) with DID
   `did:tenzro:machine:shopper` accepts the intent. It has a TDIP
   `DelegationScope` (the *protocol-level* ceiling, set when the machine
   identity was registered) and a runtime `SpendingPolicy` (the
   *execution-level* ceiling, mutable, enforces a daily-spend window).
3. A **merchant** publishes a `CartMandate` whose total fits within the
   intent's `max_amount`.
4. A **`PaymentMandate`** is constructed with
   `payment_method.supported_methods = "tenzro:micropayment-channel"` —
   pointing at a Tenzro per-message billing channel rather than a card,
   stablecoin transfer, or ACH rail.
5. The sample calls `tenzro_ap2ValidateMandatePair` (with
   `enforce_delegation=true`), which exercises **all four ceilings**:

   - AP2 `IntentMandate` constraints (max_amount, allowed merchants /
     SKUs, expiry).
   - AP2 `CartMandate` consistency (total = sum of line items, parent
     intent matches, expiry).
   - TDIP `DelegationScope::enforce_operation` (max_transaction_value,
     allowed_operations, allowed_payment_protocols, allowed_chains,
     time_bound).
   - TDIP runtime `SpendingPolicy::check` (max_per_transaction,
     max_daily_spend, current_daily_spend, enabled).

6. Settlement: a Plonky3 STARK proof is generated over the `settlement`
   AIR (witness: payer balance, service proof, nonce, prev_nonce,
   amount). The proof's 32-byte SHA-256 commitment is recorded in
   Tenzro's `ZkCommitmentRegistry` so the on-chain `ZK_VERIFY`
   precompile becomes an O(1) HashSet lookup. The micropayment channel
   is settled with the resulting receipt.

7. The sample pretty-prints all three mandates and the settlement
   receipt to stdout.

## Why this fills a gap

The existing AP2 samples in this directory (`scenarios/a2a/...`)
demonstrate card and x402 payment methods using opaque user / agent
identifiers. They do **not** show what AP2 looks like when the parties'
identities are first-class DIDs with on-chain delegation enforcement
and verifiable-credential-style scope binding.

AP2's IntentMandate / CartMandate / PaymentMandate types are explicitly
identity-system-agnostic — they take the principal's, agent's, and
merchant's identifiers as opaque strings. This sample concretely shows
how those strings can be a real DID method, with the corresponding
identity-resolution and delegation-checking flow.

## Dependencies

- Python 3.11+
- [`ap2`](https://github.com/google-agentic-commerce/AP2) (the AP2
  Python SDK; install via `pip install -e code/sdk/python/ap2` from a
  checkout, or via the workspace install).
- `requests==2.32.5` — for talking to the Tenzro JSON-RPC.
- `pydantic>=2.7` — already a transitive dep of `ap2`.

The sample is **stdlib + AP2 + requests**. No `web3`, no `cryptography`
extras, no Google API key required.

See `requirements.txt` for the pinned subset.

## Live testnet — no setup required

By default the sample talks to `https://rpc.tenzro.network` (the live
Tenzro testnet). No private key, no node binary, no faucet credit is
required to run the validation flow because:

- DID resolution (`tenzro_resolveIdentity`) is a read-only RPC.
- Mandate validation (`tenzro_ap2ValidateMandatePair`) is a
  read-only RPC over caller-provided VDCs.
- ZK proof generation (`tenzro_createZkProof`) is a read-only,
  CPU-bound RPC; it produces a proof envelope but does not record it
  on-chain.

The settlement step (channel update + commitment registration) is
**simulated** in the sample with a clearly-labeled stub. Running it
against a live channel would require funded keys, which is outside the
scope of a public AP2 sample. Tenzro's CLI (`tenzro escrow ...`) is the
production path for that.

To point at a different RPC, set `TENZRO_RPC_URL`:

```sh
TENZRO_RPC_URL=https://rpc.tenzro.network python main.py
```

## How to run

From this directory:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Or via the AP2 workspace (if you've installed `ap2-samples` already):

```sh
uv run --package ap2-samples python -m tenzro_did_settlement.main
```

## Expected output

```text
=== AP2 sample: DID-based settlement (TDIP example) ===
RPC: https://rpc.tenzro.network

[1/5] Resolving principal DID         did:tenzro:human:alice ... resolved (kyc_tier=Basic)
[2/5] Resolving delegate DID          did:tenzro:machine:shopper ... resolved (controller=did:tenzro:human:alice)
[3/5] Building mandate chain
      IntentMandate                   id=…  max=50.00 USD  expires=2026-…
      CartMandate                     id=…  total=37.50 USD  items=2
      PaymentMandate                  id=…  method=tenzro:micropayment-channel

[4/5] Validating against all four ceilings
      AP2 IntentMandate constraints   OK (max_amount, expiry, merchants)
      AP2 CartMandate consistency     OK (total recompute, parent binding)
      TDIP DelegationScope            OK (37.50 USD ≤ 100.00 USD scope cap)
      TDIP SpendingPolicy             OK (37.50 USD ≤ 50.00 USD daily window)
      Tenzro RPC ap2ValidateMandatePair{enforce_delegation=true}  valid=true

[5/5] Settling via Plonky3 commitment
      circuit_id                      settlement
      proof_size                      ~80 KiB (Plonky3 STARK over KoalaBear)
      commitment (sha256)             0x…
      registry recordable             true
      simulated channel receipt       channel_id=…  payment_amount=37.50 USD

=== Done. Mandate chain validated and settlement-ready. ===
```

## Notes for reviewers

- The sample uses the AP2 SDK's `IntentMandate` / `CartMandate` /
  `PaymentMandate` Pydantic models exactly as defined in
  `code/sdk/python/ap2/models/mandate.py`. No SDK modifications.
- The DID-method-specific glue (resolution, delegation, ZK commitment)
  is isolated in `tenzro_client.py` so the structure of `main.py`
  closely mirrors a chain-agnostic AP2 mandate flow.
- The Plonky3 STARK proving call (`tenzro_createZkProof`) is the
  canonical path used by Tenzro's own settlement engine; the sample is
  not introducing a new proving system.
