"""Tests for PaymentMandateChain (ap2.sdk.payment_mandate_chain)."""

import pytest

from ap2.sdk.constraints import check_payment_constraints
from ap2.sdk.generated.open_payment_mandate import (
    AmountRange,
    OpenPaymentMandate,
    PaymentReference,
)
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.payment_mandate_chain import PaymentMandateChain
from ap2.tests.conftest import make_cnf, sample_payment_mandate


# Two DISTINCT artifacts: the hash of the OPEN checkout mandate the user
# authorized, and the hash of the Checkout JWT actually being processed.
_OPEN_CHECKOUT_HASH = 'sha256-open-checkout-mandate'
_REAL_CHECKOUT_JWT_HASH = 'sha256-real-checkout-jwt'


def _chain_with_mismatched_closed_binding() -> PaymentMandateChain:
    """Open mandate authorizes one checkout; closed mandate binds another JWT."""
    return PaymentMandateChain(
        open_mandate=OpenPaymentMandate(
            constraints=[
                PaymentReference(conditional_transaction_id=_OPEN_CHECKOUT_HASH)
            ],
            cnf={'jwk': {'kty': 'EC'}},
        ),
        closed_mandate=sample_payment_mandate(
            transaction_id='sha256-a-DIFFERENT-checkout-jwt'
        ),
    )


def test_payment_chain_constraint_violation(
    user_key,
    user_public_key,
    agent_key,
    holder,
):
    """Amount exceeding the open mandate's max triggers a constraint error."""
    open_tok = holder.create(
        payloads=[
            OpenPaymentMandate(
                constraints=[
                    AmountRange(
                        currency='USD',
                        max=5000,
                    ),
                ],
                cnf=make_cnf(agent_key),
            )
        ],
        issuer_key=user_key,
    )
    tok_chain = holder.present(
        holder_key=agent_key,
        mandate_token=open_tok,
        payloads=[
            sample_payment_mandate(
                payment_amount=Amount(amount=10000, currency='USD')
            )
        ],
        aud='merchant',
        nonce='merchant-nonce',
    )

    payloads = holder.verify(
        token=tok_chain,
        key_or_provider=lambda _token: user_public_key,
    )
    chain = PaymentMandateChain.parse(payloads)
    # sample_payment_mandate() binds transaction_id='tx_1'; supply it so this
    # stays a pure amount-constraint test and not a binding failure too.
    violations = chain.verify(expected_transaction_id='tx_1')
    assert any('exceeds maximum' in v for v in violations)


def test_payment_chain_parse_wrong_payload_count():
    """parse() requires exactly 2 payloads."""
    with pytest.raises(ValueError, match='exactly 2'):
        PaymentMandateChain.parse([{}])


def test_payment_chain_transaction_id_mismatch(
    user_key,
    user_public_key,
    agent_key,
    holder,
):
    """Payment mandate rejected if expected transaction ID doesn't match."""
    open_tok = holder.create(
        payloads=[OpenPaymentMandate(constraints=[], cnf=make_cnf(agent_key))],
        issuer_key=user_key,
    )
    tok_chain = holder.present(
        holder_key=agent_key,
        mandate_token=open_tok,
        payloads=[sample_payment_mandate(transaction_id='tx_actual')],
        aud='merchant',
        nonce='merchant-nonce',
    )
    payloads = holder.verify(
        token=tok_chain,
        key_or_provider=lambda _token: user_public_key,
    )
    chain = PaymentMandateChain.parse(payloads)

    violations = chain.verify(expected_transaction_id='tx_expected')
    assert len(violations) == 1
    assert 'Payment transaction_id mismatch' in violations[0]


def test_full_payment_end_to_end(
    user_key,
    user_public_key,
    agent_key,
    holder,
):
    """Full end-to-end: provider key verifies open, cnf verifies closed."""
    open_tok = holder.create(
        payloads=[
            OpenPaymentMandate(
                constraints=[],
                cnf=make_cnf(agent_key),
            )
        ],
        issuer_key=user_key,
    )
    tok_chain = holder.present(
        holder_key=agent_key,
        mandate_token=open_tok,
        payloads=[sample_payment_mandate()],
        aud='merchant',
        nonce='merchant-nonce',
    )

    payloads = holder.verify(
        token=tok_chain,
        key_or_provider=lambda _token: user_public_key,
    )
    chain = PaymentMandateChain.parse(payloads)
    # A legitimate verifier asserts the closed checkout binding (the JWT hash it
    # is processing); sample_payment_mandate() uses transaction_id='tx_1'.
    violations = chain.verify(expected_transaction_id='tx_1')
    assert violations == []
    assert chain.open_mandate.vct == 'mandate.payment.open.1'
    assert chain.closed_mandate.transaction_id == 'tx_1'


