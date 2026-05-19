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

    budget_max_cents = round(budget.max_dollars * 100)
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
    overspend = total - round(budget.max_dollars * 100)
    print(f'Total spent: ${total / 100:.2f}')
    print(f'Budget:      ${budget.max_dollars:.2f}')
    print(f'Overspent:   ${overspend / 100:.2f}')
    print()
    print('Problem: each merchant evaluated independently.')
    print("Neither knew about the other's transaction.")


# =========================================================
# Part 2: The fix — external budget authority
# =========================================================


class Decision(Enum):
    """Canonical three-way decision from a budget authority.

    ALLOW             — full requested amount approved.
    ALLOW_WITH_CAPS   — partial budget remains; approved for
                        less than requested. Canonical for
                        divisible / metered budgets (API
                        credits, streaming, stablecoin
                        cents). Not exercised in this retail
                        sample. Callers MUST treat as DENY
                        if they cannot accept partial
                        fulfillment.
    DENY              — no budget remains, or other error.
    """

    ALLOW = 'allow'
    ALLOW_WITH_CAPS = 'allow_with_caps'
    DENY = 'deny'


class ReservationStatus(Enum):
    """Status of a budget reservation."""

    HELD = 'held'
    COMMITTED = 'committed'
    RELEASED = 'released'


@dataclass
class Reservation:
    """A budget reservation placed by the authority."""

    reservation_id: str
    mandate_id: str
    amount: int
    status: ReservationStatus = ReservationStatus.HELD


@dataclass
class ReserveResult:
    """Result of a reserve call."""

    decision: Decision
    reservation_id: str | None = None
    reason: str | None = None
    remaining: int | None = None
    allowed_amount: int | None = None
    requested_amount: int | None = None


@dataclass
class BudgetState:
    """Result of a query_budget call."""

    mandate_id: str
    budget: int
    spent: int
    held: int
    remaining: int


class BudgetAuthority:
    """External budget authority.

    Maintains a single ledger across all merchants. The
    reserve call is atomic: checks the budget and places a
    reservation in one operation.

    Canonical six-verb interface (see
    goodmeta/agent-payments-landscape Budget Authority
    Protocol). This sample demonstrates four:

        reserve            — atomically check + hold
        commit             — confirm after successful payment
        release            — return unspent reservation
                             before commit
        query_budget       — snapshot of budget state

    Two additional verbs are part of the canonical interface
    but out of scope for this minimal sample:

        refund(reservation_id, amount)
            — reverse an already-committed amount
              (post-commit, distinct from release)
        query_reservation(reservation_id)
            — per-reservation state lookup
    """

    def __init__(self) -> None:
        """Initialize empty ledger."""
        self._budgets: dict[str, int] = {}
        self._spent: dict[str, int] = {}
        self._reservations: dict[str, Reservation] = {}
        self._held_by_mandate: dict[str, int] = {}
        self._keys: dict[str, str] = {}

    def register_mandate(
        self,
        mandate_id: str,
        budget_cents: int,
    ) -> None:
        """Register a mandate with a budget limit."""
        self._budgets[mandate_id] = budget_cents
        self._spent.setdefault(mandate_id, 0)
        self._held_by_mandate.setdefault(mandate_id, 0)

    def reserve(
        self,
        mandate_id: str,
        amount_cents: int,
        idempotency_key: str,
    ) -> ReserveResult:
        """Atomically check budget and place reservation.

        This retail sample emits ALLOW or DENY only. The
        canonical interface also defines ALLOW_WITH_CAPS for
        divisible / metered budgets (see Cycles for an
        implementation that emits it).
        """
        if idempotency_key in self._keys:
            rid = self._keys[idempotency_key]
            res = self._reservations[rid]
            return ReserveResult(
                decision=Decision.ALLOW,
                reservation_id=rid,
                remaining=self._remaining(mandate_id),
                allowed_amount=res.amount,
                requested_amount=res.amount,
            )

        budget_max = self._budgets.get(mandate_id)
        if budget_max is None:
            return ReserveResult(
                decision=Decision.DENY,
                reason='Unknown mandate',
                requested_amount=amount_cents,
            )

        remaining = self._remaining(mandate_id)
        if amount_cents > remaining:
            return ReserveResult(
                decision=Decision.DENY,
                reason=(
                    f'Budget exceeded: {amount_cents} > '
                    f'{remaining} remaining'
                ),
                remaining=remaining,
                requested_amount=amount_cents,
            )

        reservation_id = f'res_{uuid.uuid4().hex}'
        self._reservations[reservation_id] = Reservation(
            reservation_id=reservation_id,
            mandate_id=mandate_id,
            amount=amount_cents,
        )
        self._held_by_mandate[mandate_id] = (
            self._held_by_mandate.get(mandate_id, 0)
            + amount_cents
        )
        self._keys[idempotency_key] = reservation_id

        return ReserveResult(
            decision=Decision.ALLOW,
            reservation_id=reservation_id,
            remaining=remaining - amount_cents,
            allowed_amount=amount_cents,
            requested_amount=amount_cents,
        )

    def commit(self, reservation_id: str) -> bool:
        """Confirm a reservation after successful payment."""
        res = self._reservations.get(reservation_id)
        if not res or res.status != ReservationStatus.HELD:
            return False
        res.status = ReservationStatus.COMMITTED
        self._spent[res.mandate_id] += res.amount
        self._held_by_mandate[res.mandate_id] -= res.amount
        return True

    def release(self, reservation_id: str) -> bool:
        """Return an unspent reservation before commit.

        Pre-commit only. Use refund (not implemented here)
        for post-commit reversal.
        """
        res = self._reservations.get(reservation_id)
        if not res or res.status != ReservationStatus.HELD:
            return False
        res.status = ReservationStatus.RELEASED
        self._held_by_mandate[res.mandate_id] -= res.amount
        return True

    def query_budget(self, mandate_id: str) -> BudgetState:
        """Snapshot of budget state across all reservations."""
        budget_max = self._budgets.get(mandate_id, 0)
        spent = self._spent.get(mandate_id, 0)
        held = self._held_by_mandate.get(mandate_id, 0)
        return BudgetState(
            mandate_id=mandate_id,
            budget=budget_max,
            spent=spent,
            held=held,
            remaining=budget_max - spent - held,
        )

    def _remaining(self, mandate_id: str) -> int:
        budget = self._budgets.get(mandate_id, 0)
        spent = self._spent.get(mandate_id, 0)
        held = self._held_by_mandate.get(mandate_id, 0)
        return budget - spent - held


