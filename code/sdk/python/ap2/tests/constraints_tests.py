"""Tests for centralized constraint checking (ap2.sdk.constraints)."""

import time

import pytest

from ap2.sdk.checkout_mandate_chain import CheckoutMandateChain
from ap2.sdk.constraints import (
    MandateContext,
    check_checkout_constraints,
    check_payment_constraints,
    check_preset_payment_claims,
    merchant_matches,
)
from ap2.sdk.generated.checkout_mandate import CheckoutMandate
from ap2.sdk.generated.open_checkout_mandate import (
    AllowedMerchants,
    OpenCheckoutMandate,
)
from ap2.sdk.generated.open_payment_mandate import (
    AllowedPayees,
    AllowedPaymentInstruments,
    AllowedPisps,
    AmountRange,
    Budget,
    ExecutionDate,
    OpenPaymentMandate,
    PaymentReference,
)
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.jwk import JsonWebKey
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.utils import ec_key_to_jwk
from ap2.tests.conftest import make_checkout_jwt
from cryptography.hazmat.primitives.asymmetric import ec


# MockUsageProvider removed as it was replaced by MandateContext


# ── Helpers ──────────────────────────────────────────────────────────────

_DUMMY_KEY = ec.generate_private_key(ec.SECP256R1())
_CNF: JsonWebKey = {
    'jwk': ec_key_to_jwk(_DUMMY_KEY.public_key()).model_dump(exclude_none=True)
}


def _open_payment(**kw):
    defaults = dict(constraints=[], cnf=_CNF)
    defaults.update(kw)
    return OpenPaymentMandate(**defaults)


def _open_checkout(**kw):
    defaults = dict(constraints=[], cnf=_CNF)
    defaults.update(kw)
    return OpenCheckoutMandate(**defaults)


def _closed_payment(**kw):
    defaults = dict(
        transaction_id='tx_1',
        payee=Merchant(name='Shop', id='s-1'),
        payment_amount=Amount(amount=1000, currency='USD'),
        payment_instrument=PaymentInstrument(id='pi-1', type='credit'),
    )
    defaults.update(kw)
    return PaymentMandate(**defaults)


def _checkout(merchant=None, line_items=None, **kw):
    """Build a Checkout object via CheckoutMandateChain."""
    checkout_jwt = make_checkout_jwt(
        merchant=merchant,
        line_items=line_items,
    )
    defaults = dict(checkout_jwt=checkout_jwt, checkout_hash='hash')
    defaults.update(kw)
    mandate = CheckoutMandate(**defaults)
    chain = CheckoutMandateChain(
        open_mandate=_open_checkout(),
        closed_mandate=mandate,
    )
    return chain.extract_parsed_checkout_object(checkout_jwt)


# ── merchant_matches (parameterized) ─────────────────────────────────────


@pytest.mark.parametrize(
    'candidate, target',
    [
        pytest.param(
            Merchant(id='m-1', name='A', website='https://a.com'),
            Merchant(id='m-1', name='B', website='https://b.com'),
            id='by_id',
        ),
        pytest.param(
            Merchant(id='', name='Shop', website='https://shop.com'),
            Merchant(id='', name='Shop', website='https://shop.com'),
            id='by_name_and_website',
        ),
        pytest.param(
            Merchant(id='m-1', name='A'),
            Merchant(id='m-1', name='B').model_dump(mode='json'),
            id='dict_target_by_id',
        ),
        pytest.param(
            Merchant(id='', name='Shop', website='https://shop.com'),
            Merchant(id='', name='Shop', website='https://shop.com').model_dump(
                mode='json'
            ),
            id='dict_target_by_name_and_website',
        ),
    ],
)
def test_merchant_matches(candidate, target):
    """Merchants that should match do match."""
    assert merchant_matches(candidate, target)


@pytest.mark.parametrize(
    'candidate, target',
    [
        pytest.param(
            Merchant(id='m-1', name='A'),
            Merchant(id='m-2', name='A'),
            id='different_id',
        ),
        pytest.param(
            Merchant(id='', name='Shop'),
            Merchant(id='', name='Shop'),
            id='name_only_without_website',
        ),
        pytest.param(
            Merchant(id='m-1', name='A'),
            Merchant(id='m-2', name='A').model_dump(mode='json'),
            id='dict_target_different_id',
        ),
        pytest.param(
            Merchant(id='', name='Shop', website=''),
            Merchant(id='', name='Shop', website=''),
            id='both_empty_id_and_empty_website',
        ),
    ],
)
def test_merchant_no_match(candidate, target):
    """Merchants that should not match do not match."""
    assert not merchant_matches(candidate, target)


# ── check_payment_constraints – empty constraints ────────────────────────


