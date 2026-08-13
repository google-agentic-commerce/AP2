"""Tests for extensible payment instrument fields."""

from ap2.sdk.generated.open_payment_mandate import (
    AllowedPaymentInstruments,
    OpenPaymentMandate,
)
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.payment_mandate_chain import PaymentMandateChain
from ap2.tests.conftest import make_cnf, sample_payment_mandate


def test_type_specific_fields_survive_signed_payment_mandate_roundtrip(
    user_key,
    user_public_key,
    agent_key,
    holder,
):
    """Type-specific instrument fields remain signed and typed after verify."""
    instrument = PaymentInstrument(
        id='x402-base-sepolia-usdc',
        type='x402',
        payee_address='0x1111111111111111111111111111111111111111',
        facilitator='https://facilitator.example',
    )
    expected_extension = {
        'payee_address': '0x1111111111111111111111111111111111111111',
        'facilitator': 'https://facilitator.example',
    }

    instrument_dump = instrument.model_dump(exclude_none=True)
    assert {
        key: instrument_dump[key] for key in expected_extension
    } == expected_extension

    closed_mandate = sample_payment_mandate(payment_instrument=instrument)
    nested_dump = closed_mandate.model_dump(exclude_none=True)
    assert {
        key: nested_dump['payment_instrument'][key]
        for key in expected_extension
    } == expected_extension

    open_token = holder.create(
        payloads=[
            OpenPaymentMandate(
                constraints=[
                    AllowedPaymentInstruments(allowed=[instrument]),
                ],
                cnf=make_cnf(agent_key),
            )
        ],
        issuer_key=user_key,
    )
    signed_chain = holder.present(
        holder_key=agent_key,
        mandate_token=open_token,
        payloads=[closed_mandate],
        aud='merchant',
        nonce='merchant-nonce',
    )

    verified_payloads = holder.verify(
        token=signed_chain,
        key_or_provider=lambda _token: user_public_key,
    )
    parsed_chain = PaymentMandateChain.parse(verified_payloads)

    assert parsed_chain.verify() == []
    parsed_instrument = parsed_chain.closed_mandate.payment_instrument
    assert {
        key: parsed_instrument.model_dump(exclude_none=True)[key]
        for key in expected_extension
    } == expected_extension
    assert parsed_instrument.payee_address == expected_extension['payee_address']
    assert parsed_instrument.facilitator == expected_extension['facilitator']
