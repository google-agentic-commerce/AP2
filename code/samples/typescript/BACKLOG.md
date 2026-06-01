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
- [ ] Add a deterministic cross-role integration test: `assembleAndSignMandates` → `create_checkout` → `createMandateFulfillment` → `verifyCheckoutChain` + `verifyPaymentChainAndConstraints`, all via the file contract, asserting a valid end-to-end purchase and an over-budget rejection. No Gemini.

## Robustness
- [ ] Pin `expectedL3*Aud` / `expectedL3*Nonce` (and `expectedL2*`) in the role `verifyChain` calls (currently optional) so a presentation for a different audience/transaction is rejected; add tests proving it.
- [ ] `verifyPaymentChainAndConstraints`: surface a clear error when the issuer key is missing, and test it.

## Docs
- [ ] Add `src/common/vi/README.md` documenting the L1→L2→L3 flow (diagram, field reference, who-stores-what), matching the integration.
