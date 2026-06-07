# Verifiable Intent TS integration — improvement backlog

`improve-loop.sh` works ONE unchecked item at a time. Keep items small and
independently verifiable (`npx tsc --noEmit` + `npm run lint` +
`npx vitest run test/unit` all green). Check items off (`- [x]`) when done.

## Test coverage & hardening
- [ ] Enable coverage: `npm i -D @vitest/coverage-v8` (not yet installed); add a unit-only `"test:coverage:unit": "vitest run test/unit --coverage"` script (the existing `test:coverage` also runs e2e) + a coverage block in `vitest.config.ts`; report coverage for `src/common/vi`.
- [ ] Strengthen `src/common/vi` negative-path tests (see `test/unit/vi-chain-negative.test.ts`): add a tampered-L2 case (mutate a disclosed claim → chain invalid) and a kid-mismatch case (L3 signed by a key whose kid ≠ L2 `cnf.kid` → invalid).
- [ ] Add immediate-flow rejection tests: bad issuer signature, and an L2 whose `sd_hash` does not match L1 → `verifyChain` invalid.
- [ ] Constraint-checker edge cases: amount exactly at the cap (allowed), one cent over (rejected), currency mismatch, empty `acceptable_items` (wildcard).

## Make the MCP role logic testable without servers
- [ ] Extract the pure logic of merchant-agent-mcp `complete_checkout`, credentials-provider-mcp `issue_payment_credential`, and merchant `create_checkout` into small exported functions (no `McpServer`/stdio), and unit-test their happy + error paths against the persisted-file contract in a temp `TEMP_DB`.
- [x] Add a deterministic cross-role integration test via the persisted-file contract (`test/unit/vi-integration.test.ts`): agent writes `l1/l2/chk_*/pay_*` to a temp dir, merchant + network read them back and verify with aud pinning; asserts a valid purchase and an over-budget rejection. No Gemini/servers. (Tool-level tests of the actual `*.execute` handlers are still worth adding — see item above.)
- [ ] **Gap (flow):** the merchant MCP serves generated slug item ids (`<slug>_0` from `generateInventoryEntry`), but the L2 `acceptable_items` default to the VI catalog skus (BAB86345). If consent signs L2 before `search_inventory` supplies the merchant item id, `createAgentFulfillment` can't match the item disclosure and throws. Fix: have the merchant serve the VI catalog (sku ids), or require consent to thread the merchant `item_id` into the mandate.

## Robustness
- [x] Pin `expectedL3*Aud` in the role `verifyChain` calls so a presentation addressed to a different party is rejected — merchant pins `MERCHANT_AUD`, CP pins `NETWORK_AUD`, agent stamps both via shared fixtures constants. Test in `test/unit/vi-chain-negative.test.ts`.
- [ ] Replay protection: verifiers don't pin nonce/`transaction_id`, and used payment tokens / mandates aren't deduped — the same authorization could be replayed. Track spent nonces/tokens across the role servers (the VI lib leaves replay to the caller) + add a test.
- [ ] **Gap (binding):** credentials-provider mints `pay_token_*` after verifying the payment chain, but the token isn't cryptographically bound to `checkout_jwt_hash`, and `complete_checkout` / the PSP don't re-verify the chain — a minted token could be presented for a different settlement. Bind the token to the checkout hash (and/or have the PSP re-verify) + add a test.
- [ ] `verifyPaymentChainAndConstraints`: surface a clear error when the issuer key is missing, and test it.

## Docs
- [ ] Add `src/common/vi/README.md` documenting the L1→L2→L3 flow (diagram, field reference, who-stores-what), matching the integration.
