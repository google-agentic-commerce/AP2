"""Cross-merchant budget enforcement sample for AP2.

Demonstrates the budget enforcement gap described in
https://github.com/google-agentic-commerce/AP2/issues/207

Part 1: Shows how independent merchant evaluation leads to
budget overflow.
Part 2: Shows how an external budget authority prevents it.

No external dependencies. The budget authority is mocked
in-process.
"""

from __future__ import annotations

import uuid

from dataclasses import dataclass
from enum import Enum


@dataclass
class Budget:
    """AP2 budget constraint (simplified from SDK)."""

    max_dollars: float
    currency: str = 'USD'


@dataclass
class MandateContext:
    """Transaction history that feeds BudgetEvaluator.

    In production, populated from the merchant's own history.
    The cross-merchant gap: each merchant only has ITS
    history.
    """

    total_amount: int = 0


@dataclass
class PaymentAmount:
    """Amount for a single transaction in cents."""

    amount: int
    currency: str = 'USD'


def evaluate_budget(
    budget: Budget,
    new_amount: PaymentAmount,
    context: MandateContext,
) -> list[str]:
    """Evaluate whether a transaction fits within budget.

    Returns an empty list if approved, or a list of reasons.
    Matches the AP2 SDK BudgetEvaluator pattern.
    """
    if new_amount.currency != budget.currency:
        return [
            f'Currency mismatch: expected {budget.currency},'
            f' got {new_amount.currency}'
        ]

    budget_max_cents = int(budget.max_dollars * 100)
    total = context.total_amount + new_amount.amount

    if total > budget_max_cents:
        return [
            f'Cumulative spend {total} exceeds '
            f'budget limit {budget_max_cents} '
            f'(past spend: {context.total_amount})'
        ]
    return []


# =========================================================
# Part 1: The problem — independent merchant evaluation
# =========================================================


def demo_overspend() -> None:
    """Show cross-merchant budget overflow."""
    print('=' * 60)
    print('PART 1: Cross-Merchant Budget Overflow')
    print('=' * 60)
    print()

    budget = Budget(max_dollars=100.00)

    # Each merchant maintains its own context.
    # Neither knows about the other's transactions.
    ctx_a = MandateContext(total_amount=0)
    ctx_b = MandateContext(total_amount=0)

    # Merchant A: agent buys $60 item
    amt_a = PaymentAmount(amount=6000)
    errors_a = evaluate_budget(budget, amt_a, ctx_a)
    label_a = errors_a if errors_a else 'APPROVED'
    print(f'Merchant A: ${amt_a.amount / 100:.2f} purchase')
    print(f'  Context: total_amount={ctx_a.total_amount}')
    print(f'  Result: {label_a}')
    if not errors_a:
        ctx_a.total_amount += amt_a.amount
    print()

    # Merchant B: agent buys $60 item
    amt_b = PaymentAmount(amount=6000)
    errors_b = evaluate_budget(budget, amt_b, ctx_b)
    label_b = errors_b if errors_b else 'APPROVED'
    print(f'Merchant B: ${amt_b.amount / 100:.2f} purchase')
    print(f'  Context: total_amount={ctx_b.total_amount}')
    print(f'  Result: {label_b}')
    if not errors_b:
        ctx_b.total_amount += amt_b.amount
    print()

    total = ctx_a.total_amount + ctx_b.total_amount
    overspend = total - int(budget.max_dollars * 100)
    print(f'Total spent: ${total / 100:.2f}')
    print(f'Budget:      ${budget.max_dollars:.2f}')
    print(f'Overspent:   ${overspend / 100:.2f}')
    print()
    print('Problem: each merchant evaluated independently.')
    print("Neither knew about the other's transaction.")


# =========================================================
# Part 2: The fix — external budget authority
# =========================================================


class HoldStatus(Enum):
    """Status of a budget hold."""

    HELD = 'held'
    COMMITTED = 'committed'
    REFUNDED = 'refunded'


@dataclass
class Hold:
    """A budget hold placed by the authority."""

    hold_id: str
    mandate_id: str
    amount: int
    status: HoldStatus = HoldStatus.HELD


@dataclass
class AuthorizeResult:
    """Result of an authorize call."""

    approved: bool
    hold_id: str | None = None
    reason: str | None = None
    remaining: int | None = None