def test_payment_empty_constraints():
    """Empty constraints list produces no violations."""
    violations = check_payment_constraints(
        _open_payment(),
        _closed_payment(),
    )
    assert violations == []


# ── check_payment_constraints – amount / amount_range ────────────────────


def test_payment_amount_below_min():
    """Amount below minimum is a violation."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AmountRange(
                    min=1000,
                    max=5000,
                    currency='USD',
                ),
            ]
        ),
        _closed_payment(payment_amount=Amount(amount=500, currency='USD')),
    )
    assert len(violations) == 1
    assert 'below minimum' in violations[0]


def test_payment_amount_above_max():
    """Amount above maximum is a violation."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AmountRange(
                    min=1000,
                    max=5000,
                    currency='USD',
                ),
            ]
        ),
        _closed_payment(payment_amount=Amount(amount=6000, currency='USD')),
    )
    assert len(violations) == 1
    assert 'exceeds maximum' in violations[0]


def test_payment_amount_currency_mismatch():
    """Currency mismatch between constraint and payment is a violation."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AmountRange(max=50000, currency='USD'),
            ]
        ),
        _closed_payment(payment_amount=Amount(amount=1000, currency='EUR')),
    )
    assert any('Currency mismatch' in v for v in violations)


def test_payment_amount_no_min():
    """When min is absent, only max is checked."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AmountRange(max=2000, currency='USD'),
            ]
        ),
        _closed_payment(payment_amount=Amount(amount=1500, currency='USD')),
    )
    assert violations == []


# ── check_payment_constraints – amount boundary cases (parameterized) ────


@pytest.mark.parametrize(
    'constraint_min, constraint_max, payment_amount',
    [
        pytest.param(0, 5000, 0, id='zero_at_boundary'),
        pytest.param(1000, 5000, 1000, id='exact_min'),
        pytest.param(1000, 5000, 5000, id='exact_max'),
        pytest.param(1000, 999999999, 999999, id='very_large_max'),
    ],
)
def test_payment_amount_boundary_passes(
    constraint_min, constraint_max, payment_amount
):
    """Amount at or within boundary values passes."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AmountRange(
                    min=constraint_min,
                    max=constraint_max,
                    currency='USD',
                ),
            ]
        ),
        _closed_payment(
            payment_amount=Amount(amount=payment_amount, currency='USD')
        ),
    )
    assert violations == []


# ── check_payment_constraints – allowed_payee ────────────────────────────


def test_payment_allowed_payee_match_by_id():
    """Payee matching by id passes."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AllowedPayees(
                    allowed=[Merchant(id='s-1', name='Shop')],
                ),
            ]
        ),
        _closed_payment(payee=Merchant(id='s-1', name='Shop')),
    )
    assert violations == []


def test_payment_allowed_payee_not_in_list():
    """Payee not in allowed list is a violation."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AllowedPayees(
                    allowed=[Merchant(id='s-1', name='Shop')],
                ),
            ]
        ),
        _closed_payment(payee=Merchant(id='other', name='Other')),
    )
    assert any('not in allowed list' in v for v in violations)


def test_payment_multiple_constraints():
    """Multiple constraints are all evaluated."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AmountRange(max=500, currency='USD'),
                AllowedPayees(
                    allowed=[Merchant(id='s-1', name='Shop')],
                ),
            ]
        ),
        _closed_payment(
            payment_amount=Amount(amount=1000, currency='USD'),
            payee=Merchant(id='other', name='Other'),
        ),
    )
    assert any('exceeds maximum' in v for v in violations)
    assert any('not in allowed list' in v for v in violations)


# ── check_payment_constraints – payment_reference ────────────────────────


def test_payment_reference_match():
    """Payment reference matching passes."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                PaymentReference(
                    conditional_transaction_id='expected_hash',
                ),
            ]
        ),
        _closed_payment(),
        open_checkout_hash='expected_hash',
    )
    assert violations == []


def test_payment_reference_mismatch():
    """Payment reference mismatch is a violation."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                PaymentReference(
                    conditional_transaction_id='expected_hash',
                ),
            ]
        ),
        _closed_payment(),
        open_checkout_hash='wrong_hash',
    )
    assert len(violations) == 1
    assert 'PaymentReference mismatch' in violations[0]


def test_payment_reference_missing_context():
    """Missing open_checkout_hash is a violation.

    Evaluating PaymentReference requires open_checkout_hash to be provided.
    """
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                PaymentReference(
                    conditional_transaction_id='expected_hash',
                ),
            ]
        ),
        _closed_payment(),
        # open_checkout_hash omitted
    )
    assert len(violations) == 1
    assert 'open_checkout_hash is required' in violations[0]


# ── check_payment_constraints – allowed_payment_instrument ───────────────


