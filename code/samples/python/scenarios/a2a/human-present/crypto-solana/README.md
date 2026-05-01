<!-- cspell:words Hedera Solflare keypair mainnet devnet ALGOVOI algv Helius Backpack Triton Phantom -->

# Agent Payments Protocol Sample: Human Present Purchases with On-Chain Solana USDC

This sample demonstrates the A2A `ap2-extension` for a human-present transaction
where the buyer settles with on-chain USDC on Solana (or native SOL for
micropayments). It mirrors the existing `x402` scenario but uses Solana Pay
semantics — specifically the **`reference` pubkey** primitive — to bind the
settling transaction to a specific AP2 `PaymentMandate`.

**Note:** This sample pairs with the separate `crypto-algo` human-present
scenario. Together they cover non-EVM settlement on Algorand and Solana as a
complement to the EVM-focused `x402` path.

## Scenario

Human-present flows are commerce flows where the user is present to confirm
purchase details. The user signs the `PaymentMandate` giving all parties high
confidence in the transaction.

The Solana variant adds one additional primitive on top of the standard AP2
mandate chain:

### Solana Pay `reference` binding

Solana has no native transaction memo field (unlike Algorand or Hedera), and
the SPL Memo Program is unreliable across wallets. Instead, Solana Pay defines
a `reference` pubkey mechanism:

1. The merchant (or its Merchant Agent) generates a fresh, single-use ed25519
   keypair per checkout.
2. The public key is embedded in the Solana Pay URL:

   ```text
   solana:<recipient>
     ?amount=<amount>
     &spl-token=<USDC_MINT>
     &reference=<reference_pubkey>
     &label=<label>
     &message=<order-id>
   ```

3. The buyer's wallet (Phantom, Solflare, Backpack, etc.) includes the
   `reference` pubkey as a read-only, non-signer account in the transfer
   instruction.
4. After the user signs and broadcasts the SPL Token transfer, the merchant
   (or facilitator) queries `getSignaturesForAddress(<reference>)` to locate
   the exact transaction that settled this order.
5. Final verification compares the on-chain transfer's recipient, amount, and
   SPL mint against the AP2 `PaymentMandate` contents. All three must match.

This is stronger than relying on amount uniqueness (EVM-style) and more
wallet-compatible than relying on memos. It also means the merchant never has
to ask the buyer to paste a transaction signature back.

## Key Actors

This sample consists of:

- **Shopping Agent:** The main orchestrator that handles the user's shopping
  request and delegates to specialist agents.
- **Merchant Agent:** Handles product queries and assembles the `CartMandate`.
- **Merchant Payment Processor Agent:** Takes payments on behalf of the
  merchant and, in the Solana flow, verifies the on-chain USDC transfer
  against the expected `reference`, amount, and mint.
- **Credentials Provider Agent:** Holds the user's payment credentials — in
  this flow, the Solana wallet address and optional mint preferences.

## Mandate Chain

The AP2 mandate chain is unchanged by the Solana variant:

```text
IntentMandate  ──▶  CartMandate  ──▶  PaymentMandate
     (user)              (merchant)       (user-signed)
                                                │
                                                ▼
                                 Solana Pay URL (reference-bound)
                                                │
                                                ▼
                             SPL Token Transfer + reference pubkey
                                                │
                                                ▼
                              getSignaturesForAddress(reference)
                                                │
                                                ▼
                                   PaymentReceipt
```

## Payment Method

This scenario sets `PAYMENT_METHOD=CRYPTO_SOLANA` at startup. Downstream agents
treat it as a non-card, non-x402 payment flow and route through the
Solana-aware credentials provider path.

## Assets Supported

| Asset | Mint | Decimals |
| --- | --- | --- |
| USDC (Solana mainnet) | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` | 6 |
| USDT (Solana mainnet) | `Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB` | 6 |
| USDC (Solana devnet) | `4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU` | 6 |
| Native SOL | — | 9 |

The Solana Pay URL format
(`solana:<recipient>?amount=...&spl-token=<mint>&reference=<pubkey>`) carries
the mint identifier, so supporting additional SPL tokens is a configuration
concern on the Merchant Agent and does not require protocol changes.

## Running the sample

```bash
# From the repository root:
export ALGOVOI_API_KEY="algv_..."           # or any Solana-aware facilitator
export SOLANA_RPC_URL="https://..."         # Solana mainnet or devnet RPC
export GOOGLE_API_KEY="..."                 # or GOOGLE_GENAI_USE_VERTEXAI=true
./samples/python/scenarios/a2a/human-present/crypto-solana/run.sh
```

The sample script starts the Merchant, Credentials Provider, and Merchant
Payment Processor agents locally, then launches the Shopping Agent via the ADK
web UI. You can then drive a purchase end-to-end with USDC on Solana.

## Why Solana Pay `reference` matters for AP2

AP2 mandates are already cryptographically signed, but they describe intent
and authorization — not the on-chain settlement event itself. The `reference`
pubkey is the missing link that ties a specific blockchain transaction to a
specific `PaymentMandate` deterministically, without trusting the buyer to
self-report their transaction signature. For agent-initiated commerce, where
the "buyer" may be an AI agent and the "merchant" may be another AI agent,
this mechanical binding removes an otherwise social trust layer.

## Reference implementations

- [AlgoVoi facilitator](https://api1.ilovechicken.co.uk) — verifies Solana
  USDC transfers by (a) resolving `getSignaturesForAddress(reference)`,
  (b) fetching the transaction, (c) checking mint + amount + recipient, and
  (d) confirming the `reference` pubkey appears in the transaction's
  account keys.
- [Solana Pay specification](https://solanapay.com/) — the canonical
  reference for URL format and merchant-side flow.