class BudgetAuthority:
    """External budget authority with four verbs.

    Maintains a single ledger across all merchants.
    The authorize call is atomic: it checks the budget and
    places a hold in one operation.

    Verbs:
        authorize — atomically check + hold
        commit    — confirm after successful payment
        refund    — release if payment fails
        query     — check remaining budget
    """

    def __init__(self) -> None:
        """Initialize empty ledger."""
        self._budgets: dict[str, int] = {}
        self._spent: dict[str, int] = {}
        self._holds: dict[str, Hold] = {}
        self._keys: dict[str, str] = {}

    def register_mandate(
        self,
        mandate_id: str,
        budget_cents: int,
    ) -> None:
        """Register a mandate with a budget limit."""
        self._budgets[mandate_id] = budget_cents
        self._spent.setdefault(mandate_id, 0)

    def authorize(
        self,
        mandate_id: str,
        amount_cents: int,
        idempotency_key: str,
    ) -> AuthorizeResult:
        """Atomically check budget and place hold."""
        if idempotency_key in self._keys:
            hid = self._keys[idempotency_key]
            return AuthorizeResult(
                approved=True,
                hold_id=hid,
                remaining=self._remaining(mandate_id),
            )

        budget_max = self._budgets.get(mandate_id)
        if budget_max is None:
            return AuthorizeResult(
                approved=False,
                reason='Unknown mandate',
            )

        remaining = self._remaining(mandate_id)
        if amount_cents > remaining:
            return AuthorizeResult(
                approved=False,
                reason=(
                    f'Budget exceeded: {amount_cents} > '
                    f'{remaining} remaining'
                ),
                remaining=remaining,
            )

        hold_id = f'hold_{uuid.uuid4().hex[:16]}'
        self._holds[hold_id] = Hold(
            hold_id=hold_id,
            mandate_id=mandate_id,
            amount=amount_cents,
        )
        self._keys[idempotency_key] = hold_id

        return AuthorizeResult(
            approved=True,
            hold_id=hold_id,
            remaining=remaining - amount_cents,
        )

    def commit(self, hold_id: str) -> bool:
        """Confirm a hold after successful payment."""
        hold = self._holds.get(hold_id)
        if not hold or hold.status != HoldStatus.HELD:
            return False
        hold.status = HoldStatus.COMMITTED
        self._spent[hold.mandate_id] += hold.amount
        return True

    def refund(self, hold_id: str) -> bool:
        """Release a hold when payment fails."""
        hold = self._holds.get(hold_id)
        if not hold or hold.status != HoldStatus.HELD:
            return False
        hold.status = HoldStatus.REFUNDED
        return True

    def query(
        self, mandate_id: str,
    ) -> dict[str, int | str]:
        """Query budget state."""
        budget_max = self._budgets.get(mandate_id, 0)
        spent = self._spent.get(mandate_id, 0)
        held = self._active_holds(mandate_id)
        return {
            'mandate_id': mandate_id,
            'budget': budget_max,
            'spent': spent,
            'held': held,
            'remaining': budget_max - spent - held,
        }

    def _remaining(self, mandate_id: str) -> int:
        budget = self._budgets.get(mandate_id, 0)
        spent = self._spent.get(mandate_id, 0)
        held = self._active_holds(mandate_id)
        return budget - spent - held

    def _active_holds(self, mandate_id: str) -> int:
        return sum(
            h.amount
            for h in self._holds.values()
            if h.mandate_id == mandate_id
            and h.status == HoldStatus.HELD
        )


def demo_budget_authority() -> None:
    """Show budget authority preventing overspend."""
    print()
    print('=' * 60)
    print('PART 2: External Budget Authority')
    print('=' * 60)
    print()

    mandate_id = 'mandate_agent_001'
    authority = BudgetAuthority()
    authority.register_mandate(mandate_id, 10000)

    # Merchant A: authorize $60
    result_a = authority.authorize(
        mandate_id, 6000, uuid.uuid4().hex,
    )
    label = 'APPROVED' if result_a.approved else 'DENIED'
    print('Merchant A: authorize($60.00)')
    print(f'  Result: {label}')
    print(f'  Hold: {result_a.hold_id}')
    remaining_a = (result_a.remaining or 0) / 100
    print(f'  Remaining: ${remaining_a:.2f}')
    if result_a.approved and result_a.hold_id:
        authority.commit(result_a.hold_id)
        print('  Payment succeeded -> committed')
    print()

    # Merchant B: authorize $60 — should be denied
    result_b = authority.authorize(
        mandate_id, 6000, uuid.uuid4().hex,
    )
    label = 'APPROVED' if result_b.approved else 'DENIED'
    print('Merchant B: authorize($60.00)')
    print(f'  Result: {label}')
    if not result_b.approved:
        print(f'  Reason: {result_b.reason}')
    print()

    # Merchant B: retry with smaller amount
    result_c = authority.authorize(
        mandate_id, 3500, uuid.uuid4().hex,
    )
    label = 'APPROVED' if result_c.approved else 'DENIED'
    print('Merchant B: authorize($35.00) — retry')
    print(f'  Result: {label}')
    if result_c.approved and result_c.hold_id:
        remaining_c = (result_c.remaining or 0) / 100
        print(f'  Hold: {result_c.hold_id}')
        print(f'  Remaining: ${remaining_c:.2f}')
        authority.commit(result_c.hold_id)
        print('  Payment succeeded -> committed')
    print()

    state = authority.query(mandate_id)
    print('Final state:')
    print(f'  Budget:    ${int(state["budget"]) / 100:.2f}')
    print(f'  Spent:     ${int(state["spent"]) / 100:.2f}')
    remaining = int(state['remaining']) / 100
    print(f'  Remaining: ${remaining:.2f}')
    print()
    print('Budget enforced across both merchants.')


if __name__ == '__main__':
    demo_overspend()
    demo_budget_authority()
