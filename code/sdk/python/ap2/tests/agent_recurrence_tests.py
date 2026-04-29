"""Tests for AgentRecurrence constraint evaluation."""

import time

from ap2.sdk.constraints import (
    MandateContext,
    check_payment_constraints,
)
from ap2.sdk.generated.open_payment_mandate import (
    AgentRecurrence,
    AmountRange,
    Budget,
    Frequency,
    OpenPaymentMandate,
)
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.jwk import JsonWebKey
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.utils import ec_key_to_jwk
from cryptography.hazmat.primitives.asymmetric import ec


_DUMMY_KEY = ec.generate_private_key(ec.SECP256R1())
_CNF: JsonWebKey = {
    'jwk': ec_key_to_jwk(_DUMMY_KEY.public_key()).model_dump(exclude_none=True)
}


def _open_payment(**kw):
    defaults = dict(constraints=[], cnf=_CNF)
    defaults.update(kw)
    return OpenPaymentMandate(**defaults)


def _closed_payment(**kw):
    defaults = dict(
        transaction_id='tx_1',
        payee=Merchant(name='Shop', id='s-1'),
        payment_amount=Amount(amount=1000, currency='USD'),
        payment_instrument=PaymentInstrument(id='pi-1', type='credit'),
    )
    defaults.update(kw)
    return PaymentMandate(**defaults)


def test_payment_agent_recurrence_no_state():
    """No state (zero usages) passes."""

    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AgentRecurrence(frequency=Frequency.DAILY, max_occurrences=1),
                AmountRange(min=100, max=2000, currency='USD'),
                Budget(max=5000, currency='USD'),
            ]
        ),
        _closed_payment(),
        mandate_context=MandateContext(total_uses=0, total_amount=0),
    )
    assert violations == []


def test_payment_agent_recurrence_under_limit():
    """Usage count under limit passes."""

    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AgentRecurrence(frequency=Frequency.DAILY, max_occurrences=2),
                AmountRange(min=100, max=2000, currency='USD'),
                Budget(max=5000, currency='USD'),
            ]
        ),
        _closed_payment(),
        mandate_context=MandateContext(
            total_uses=1, total_amount=1000, last_used_date=time.time()
        ),
    )
    assert violations == []


def test_payment_agent_recurrence_over_limit():
    """Usage count reaching max_occurrences fails."""

    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AgentRecurrence(frequency=Frequency.DAILY, max_occurrences=1),
                AmountRange(min=100, max=2000, currency='USD'),
                Budget(max=5000, currency='USD'),
            ]
        ),
        _closed_payment(),
        mandate_context=MandateContext(
            total_uses=1, total_amount=1000, last_used_date=time.time()
        ),
    )
    assert any('Maximum occurrences exceeded' in v for v in violations)


def test_payment_agent_recurrence_absent_limit():
    """If max_occurrences is absent, no count limit is enforced."""

    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AgentRecurrence(
                    frequency=Frequency.DAILY, max_occurrences=None
                ),
                AmountRange(min=100, max=2000, currency='USD'),
                Budget(max=5000, currency='USD'),
            ]
        ),
        _closed_payment(),
        mandate_context=MandateContext(
            total_uses=100, total_amount=1000, last_used_date=time.time()
        ),
    )
    assert violations == []


def test_payment_agent_recurrence_requires_amount():
    """AgentRecurrence requires AmountRange constraint."""

    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AgentRecurrence(frequency=Frequency.DAILY, max_occurrences=1),
                Budget(max=5000, currency='USD'),
            ]
        ),
        _closed_payment(),
        mandate_context=MandateContext(total_uses=0, total_amount=0),
    )
    assert any(
            'payment.agent_recurrence requires payment.amount_range '
            'constraint' in v
        for v in violations
    )


def test_payment_agent_recurrence_requires_budget():
    """AgentRecurrence requires Budget constraint."""

    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AgentRecurrence(frequency=Frequency.DAILY, max_occurrences=1),
                AmountRange(min=100, max=2000, currency='USD'),
            ]
        ),
        _closed_payment(),
        mandate_context=MandateContext(total_uses=0, total_amount=0),
    )
    assert any(
        'payment.agent_recurrence requires payment.budget constraint' in v
        for v in violations
    )


def test_payment_agent_recurrence_missing_context():
    """AgentRecurrence fails if max_occurrences is set but context is missing."""

    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AgentRecurrence(frequency=Frequency.DAILY, max_occurrences=1),
                AmountRange(min=100, max=2000, currency='USD'),
                Budget(max=5000, currency='USD'),
            ]
        ),
        _closed_payment(),
        mandate_context=None,
    )
    assert any(
        'Missing mandate context required to evaluate recurrence' in v
        for v in violations
    )