def test_payment_allowed_payment_instrument_match():
    """Instrument in allowed list passes."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AllowedPaymentInstruments(
                    allowed=[
                        PaymentInstrument(id='pi-1', type='credit')
                    ],
                ),
            ]
        ),
        _closed_payment(
            payment_instrument=PaymentInstrument(id='pi-1', type='credit')
        ),
    )
    assert violations == []


def test_payment_allowed_payment_instrument_mismatch():
    """Instrument not listed is a violation."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AllowedPaymentInstruments(
                    allowed=[
                        PaymentInstrument(id='pi-1', type='credit')
                    ],
                ),
            ]
        ),
        _closed_payment(
            payment_instrument=PaymentInstrument(id='pi-other', type='credit')
        ),
    )
    assert any('not in allowed list' in v for v in violations)


# ── check_payment_constraints – budget ───────────────────────────────────


def test_payment_budget_within_limit():
    """Amount within budget passes."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                Budget(max=15.0, currency='USD'),  # 1500 cents
            ]
        ),
        _closed_payment(payment_amount=Amount(amount=1000, currency='USD')),
        mandate_context=MandateContext(total_amount=0, total_uses=0),
    )
    assert violations == []


def test_payment_budget_exceeds_limit():
    """Amount exceeding budget is a violation."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                Budget(max=5.0, currency='USD'),  # 500 cents
            ]
        ),
        _closed_payment(payment_amount=Amount(amount=1000, currency='USD')),
        mandate_context=MandateContext(total_amount=0, total_uses=0),
    )
    assert any('exceeds budget limit' in v for v in violations)


def test_payment_budget_cumulative_exceeds_limit():
    """Cumulative amount exceeding budget is a violation."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                Budget(max=15.0, currency='USD'),  # 1500 cents
            ]
        ),
        _closed_payment(payment_amount=Amount(amount=1000, currency='USD')),
        mandate_context=MandateContext(
            total_amount=600, total_uses=1, last_used_date=time.time()
        ),
    )
    assert any(
        'Cumulative spend 1600 exceeds budget limit 1500' in v
        for v in violations
    )


def test_payment_budget_currency_mismatch():
    """Currency mismatch in budget is a violation."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                Budget(max=10.0, currency='EUR'),
            ]
        ),
        _closed_payment(payment_amount=Amount(amount=1000, currency='USD')),
    )
    assert any('Budget currency mismatch' in v for v in violations)


def test_payment_budget_missing_context():
    """Budget fails if context is missing."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                Budget(max=10.0, currency='USD'),
            ]
        ),
        _closed_payment(payment_amount=Amount(amount=1000, currency='USD')),
        mandate_context=None,
    )
    assert any(
        'Missing mandate context required to evaluate budget' in v
        for v in violations
    )


# ── check_payment_constraints – execution_date ───────────────────────────


def test_payment_execution_date_within_window():
    """Execution date within window passes."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                ExecutionDate(not_before='2025-01-01', not_after='2025-12-31'),
            ]
        ),
        _closed_payment(execution_date='2025-06-01'),
    )
    assert violations == []


def test_payment_execution_date_before_window():
    """Execution date before window is a violation."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                ExecutionDate(not_before='2025-01-01', not_after='2025-12-31'),
            ]
        ),
        _closed_payment(execution_date='2024-12-31'),
    )
    assert any('before allowed window' in v for v in violations)


def test_payment_execution_date_after_window():
    """Execution date after window is a violation."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                ExecutionDate(not_before='2025-01-01', not_after='2025-12-31'),
            ]
        ),
        _closed_payment(execution_date='2026-01-01'),
    )
    assert any('after allowed window' in v for v in violations)


def test_payment_execution_date_missing_passes():
    """Missing execution date (immediate) passes."""
    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                ExecutionDate(not_before='2025-01-01', not_after='2025-12-31'),
            ]
        ),
        _closed_payment(execution_date=None),
    )
    assert violations == []


# ── check_payment_constraints – allowed_pisp ─────────────────────────────


def test_payment_allowed_pisp_match():
    """PISP in allowed list passes."""
    from ap2.sdk.generated.types.pisp import PISP

    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AllowedPisps(
                    allowed=[
                        PISP(
                            legal_name='PISP 1 Legal',
                            brand_name='PISP 1 Brand',
                            domain_name='pisp1.com',
                        )
                    ]
                ),
            ]
        ),
        _closed_payment(
            pisp=PISP(
                legal_name='PISP 1 Legal',
                brand_name='PISP 1 Brand',
                domain_name='pisp1.com',
            )
        ),
    )
    assert violations == []