# --- #328: closed Payment Mandate transaction_id binding must fail closed ---


def test_closed_binding_skipped_is_now_flagged_by_default():
    """#328 repro: a mismatched closed transaction_id must NOT pass silently.

    Verifying with only ``expected_open_checkout_hash`` used to return ``[]``
    even though the closed mandate binds a different Checkout JWT. After the
    fix the missing closed-binding check is itself a violation (fail closed).
    """
    chain = _chain_with_mismatched_closed_binding()
    violations = chain.verify(expected_open_checkout_hash=_OPEN_CHECKOUT_HASH)
    assert violations != [], (
        'closed transaction_id binding was silently skipped (#328)'
    )
    assert any('transaction_id' in v for v in violations)


def test_default_verify_protects_legitimate_caller():
    """A caller using the bare default API is protected, not silently passed.

    Worst case: the open mandate carries NO constraints, so nothing else fires.
    Today ``verify()`` returns [] (total bypass). It must fail closed instead,
    because it cannot confirm the closed Payment Mandate's checkout binding.
    """
    chain = PaymentMandateChain(
        open_mandate=OpenPaymentMandate(
            constraints=[], cnf={'jwk': {'kty': 'EC'}}
        ),
        closed_mandate=sample_payment_mandate(transaction_id='tx_whatever'),
    )
    assert chain.verify() != []


def test_matching_closed_binding_passes():
    """Legit flow is never trapped: correct expected_transaction_id passes."""
    chain = PaymentMandateChain(
        open_mandate=OpenPaymentMandate(
            constraints=[
                PaymentReference(conditional_transaction_id=_OPEN_CHECKOUT_HASH)
            ],
            cnf={'jwk': {'kty': 'EC'}},
        ),
        closed_mandate=sample_payment_mandate(
            transaction_id=_REAL_CHECKOUT_JWT_HASH
        ),
    )
    violations = chain.verify(
        expected_transaction_id=_REAL_CHECKOUT_JWT_HASH,
        expected_open_checkout_hash=_OPEN_CHECKOUT_HASH,
    )
    assert violations == []


def test_mismatched_closed_binding_still_flagged_when_supplied():
    """The supplied-correctly control keeps flagging a real mismatch."""
    chain = _chain_with_mismatched_closed_binding()
    violations = chain.verify(
        expected_transaction_id=_REAL_CHECKOUT_JWT_HASH,
        expected_open_checkout_hash=_OPEN_CHECKOUT_HASH,
    )
    assert any('transaction_id mismatch' in v for v in violations)


def test_blank_expected_transaction_id_fails_closed():
    """A blank/empty expected_transaction_id binds nothing -> fail closed.

    ``transaction_id`` has no min_length, so a mandate can carry ''. A caller
    that passes '' (e.g. ``data.get('checkout_jwt_hash', '')``) must not be
    treated as having confirmed the binding.
    """
    chain = PaymentMandateChain(
        open_mandate=OpenPaymentMandate(constraints=[], cnf={'jwk': {}}),
        closed_mandate=sample_payment_mandate(transaction_id=''),
    )
    for blank in ('', '   '):
        violations = chain.verify(expected_transaction_id=blank)
        assert violations != [], f'blank {blank!r} was accepted'
        assert any('binding not verified' in v for v in violations)


def test_constraints_only_honest_exit_is_check_payment_constraints():
    """The bounded honest exit for non-settlement checks is a distinct API.

    ``verify()`` fails closed with no binding, but a caller that genuinely only
    wants constraint evaluation calls ``check_payment_constraints`` directly --
    a self-describing entry point that cannot be mistaken for full verify().
    """
    chain = PaymentMandateChain(
        open_mandate=OpenPaymentMandate(
            constraints=[AmountRange(currency='USD', max=5000)],
            cnf={'jwk': {'kty': 'EC'}},
        ),
        closed_mandate=sample_payment_mandate(
            payment_amount=Amount(amount=10000, currency='USD'),
        ),
    )
    # Full verify() fails closed (no checkout binding supplied).
    assert chain.verify() != []
    # The honest constraints-only exit reports the amount violation and adds
    # no spurious binding violation.
    constraint_violations = check_payment_constraints(
        chain.open_mandate, chain.closed_mandate
    )
    assert any('exceeds maximum' in v for v in constraint_violations)
    assert not any('binding not verified' in v for v in constraint_violations)
