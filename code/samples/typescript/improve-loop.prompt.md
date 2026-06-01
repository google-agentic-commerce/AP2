# Autonomous improve + test loop — Verifiable Intent TypeScript integration

You are running headless inside `code/samples/typescript` (the AP2 TypeScript
sample). Your job: make ONE small, fully-verified improvement per run that
hardens or tests the Verifiable Intent integration (`src/common/vi` and the role
wiring in `src/roles`). Then stop.

## Procedure (do this exactly, once)

1. Read `BACKLOG.md`. Choose the single highest-priority unchecked item `- [ ]`.
   If every item is already checked, pick the most valuable NEW hardening/test
   task you can find and add it.
2. Make a small, focused change. Strongly prefer ADDING or STRENGTHENING tests
   over changing production code. If you change production code, it must be to
   fix a real bug that a test now proves.
3. Verify — ALL of these must pass before you keep the change:
   - `npx tsc --noEmit`   (this sample has no `typecheck` script)
   - `npm run lint`
   - `npx vitest run test/unit`
   Do NOT run `npm test` or anything in `test/e2e/` — e2e needs a live Gemini
   API key and running servers, and will fail or hang here.
4. If green: tick the item in `BACKLOG.md` (`- [x]`), then `git add -A` and
   `git commit -m "loop: <what you did>"`. If you discovered new useful work,
   append new `- [ ]` items to `BACKLOG.md`.
5. If you cannot get to green: run `git checkout -- .` to revert your changes,
   leave the item unchecked, and append a short `blocked:` note under it.

## Hard rules

- Never delete, skip, weaken, or loosen an assertion just to make tests pass.
- Never edit files under `.git/`, `.github/`, `.claude/`, or the npm-linked
  `node_modules/@verifiable-intent` package. Only touch this sample.
- Keep each change minimal and reversible. One backlog item per run, then stop.
- Amounts are in minor units (cents). Scenario fixtures live in
  `src/common/vi/fixtures.ts`; the layer model lives in `src/common/vi/flow.ts`.
