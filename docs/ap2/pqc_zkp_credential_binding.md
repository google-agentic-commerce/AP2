# AP2 — PQC credential binding + ZKP receipt in production

**Repo:** google-agentic-commerce/AP2
**Related open PRs:** #270 (lifecycle), #271 (settlement), #272 (trust query), #273 (RFC 9421), #274 (PEF)
**Type:** Production deployment notice

---

## Production status

AlgoVoi's AP2 `POST /ap2/confirm` is **live in production** with ZKP-bound payment evidence and full agent session spend tracking as of 2026-06-04.

---

## New response headers on `POST /ap2/confirm` (Phase 2 ATB sessions only)

```http
HTTP/1.1 200 OK
X-ZKP-Receipt-Payload: <base64url unsigned ZKP receipt>
X-Composite-Trust-Verdict: TRUSTED

{"verified": true, "access_token": "...", "settlement_attestation": {"settlement_result": "SETTLED", ...}}
```

Additionally: **agent session spend cap is now wired** to `/ap2/confirm` — payments made via session JWT decrement the cap; exceeded cap returns `402 agent_spend_cap_exceeded`.

Both headers are **only present for Phase 2 ATB sessions**. All existing AP2 flows are unaffected.

---

## Agent credential flow for AP2

AP2 is a mandate-based protocol. The ZKP credential binds at the `/ap2/confirm` step, after the `CartMandate` and `PaymentMandate` have been accepted:

```text
1. Agent → POST /auth/token
   Headers: X-Tenant-Id, Authorization: Bearer <api_key>
   Body: { "atb_zk_credential": "<Falcon-1024 Phase 2 cert>", "spend_cap_usd": 100.0 }
   ← session JWT issued; ZKP commitment + proof bound to session; spend cap initialized

2. Agent → POST /ap2/intent   (IntentMandate)
   Authorization: Bearer <session_token>

3. Agent → POST /ap2/cart     (CartMandate, merchant-signed)
   Authorization: Bearer <session_token>

4. Agent → POST /ap2/pay      (initiate on-chain payment)
   Authorization: Bearer <session_token>

5. Agent → POST /ap2/confirm
   Authorization: Bearer <session_token>
   Body: { "tx_id": "...", "network": "...", "payment_id": "..." }
   ← 200 OK with X-ZKP-Receipt-Payload + X-Composite-Trust-Verdict
      Spend cap decremented by confirmed payment amount
```

The session token is valid across the full AP2 lifecycle. Once `spend_cap_usd` is exhausted, further payments return `402 agent_spend_cap_exceeded`.

---

## Composite trust verdict

The `X-Composite-Trust-Verdict` header composes the AP2 settlement attestation with the ZKP receipt at confirmation time. Independently reproducible:

```http
POST https://api.algovoi.co.uk/compliance/trust-query
Content-Type: application/json

{
  "receipts": [
    {
      "settlement_result": "SETTLED",
      "settlement_provider_did": "did:web:api.algovoi.co.uk"
    },
    {
      "type": "zkp_receipt",
      "threshold_met": true,
      "bench_issuer": "did:web:agent-trust-bench.algovoi.co.uk"
    }
  ]
}
```

```json
{
  "trust_outcome": "TRUSTED",
  "composite_hash": "36042eb288b6557aed801ed9a2fe6e077b31bd7261a4dffbe8107ef078867f10",
  "receipt_count": 2
}
```

