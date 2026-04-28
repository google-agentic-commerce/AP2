"""Centralized constraint checking for AP2 mandates.

Provides an object-oriented constraint evaluation system where each constraint
type has a corresponding evaluator class.  New constraint types can be added
by implementing a new evaluator and registering it in the factory function.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from ap2.sdk.generated.open_checkout_mandate import (
    AllowedMerchants,
    LineItems,
    OpenCheckoutMandate,
)
from ap2.sdk.generated.open_payment_mandate import (
    AgentRecurrence,
    AllowedPayees,
    AllowedPaymentInstruments,
    AllowedPisps,
    AmountRange,
    Budget,
    ExecutionDate,
    Frequency,
    OpenPaymentMandate,
    PaymentReference,
)
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.checkout import Checkout
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.max_flow_helper import evaluate_line_items_max_flow
from pydantic import BaseModel


class MandateContext(BaseModel):
    """Aggregated usage context for a mandate."""

    total_amount: int = 0
    total_uses: int = 0
    last_used_date: float | None = None


def merchant_matches(candidate: Merchant, target: Merchant) -> bool:
    """Match merchants by ``id`` (preferred) or by ``name`` + ``website``."""
    candidate_id = candidate.id

    if isinstance(target, Merchant):
        target_id = target.id
        target_name = target.name
        target_website = target.website
    else:
        target_id = target.get('id')
        target_name = target.get('name')
        target_website = target.get('website')

    if candidate_id and target_id:
        return candidate_id == target_id

    return (
        candidate.name == target_name
        and bool(candidate.name)
        and candidate.website == target_website
        and bool(candidate.website)
    )


class PaymentConstraintEvaluator(ABC):
    """Base class for payment constraint evaluators."""

    @abstractmethod
    def evaluate(
        self,
        closed_mandate: PaymentMandate,
        open_checkout_hash: str | None = None,
    ) -> list[str]:
        """Return violation messages, or [] if the constraint is satisfied."""


class AmountRangeEvaluator(PaymentConstraintEvaluator):
    """Evaluates if the payment amount is within the specified range."""

    def __init__(self, constraint: AmountRange):
        self.constraint = constraint

    def evaluate(
        self,
        closed_mandate: PaymentMandate,
        open_checkout_hash: str | None = None,
    ) -> list[str]:
        violations: list[str] = []
        amount = closed_mandate.payment_amount

        if (
            self.constraint.currency
            and amount.currency != self.constraint.currency
        ):
            violations.append(
                f'Currency mismatch: expected {self.constraint.currency}, '
                f'got {amount.currency}'
            )
        if (
            self.constraint.min is not None
            and amount.amount < self.constraint.min
        ):
            violations.append(
                f'Amount {amount.amount} below minimum {self.constraint.min}'
            )
        if (
            self.constraint.max is not None
            and amount.amount > self.constraint.max
        ):
            violations.append(
                f'Amount {amount.amount} exceeds maximum {self.constraint.max}'
            )
        return violations


class AllowedPayeeEvaluator(PaymentConstraintEvaluator):
    """Evaluates if the payment's payee is in the allowed list."""

    def __init__(self, constraint: AllowedPayees):
        self.constraint = constraint

    def evaluate(
        self,
        closed_mandate: PaymentMandate,
        open_checkout_hash: str | None = None,
    ) -> list[str]:
        payee = closed_mandate.payee
        if any(
            merchant_matches(allowed, payee)
            for allowed in self.constraint.allowed
        ):
            return []
        return [f'Payee {payee.name} not in allowed list']


class PaymentReferenceEvaluator(PaymentConstraintEvaluator):
    """Verify that the payment's transaction_id matches the checkout reference.

    This constraint binds the payment mandate to a specific open checkout
    mandate via the ``checkout_reference`` digest.  The closed payment's
    ``transaction_id`` (which is the SHA-256 of the checkout JWT) must
    equal the ``checkout_reference`` in this constraint.
    """

    def __init__(self, constraint: PaymentReference):
        self.constraint = constraint

    def evaluate(
        self,
        closed_mandate: PaymentMandate,
        open_checkout_hash: str | None = None,
    ) -> list[str]:
        if not open_checkout_hash:
            return [
                'open_checkout_hash is required to evaluate PaymentReference'
                ' constraints'
            ]

        if open_checkout_hash != self.constraint.conditional_transaction_id:
            return [
                'PaymentReference mismatch: expected open checkout hash '
                f'{self.constraint.conditional_transaction_id}, '
                f'got {open_checkout_hash}'
            ]
        return []


