# Cross-Merchant Budget Enforcement

Demonstrates the cross-merchant budget enforcement gap described in
[#207](https://github.com/google-agentic-commerce/AP2/issues/207) and a
solution using an external budget authority.

## The Problem

The AP2 `BudgetEvaluator` checks cumulative spend against a budget limit, but
each merchant only sees its own transaction history. When an agent shops at
multiple merchants under the same mandate, each merchant evaluates the budget
independently:

```text
Agent mandate: $100 budget

Merchant A: BudgetEvaluator(total_amount=0, new_spend=60) → pass
Merchant B: BudgetEvaluator(total_amount=0, new_spend=60) → pass

Total spent: $120. Budget: $100. Overspent.
```

Neither merchant knows about the other's transaction. The `MandateContext`
that feeds `total_amount` is local to each merchant.

## The Fix

An external budget authority that both merchants call before accepting payment.
The authority maintains a single ledger and exposes a verb interface.

### Canonical verb set

The interface converges with the [Cycles](https://runcycles.io) protocol
(`reserve / commit / release`) and the broader budget-authority layer being
crosswalked in [`aeoess/agent-governance-vocabulary`][vocab]. Canonical six
verbs:

| Verb                                                | Purpose                              | In sample |
| --------------------------------------------------- | ------------------------------------ | --------- |
| `reserve(mandate_id, amount, idempotency_key)`      | Atomically check budget + hold       | yes       |
| `commit(reservation_id)`                            | Confirm after successful payment     | yes       |
| `release(reservation_id)`                           | Return unspent reservation (pre-commit) | yes    |
| `refund(reservation_id, amount)`                    | Reverse a committed amount (post-commit) | no    |
| `query_budget(mandate_id)`                          | Snapshot of budget state             | yes       |
| `query_reservation(reservation_id)`                 | Per-reservation lookup               | no        |

`release` and `refund` are deliberately separate: `release` returns an
unspent reservation before commit; `refund` reverses an already-committed
amount. Audit trails need both states.

### Decision shape

`reserve` returns a canonical three-value decision:

| Decision         | Meaning                                              | Exercised here |
| ---------------- | ---------------------------------------------------- | -------------- |
| `ALLOW`          | Full requested amount approved.                      | yes            |
| `ALLOW_WITH_CAPS`| Partial budget remains; approved for less than requested. | no — see note below |
| `DENY`           | No budget remains, or other error.                   | yes            |

`ALLOW_WITH_CAPS` is canonical for divisible / metered budgets (API credits,
streaming, stablecoin micropayments) where partial fulfillment is meaningful.
This retail sample does not exercise it — a $60 indivisible product cannot be
partially fulfilled at $40. See [Cycles](https://runcycles.io) for an
implementation that emits `ALLOW_WITH_CAPS`. Callers that do not handle
partial fulfillment MUST treat `ALLOW_WITH_CAPS` as `DENY` (safe default).

```text
Agent mandate: $100 budget

Merchant A: authority.reserve(mandate, 60) → ALLOW (remaining: 40)
Merchant B: authority.reserve(mandate, 60) → DENY (40 < 60)
Merchant B: authority.reserve(mandate, 35) → ALLOW (retry, remaining: 5)

Total spent: $95. Budget enforced.
```

The `reserve` call is atomic: it decrements the budget and returns a
reservation in one operation. There is no separate "check remaining" call
that could race.

## Running

```bash
python cross_merchant_budget.py
```

No external dependencies required. The budget authority is mocked in-process.

## Related

- AP2 [#207](https://github.com/google-agentic-commerce/AP2/issues/207) — gap discussion
- ACP [#231](https://github.com/agentic-commerce-protocol/agentic-commerce-protocol/issues/231) — three-layer model (passport / budget authority / rail)
- Cycles ([runcycles.io](https://runcycles.io)) — independent `reserve/commit/release` implementation
- Budget Authority Protocol spec — [goodmeta/agent-payments-landscape][bap]

[vocab]: https://github.com/aeoess/agent-governance-vocabulary
[bap]: https://github.com/goodmeta/agent-payments-landscape/blob/main/specs/budget-authority-protocol.md
