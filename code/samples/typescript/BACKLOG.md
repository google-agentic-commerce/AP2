# Verifiable Intent TS integration — improvement backlog

`improve-loop.sh` works ONE unchecked item at a time. Keep items small and
independently verifiable (`npx tsc --noEmit` + `npm run lint` +
`npx vitest run test/unit` all green). Check items off (`- [x]`) when done.

## Test coverage & hardening
- [x] Enable coverage: `@vitest/coverage-v8` + `test:coverage:unit` script + a coverage block in `vitest.config.ts` (scoped to `src/common/vi`). Baseline: **85.7% stmts / 82.5% branch / 73.9% funcs / 85.6% lines**.
- [x] **Coverage gap closed:** `keys.ts` now **100%** — round-trip persist/reload, per-role kids + fallback, legacy (no-kid) format, `loadViPublicJwk` missing→null + no private-scalar leak, and a persisted key signing a verifiable credential (`test/unit/vi-keys.test.ts`). Overall `src/common/vi` now **96.2% stmts / 91.3% funcs**. (`fixtures.ts` `getCatalog` still uncovered — minor.)
- [ ] Strengthen `src/common/vi` negative-path tests (see `test/unit/vi-chain-negative.test.ts`): add a tampered-L2 case (mutate a disclosed claim → chain invalid) and a kid-mismatch case (L3 signed by a key whose kid ≠ L2 `cnf.kid` → invalid).
- [x] Add immediate-flow rejection tests: wrong issuer key, and an L2 whose `sd_hash` does not match L1 (verified against a different L1) → `verifyChain` invalid. In `test/unit/vi-chain-negative.test.ts`.
- [x] Constraint amount/currency boundaries: at-cap allowed, +1 minor unit rejected, currency mismatch rejected (`test/unit/vi-constraints.test.ts`). (Empty `acceptable_items` line-items wildcard still untested — minor.)

## Make the MCP role logic testable without servers
- [ ] Extract the pure logic of merchant-agent-mcp `complete_checkout`, credentials-provider-mcp `issue_payment_credential`, and merchant `create_checkout` into small exported functions (no `McpServer`/stdio), and unit-test their happy + error paths against the persisted-file contract in a temp `TEMP_DB`.
- [x] Add a deterministic cross-role integration test via the persisted-file contract (`test/unit/vi-integration.test.ts`): agent writes `l1/l2/chk_*/pay_*` to a temp dir, merchant + network read them back and verify with aud pinning; asserts a valid purchase and an over-budget rejection. No Gemini/servers. (Tool-level tests of the actual `*.execute` handlers are still worth adding — see item above.)
- [~] **Gap (flow):** merchant MCP serves generated slug item ids (`<slug>_0`) but L2 `acceptable_items` defaulted to VI skus, so `createAgentFulfillment` couldn't match the item. **Mitigated (iter 7):** consent prompt now calls `search_inventory` FIRST and threads the resolved `item_id` into `assembleAndSignMandates` (REQUIRED), so L2 binds the exact merchant item. Prompt audit also confirmed all v2 prompts match the current tool signatures. **Still needs e2e validation** (prompt behavior isn't unit-verifiable); a `merchant-serves-VI-catalog` alternative remains an option.

## Robustness
- [x] Pin `expectedL3*Aud` in the role `verifyChain` calls so a presentation addressed to a different party is rejected — merchant pins `MERCHANT_AUD`, CP pins `NETWORK_AUD`, agent stamps both via shared fixtures constants. Test in `test/unit/vi-chain-negative.test.ts`.
- [ ] Replay protection: verifiers don't pin nonce/`transaction_id`, and used payment tokens / mandates aren't deduped — the same authorization could be replayed. Track spent nonces/tokens across the role servers (the VI lib leaves replay to the caller) + add a test.
- [ ] **Gap (binding):** credentials-provider mints `pay_token_*` after verifying the payment chain, but the token isn't cryptographically bound to `checkout_jwt_hash`, and `complete_checkout` / the PSP don't re-verify the chain — a minted token could be presented for a different settlement. Bind the token to the checkout hash (and/or have the PSP re-verify) + add a test.
- [ ] `verifyPaymentChainAndConstraints`: surface a clear error when the issuer key is missing, and test it.

## Docs
- [ ] Add `src/common/vi/README.md` documenting the L1→L2→L3 flow (diagram, field reference, who-stores-what), matching the integration.