def calculate_period_start(now: float, frequency: Frequency) -> float:
    """Calculate the start of the current period based on frequency."""
    dt = datetime.fromtimestamp(now)
    if frequency == Frequency.DAILY:
        start_dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_dt.timestamp()
    if frequency == Frequency.WEEKLY:
        start_dt = dt.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=dt.weekday())
        return start_dt.timestamp()
    if frequency == Frequency.MONTHLY:
        start_dt = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start_dt.timestamp()
    if frequency == Frequency.ANNUALLY:
        start_dt = dt.replace(
            month=1, day=1, hour=0, minute=0, second=0, microsecond=0
        )
        return start_dt.timestamp()
    if frequency == Frequency.ON_DEMAND:
        return 0.0
    # Fallback for unsupported frequencies
    return 0.0


class AgentRecurrenceEvaluator(PaymentConstraintEvaluator):
    """Evaluates agent recurrence."""

    def __init__(
        self,
        constraint: AgentRecurrence,
        mandate_context: MandateContext | None = None,
    ):
        self.constraint = constraint
        self.mandate_context = mandate_context

    def evaluate(
        self,
        closed_mandate: PaymentMandate,
        open_checkout_hash: str | None = None,
    ) -> list[str]:
        violations = []

        limit = self.constraint.max_occurrences

        if limit is not None:
            if self.mandate_context is None:
                return [
                    'Missing mandate context required to evaluate recurrence'
                ]
            occurrence_count = self.mandate_context.total_uses
            if occurrence_count >= limit:
                violations.append(
                    'Maximum occurrences exceeded: '
                    f'{occurrence_count} >= {limit}'
                )

        return violations


class AllowedPaymentInstrumentEvaluator(PaymentConstraintEvaluator):
    """Evaluates if the payment instrument is allowed."""

    def __init__(self, constraint: AllowedPaymentInstruments):
        self.constraint = constraint

    def evaluate(
        self,
        closed_mandate: PaymentMandate,
        open_checkout_hash: str | None = None,
    ) -> list[str]:
        instrument = closed_mandate.payment_instrument
        if not instrument:
            return ['Missing payment instrument in closed mandate']
        if any(
            allowed.id == instrument.id
            for allowed in self.constraint.allowed
        ):
            return []
        return [f'Payment instrument {instrument.id} not in allowed list']


class AllowedPispEvaluator(PaymentConstraintEvaluator):
    """Evaluates if the PISP is allowed."""

    def __init__(self, constraint: AllowedPisps):
        self.constraint = constraint

    def evaluate(
        self,
        closed_mandate: PaymentMandate,
        open_checkout_hash: str | None = None,
    ) -> list[str]:
        if not closed_mandate.pisp:
            return ['Missing PISP in closed mandate']

        if any(
            allowed.domain_name == closed_mandate.pisp.domain_name
            and allowed.legal_name == closed_mandate.pisp.legal_name
            and allowed.brand_name == closed_mandate.pisp.brand_name
            for allowed in self.constraint.allowed
        ):
            return []
        return [f'PISP {closed_mandate.pisp} not in allowed list']


class BudgetEvaluator(PaymentConstraintEvaluator):
    """Evaluates if the cumulative transaction amount exceeds the budget."""

    def __init__(
        self,
        constraint: Budget,
        mandate_context: MandateContext | None = None,
    ):
        self.constraint = constraint
        self.mandate_context = mandate_context

    def evaluate(
        self,
        closed_mandate: PaymentMandate,
        open_checkout_hash: str | None = None,
    ) -> list[str]:
        if closed_mandate.payment_amount.currency != self.constraint.currency:
            return [
                'Budget currency mismatch: expected '
                f'{self.constraint.currency}, '
                f'got {closed_mandate.payment_amount.currency}'
            ]

        if self.mandate_context is None:
            return ['Missing mandate context required to evaluate budget']

        past_spend = self.mandate_context.total_amount
        total_spend = past_spend + closed_mandate.payment_amount.amount

        budget_max_cents = int(self.constraint.max * 100)
        if total_spend > budget_max_cents:
            return [
                f'Cumulative spend {total_spend} exceeds '
                f'budget limit {budget_max_cents} (past spend: {past_spend})'
            ]
        return []