def test_payment_allowed_pisp_mismatch():
    """PISP not in allowed list is a violation."""
    from ap2.sdk.generated.types.pisp import PISP

    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AllowedPisps(
                    allowed=[
                        PISP(
                            legal_name='PISP 1 Legal',
                            brand_name='PISP 1 Brand',
                            domain_name='pisp1.com',
                        )
                    ]
                ),
            ]
        ),
        _closed_payment(
            pisp=PISP(
                legal_name='Other PISP Legal',
                brand_name='Other PISP Brand',
                domain_name='otherpisp.com',
            )
        ),
    )
    assert any('not in allowed list' in v for v in violations)


def test_payment_allowed_pisp_missing():
    """Missing PISP when AllowedPisps constraint is present is a violation."""
    from ap2.sdk.generated.types.pisp import PISP

    violations = check_payment_constraints(
        _open_payment(
            constraints=[
                AllowedPisps(
                    allowed=[
                        PISP(
                            legal_name='PISP 1 Legal',
                            brand_name='PISP 1 Brand',
                            domain_name='pisp1.com',
                        )
                    ]
                ),
            ]
        ),
        _closed_payment(pisp=None),
    )
    assert any('Missing PISP in closed mandate' in v for v in violations)


def test_preset_payee_match():
    """Pre-set payee matching between open and closed mandates passes."""
    violations = check_preset_payment_claims(
        _open_payment(payee=Merchant(id='s-1', name='Shop')),
        _closed_payment(payee=Merchant(id='s-1', name='Shop')),
    )
    assert violations == []


def test_preset_payee_mismatch():
    """Pre-set payee mismatch between open and closed mandates is a violation."""
    violations = check_preset_payment_claims(
        _open_payment(payee=Merchant(id='s-1', name='Shop')),
        _closed_payment(payee=Merchant(id='s-2', name='Other')),
    )
    assert any('Pre-set payee mismatch' in v for v in violations)


def test_preset_amount_mismatch():
    """Pre-set amount mismatch is a violation."""
    violations = check_preset_payment_claims(
        _open_payment(payment_amount=Amount(amount=1000, currency='USD')),
        _closed_payment(payment_amount=Amount(amount=2000, currency='USD')),
    )
    assert any('Pre-set amount mismatch' in v for v in violations)


def test_preset_payment_instrument_mismatch():
    """Pre-set payment_instrument mismatch is a violation."""
    violations = check_preset_payment_claims(
        _open_payment(
            payment_instrument=PaymentInstrument(id='pi-1', type='credit'),
        ),
        _closed_payment(
            payment_instrument=PaymentInstrument(id='pi-2', type='debit'),
        ),
    )
    assert any('Pre-set payment_instrument mismatch' in v for v in violations)


def test_preset_execution_date_mismatch():
    """Pre-set execution_date mismatch is a violation."""
    violations = check_preset_payment_claims(
        _open_payment(execution_date='2025-01-01'),
        _closed_payment(execution_date='2025-12-31'),
    )
    assert any('Pre-set execution_date mismatch' in v for v in violations)


def test_preset_claims_not_set_passes():
    """When no pre-set claims are in the open mandate, nothing to check."""
    violations = check_preset_payment_claims(
        _open_payment(),
        _closed_payment(),
    )
    assert violations == []


# ── check_checkout_constraints – empty ───────────────────────────────────


def test_checkout_empty_constraints():
    """Empty constraints list produces no violations."""
    violations = check_checkout_constraints(
        _open_checkout(),
        _checkout(),
    )
    assert violations == []


# ── check_checkout_constraints – allowed_merchants ───────────────────────


def test_checkout_allowed_merchant_match():
    """Merchant in allowed list passes (merchant extracted from checkout_jwt)."""
    merchant = Merchant(id='m-1', name='Store')
    checkout = _checkout(merchant=merchant)

    violations = check_checkout_constraints(
        _open_checkout(
            constraints=[
                AllowedMerchants(
                    allowed=[merchant],
                ),
            ]
        ),
        checkout,
    )
    assert violations == []


def test_checkout_merchant_not_in_list():
    """Merchant not in allowed list is a violation."""
    checkout = _checkout(
        merchant=Merchant(id='m-999', name='Evil'),
    )

    violations = check_checkout_constraints(
        _open_checkout(
            constraints=[
                AllowedMerchants(
                    allowed=[Merchant(id='m-1', name='Store')],
                ),
            ]
        ),
        checkout,
    )
    assert any('not in allowed list' in v for v in violations)


def test_checkout_missing_merchant():
    """Missing merchant in checkout is a violation."""
    checkout = _checkout()

    violations = check_checkout_constraints(
        _open_checkout(
            constraints=[
                AllowedMerchants(
                    allowed=[Merchant(id='m-1', name='Store')],
                ),
            ]
        ),
        checkout,
    )
    assert any('Missing merchant' in v for v in violations)
