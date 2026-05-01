# Cross-Merchant Budget Enforcement

Demonstrates the cross-merchant budget enforcement gap described in
[#207](https://github.com/google-agentic-commerce/AP2/issues/207) and a
solution using an external budget authority.

## The Problem

The AP2 `BudgetEvaluator` checks cumulative spend against a budget limit, but
each merchant only sees its own transaction history. When an agent shops at
multiple merchants under the same mandate, each merchant evaluates the budget
independently:

```
Agent mandate: $100 budget

Merchant A: BudgetEvaluator(total_amount=0, new_spend=60) → ✅ pass
Merchant B: BudgetEvaluator(total_amount=0, new_spend=60) → ✅ pass

Total spent: $120. Budget: $100. Overspent.
```

Neither merchant knows about the other's transaction. The `MandateContext`
that feeds `total_amount` is local to each merchant.

## The Fix

An external budget authority that both merchants call before accepting payment.
The authority maintains a single ledger and exposes four verbs:

| Verb | Purpose |
|------|---------|
| `authorize(mandate_id, amount, idempotency_key)` | Atomically check + hold |
| `commit(hold_id)` | Confirm after successful payment |
| `refund(hold_id)` | Release if payment fails |
| `query(mandate_id)` | Check remaining budget |

The `authorize` call is atomic: it decrements the budget and returns a hold in
one operation. There is no separate "check remaining" call that could race.

```
Agent mandate: $100 budget

Merchant A: authority.authorize(mandate, 60) → ✅ hold_1 (remaining: 40)
Merchant B: authority.authorize(mandate, 60) → ❌ rejected (40 < 60)

Total spent: $60. Budget enforced.
```

## Running

```bash
python cross_merchant_budget.py
```

No external dependencies required. The budget authority is mocked in-process.