Possible verdicts: `TRUSTED` · `PROVISIONAL` (`PENDING_FINALITY`) · `INSUFFICIENT_EVIDENCE` · `UNTRUSTED`.
Specified in [`draft-hopley-x402-composite-trust-query`](https://datatracker.ietf.org/doc/draft-hopley-x402-composite-trust-query/) — open PR #272.

---

## Validation stages

### Stage 1 — Specification

| Reference | Subject |
| --- | --- |
| [`draft-hopley-x402-pqc-credential-binding-00`](https://datatracker.ietf.org/doc/draft-hopley-x402-pqc-credential-binding/) | Falcon-1024 / ML-DSA-65 (NIST FIPS 204/206) credential binding to AP2 payment authorization — under editor review |
| [`draft-hopley-x402-federation-zkp-00`](https://datatracker.ietf.org/doc/draft-hopley-x402-federation-zkp/) | Cross-issuer ZKP composition; composite commitment: `SHA-256(domain ‖ comm_0 ‖ … ‖ nonce)` — under editor review |
| [`draft-hopley-x402-composite-trust-query`](https://datatracker.ietf.org/doc/draft-hopley-x402-composite-trust-query/) | Composite trust verdict — open PR #272 |
| [IACR ePrint 2026/109852](https://eprint.iacr.org/2026/109852) | *"Agent Trust Bench: Adversarial Payment Profiling for Autonomous Agents with Post-Quantum Credential Binding and Cross-Issuer Federation"* — under IACR editor review |

### Stage 2 — Implementation

Production deployment to `api.algovoi.co.uk` as of 2026-06-04:

- `algovoi-federation-validator` v0.1.1 — 59/59 tests pass
- `algovoi-zkp-receipt` v0.1.0 — 13/13 tests pass
- Gateway agent auth + ZKP receipt pipeline — 75/75 tests pass
- ATB ZKP service (Rust / Bulletproofs / Ristretto255) — live
- AP2 spend cap wiring — now complete (was missing; fixed 2026-06-04)

### Stage 3 — Cross-language conformance

`zkp_receipt_v1` payload canonicalization validated byte-for-byte across 8 independent JCS implementations:

| Language | Result |
| --- | --- |
| Python `rfc8785 0.1.4` | **8/8 PASS** |
| Node.js `canonicalize 3.0.0` | **8/8 PASS** |
| Ruby `json-canonicalization 1.0.0` | **8/8 PASS** |
| PHP `root23/php-json-canonicalization 1.0.1` | **8/8 PASS** |
| Go `gowebpki/jcs v1.0.1` | **8/8 PASS** |
| Rust / Java / .NET | By transitivity — 320/320 prior attestation |

Attestation: [`2026-06-04-zkp-receipt-v1-cross-validation.md`](https://github.com/chopmob-cloud/algovoi-jcs-conformance-vectors/blob/main/_attestations/2026-06-04-zkp-receipt-v1-cross-validation.md)
Cumulative: **664/664** byte-for-byte agreements across 9 vector sets, 8 JCS implementations.

### Stage 4 — Live production smoke

- 13/13 service checks pass
- All four CTQ verdicts verified live
- ATB bench score: 128/138 (92.8%)
- 7 chains: Algorand, VOI, Hedera, Stellar, Base, Solana, Tempo

---

## Licensing — these packages are not open source

Three deployment paths are available:

**1. Hosted commercial application**
Use `api.algovoi.co.uk` directly — the full PQC/ZKP/Federation stack is live under the standard AlgoVoi 0.50% transaction fee. No additional license required. All response headers are available to session-authenticated tenants.

**2. Commercial Docker instances**
Run `algovoi-federation-validator` and `algovoi-zkp-receipt` as Docker containers on your own infrastructure under the **AlgoVoi Commercial License v1.0**. Production-grade Docker images are available to license holders. Evaluation use (non-commercial, non-production) is free.

**3. Enterprise / OEM / acquisition**
Custom on-premises deployments, white-label integrations, and acquisition enquiries. Contact [hello@algovoi.co.uk](mailto:hello@algovoi.co.uk).

---

The **self-hosted implementation packages are proprietary and will not be open-sourced under any circumstances**:

| Package | License |
| --- | --- |
| `algovoi-federation-validator` | **AlgoVoi Commercial License v1.0 — not open source** |
| `algovoi-zkp-receipt` | **AlgoVoi Commercial License v1.0 — not open source** |

There is no Apache, MIT, or community-license path for these packages. Production deployment, revenue-generating use, or managed-service operation requires a written Commercial License Agreement. Contact [hello@algovoi.co.uk](mailto:hello@algovoi.co.uk).

All 31 AlgoVoi substrate packages remain Apache 2.0.

---

*AlgoVoi (chopmob-cloud) -- [docs.algovoi.co.uk/pqc-substrate](https://docs.algovoi.co.uk/pqc-substrate)*
