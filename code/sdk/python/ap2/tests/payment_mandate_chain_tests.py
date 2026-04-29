"""Tests for PaymentMandateChain (ap2.sdk.payment_mandate_chain)."""

import pytest

from ap2.sdk.generated.open_payment_mandate import (
    AmountRange,
    OpenPaymentMandate,
)
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.payment_mandate_chain import PaymentMandateChain
from ap2.tests.conftest import make_cnf, sample_payment_mandate


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
    violations = chain.verify()
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
    violations = chain.verify()
    assert violations == []
    assert chain.open_mandate.vct == 'mandate.payment.open.1'
    assert chain.closed_mandate.transaction_id == 'tx_1'
