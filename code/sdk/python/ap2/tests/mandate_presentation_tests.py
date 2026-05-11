"""Tests for mandate presentation behavior."""

import base64
import json

import pytest

from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.mandate import MandateClient
from ap2.tests.conftest import make_cnf
from jwcrypto.jwk import JWK


def _decode_jwt_payload(token: str) -> dict:
    """Decode the JWT payload section without signature verification."""
    jwt_part = token.split('~', maxsplit=1)[0]
    payload_b64 = jwt_part.split('.')[1]
    padded = payload_b64 + '=' * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def test_present_closed_mandate_omits_kb_jwt(issuer_key):
    """Test that present does not append KB-JWT for closed mandates."""
    client = MandateClient()

    # 1. Create an Open Mandate
    holder_key = JWK.generate(kty='EC', crv='P-256')
    open_payload = OpenPaymentMandate(
        constraints=[],
        cnf=make_cnf(holder_key),
    )
    open_jwt = client.create(
        payloads=[open_payload],
        issuer_key=issuer_key,
    )

    # 2. Create a Closed Mandate using present
    closed_payload = PaymentMandate(
        transaction_id='tx_456',
        payee=Merchant(name='Shop', id='shop_id'),
        payment_amount=Amount(amount=5000, currency='USD'),
        payment_instrument=PaymentInstrument(id='123', type='credit'),
    )

    nonce = 'random-nonce-123'
    aud = 'https://pay.google.com'

    closed_jwt = client.present(
        holder_key=holder_key,
        mandate_token=open_jwt,
        payloads=[closed_payload],
        nonce=nonce,
        aud=aud,
    )

    parts = closed_jwt.split('~')
    assert len(parts) > 1  # Should have disclosures

    # If it ends with '~', the last part after split will be empty.
    # This indicates no KB-JWT followed it.
    assert parts[-1] == ''

    # The second to last part should be a disclosure, not a JWT.
    assert len(parts[-2].split('.')) != 3


def test_present_open_mandate_requires_aud_and_nonce(issuer_key):
    """present() with a non-closed payload raises ValueError if aud or nonce is missing."""
    client = MandateClient()
    holder_key = JWK.generate(kty='EC', crv='P-256')
    open_payload = OpenPaymentMandate(constraints=[], cnf=make_cnf(holder_key))
    open_jwt = client.create(payloads=[open_payload], issuer_key=issuer_key)

    next_key = JWK.generate(kty='EC', crv='P-256')
    delegation_payload = OpenPaymentMandate(
        constraints=[], cnf=make_cnf(next_key)
    )

    with pytest.raises(
        ValueError,
        match='aud and nonce are required for KB-SD-JWT hops',
    ):
        client.present(
            holder_key=holder_key,
            mandate_token=open_jwt,
            payloads=[delegation_payload],
            aud='https://cp-agent.example',
            # nonce missing
        )

    with pytest.raises(
        ValueError,
        match='aud and nonce are required for KB-SD-JWT hops',
    ):
        client.present(
            holder_key=holder_key,
            mandate_token=open_jwt,
            payloads=[delegation_payload],
            nonce='some-nonce',
            # aud missing
        )


def test_present_closed_mandate_injects_binding_claims_when_provided(
    issuer_key,
):
    """Closed mandate KB-SD-JWT injects aud/nonce when explicitly provided.

    Per dSD-JWT spec §5.1.4, KB-SD-JWTs should include aud and nonce.
    When the caller passes them to present(), they are embedded in the payload.
    iat is always present for delegation hops.
    """
    client = MandateClient()
    holder_key = JWK.generate(kty='EC', crv='P-256')
    open_payload = OpenPaymentMandate(constraints=[], cnf=make_cnf(holder_key))
    open_jwt = client.create(payloads=[open_payload], issuer_key=issuer_key)

    closed_payload = PaymentMandate(
        transaction_id='tx_789',
        payee=Merchant(name='Shop', id='shop_id'),
        payment_amount=Amount(amount=1000, currency='USD'),
        payment_instrument=PaymentInstrument(id='pi-1', type='credit'),
    )
    chain = client.present(
        holder_key=holder_key,
        mandate_token=open_jwt,
        payloads=[closed_payload],
        nonce='merchant-nonce',
        aud='https://merchant.example',
    )

    closed_segment = chain.rsplit('~~', 1)[-1]
    decoded = _decode_jwt_payload(closed_segment)
    assert decoded['aud'] == 'https://merchant.example'
    assert decoded['nonce'] == 'merchant-nonce'
    assert 'iat' in decoded


def test_present_closed_mandate_omits_binding_claims_when_not_provided(
    issuer_key,
):
    """Closed mandate KB-SD-JWT requires and includes aud/nonce."""
    client = MandateClient()
    holder_key = JWK.generate(kty='EC', crv='P-256')
    open_payload = OpenPaymentMandate(constraints=[], cnf=make_cnf(holder_key))
    open_jwt = client.create(payloads=[open_payload], issuer_key=issuer_key)

    closed_payload = PaymentMandate(
        transaction_id='tx_789',
        payee=Merchant(name='Shop', id='shop_id'),
        payment_amount=Amount(amount=1000, currency='USD'),
        payment_instrument=PaymentInstrument(id='pi-1', type='credit'),
    )
    chain = client.present(
        holder_key=holder_key,
        mandate_token=open_jwt,
        payloads=[closed_payload],
        aud='merchant',
        nonce='merchant-nonce',
    )

    closed_segment = chain.rsplit('~~', 1)[-1]
    decoded = _decode_jwt_payload(closed_segment)
    assert decoded['aud'] == 'merchant'
    assert decoded['nonce'] == 'merchant-nonce'
    assert 'iat' in decoded