def _format_decision(result: ReserveResult) -> str:
    if result.decision == Decision.ALLOW:
        return 'ALLOW'
    if result.decision == Decision.ALLOW_WITH_CAPS:
        return 'ALLOW_WITH_CAPS'
    return 'DENY'


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

    # Merchant A: reserve $60 → ALLOW
    result_a = authority.reserve(
        mandate_id, 6000, uuid.uuid4().hex,
    )
    print('Merchant A: reserve($60.00)')
    print(f'  Decision: {_format_decision(result_a)}')
    print(f'  Reservation: {result_a.reservation_id}')
    remaining_a = (result_a.remaining or 0) / 100
    print(f'  Remaining: ${remaining_a:.2f}')
    if (
        result_a.decision == Decision.ALLOW
        and result_a.reservation_id
    ):
        authority.commit(result_a.reservation_id)
        print('  Payment succeeded -> committed')
    print()

    # Merchant B: reserve $60 → DENY (only $40 left, indivisible item)
    result_b = authority.reserve(
        mandate_id, 6000, uuid.uuid4().hex,
    )
    print('Merchant B: reserve($60.00)')
    print(f'  Decision: {_format_decision(result_b)}')
    if result_b.reason:
        print(f'  Reason: {result_b.reason}')
    print()

    # Merchant B: retry $35 → ALLOW
    result_c = authority.reserve(
        mandate_id, 3500, uuid.uuid4().hex,
    )
    print('Merchant B: reserve($35.00) — retry')
    print(f'  Decision: {_format_decision(result_c)}')
    if (
        result_c.decision == Decision.ALLOW
        and result_c.reservation_id
    ):
        remaining_c = (result_c.remaining or 0) / 100
        print(f'  Reservation: {result_c.reservation_id}')
        print(f'  Remaining: ${remaining_c:.2f}')
        authority.commit(result_c.reservation_id)
        print('  Payment succeeded -> committed')
    print()

    state = authority.query_budget(mandate_id)
    print('Final state:')
    print(f'  Budget:    ${state.budget / 100:.2f}')
    print(f'  Spent:     ${state.spent / 100:.2f}')
    print(f'  Remaining: ${state.remaining / 100:.2f}')
    print()
    print('Budget enforced across both merchants.')


if __name__ == '__main__':
    demo_overspend()
    demo_budget_authority()