class ExecutionDateEvaluator(PaymentConstraintEvaluator):
    """Evaluates if the execution date is within the allowed window."""

    def __init__(self, constraint: ExecutionDate):
        self.constraint = constraint

    def evaluate(
        self,
        closed_mandate: PaymentMandate,
        open_checkout_hash: str | None = None,
    ) -> list[str]:
        exec_date = closed_mandate.execution_date
        if not exec_date:
            return []

        violations = []
        if (
            self.constraint.not_before
            and exec_date < self.constraint.not_before
        ):
            violations.append(
                f'Execution date {exec_date} is before allowed window '
                f'{self.constraint.not_before}'
            )
        if self.constraint.not_after and exec_date > self.constraint.not_after:
            violations.append(
                f'Execution date {exec_date} is after allowed window '
                f'{self.constraint.not_after}'
            )
        return violations


def create_payment_evaluator(  # noqa: PLR0911
    constraint: (
        AgentRecurrence
        | AllowedPayees
        | AllowedPaymentInstruments
        | AllowedPisps
        | AmountRange
        | Budget
        | ExecutionDate
        | PaymentReference
    ),
    mandate_context: MandateContext | None = None,
) -> PaymentConstraintEvaluator:
    """Factory: create the appropriate evaluator for a payment constraint."""
    if isinstance(constraint, AmountRange):
        return AmountRangeEvaluator(constraint)
    if isinstance(constraint, AllowedPayees):
        return AllowedPayeeEvaluator(constraint)
    if isinstance(constraint, PaymentReference):
        return PaymentReferenceEvaluator(constraint)
    if isinstance(constraint, AgentRecurrence):
        return AgentRecurrenceEvaluator(constraint, mandate_context)
    if isinstance(constraint, AllowedPaymentInstruments):
        return AllowedPaymentInstrumentEvaluator(constraint)
    if isinstance(constraint, AllowedPisps):
        return AllowedPispEvaluator(constraint)
    if isinstance(constraint, Budget):
        return BudgetEvaluator(constraint, mandate_context)
    if isinstance(constraint, ExecutionDate):
        return ExecutionDateEvaluator(constraint)
    raise ValueError(f'Unknown payment constraint type: {type(constraint)}')


class CheckoutConstraintEvaluator(ABC):
    """Base class for checkout constraint evaluators."""

    @abstractmethod
    def evaluate(self, checkout: Checkout) -> list[str]:
        """Return violation messages, or [] if the constraint is satisfied."""


class AllowedMerchantsEvaluator(CheckoutConstraintEvaluator):
    """Evaluates if the checkout merchant is in the allowed list."""

    def __init__(self, constraint: AllowedMerchants):
        self.constraint = constraint

    def evaluate(self, checkout: Checkout) -> list[str]:
        merchant_data = checkout.merchant
        if not merchant_data:
            return ['Missing merchant in checkout']
        if any(
            merchant_matches(allowed, merchant_data)
            for allowed in self.constraint.allowed
        ):
            return []
        return [f'Merchant {merchant_data.name or ""} not in allowed list']


class LineItemsEvaluator(CheckoutConstraintEvaluator):
    """Validate checkout line items against a ``LineItems`` constraint."""

    def __init__(self, constraint: LineItems):
        self.constraint = constraint

    def evaluate(self, checkout: Checkout) -> list[str]:
        checkout_items = checkout.line_items or []
        if not checkout_items:
            return ['Empty cart does not satisfy line_items constraint']

        requirements = self.constraint.items
        return evaluate_line_items_max_flow(checkout_items, requirements)


def create_checkout_evaluator(
    constraint: AllowedMerchants | LineItems,
) -> CheckoutConstraintEvaluator:
    """Factory: create the appropriate evaluator for a checkout constraint."""
    if isinstance(constraint, AllowedMerchants):
        return AllowedMerchantsEvaluator(constraint)
    if isinstance(constraint, LineItems):
        return LineItemsEvaluator(constraint)
    raise ValueError(f'Unknown checkout constraint type: {type(constraint)}')


def check_preset_payment_claims(
    open_mandate: OpenPaymentMandate,
    closed_mandate: PaymentMandate,
) -> list[str]:
    """Verify pre-set claims in the open mandate match the closed mandate.

    If a field is set in the open mandate, the closed mandate must contain
    an identical value.

    Args:
      open_mandate: The open payment mandate with potential pre-set claims.
      closed_mandate: The closed payment mandate to be validated.

    Returns:
      A list of strings, where each string describes a violation of the
      pre-set claims. The list is empty if no violations are found.
    """
    violations: list[str] = []

    if open_mandate.payee is not None and not merchant_matches(
        open_mandate.payee, closed_mandate.payee
    ):
        violations.append(
            f'Pre-set payee mismatch: expected {open_mandate.payee.name}, '
            f'got {closed_mandate.payee.name}'
        )

    if (
        open_mandate.payment_amount is not None
        and open_mandate.payment_amount != closed_mandate.payment_amount
    ):
        violations.append(
            'Pre-set amount mismatch: expected '
            f'{open_mandate.payment_amount}, '
            f'got {closed_mandate.payment_amount}'
        )

    if (
        open_mandate.payment_instrument is not None
        and open_mandate.payment_instrument != closed_mandate.payment_instrument
    ):
        violations.append('Pre-set payment_instrument mismatch')

    if (
        open_mandate.execution_date is not None
        and open_mandate.execution_date != closed_mandate.execution_date
    ):
        violations.append(
            'Pre-set execution_date mismatch: expected '
            f'{open_mandate.execution_date}, '
            f'got {closed_mandate.execution_date}'
        )

    return violations


def check_payment_constraints(
    open_mandate: OpenPaymentMandate,
    closed_payment: PaymentMandate,
    open_checkout_hash: str | None = None,
    mandate_context: MandateContext | None = None,
) -> list[str]:
    """Verify the closed payment satisfies open mandate constraints.

    Also checks that any pre-set claims in the open mandate are present
    and unchanged in the closed mandate.

    Args:
      open_mandate: The open payment mandate containing constraints.
      closed_payment: The closed payment mandate to be validated.
      open_checkout_hash: The hash of the open checkout mandate, required for
        `PaymentReference` constraints.
      mandate_context: Aggregated usage context for the mandate.

    Returns:
      A list of strings, where each string describes a violation of the
      constraints. The list is empty if no violations are found.
    """
    violations: list[str] = []
    violations.extend(check_preset_payment_claims(open_mandate, closed_payment))

    has_recurrence = any(
        isinstance(c, AgentRecurrence) for c in open_mandate.constraints
    )
    if has_recurrence:
        has_amount = any(
            isinstance(c, AmountRange) for c in open_mandate.constraints
        )
        has_budget = any(
            isinstance(c, Budget) for c in open_mandate.constraints
        )

        if not has_amount:
            violations.append(
                    'payment.agent_recurrence requires payment.amount_range '
                    'constraint'
            )
        if not has_budget:
            violations.append(
                'payment.agent_recurrence requires payment.budget constraint'
            )

    for constraint in open_mandate.constraints:
        evaluator = create_payment_evaluator(constraint, mandate_context)
        violations.extend(
            evaluator.evaluate(closed_payment, open_checkout_hash)
        )

    return violations


def check_checkout_constraints(
    open_mandate: OpenCheckoutMandate,
    checkout: Checkout,
) -> list[str]:
    """Verify checkout satisfies open checkout mandate constraints."""
    violations: list[str] = []

    for constraint in open_mandate.constraints:
        evaluator = create_checkout_evaluator(constraint)
        violations.extend(evaluator.evaluate(checkout))

    return violations
