"""Round-trip tests for type-specific PaymentInstrument extension fields.

The AP2 specification states that additional properties MAY be defined for a
specific Payment Instrument ``type`` (specification.md, Payment Instrument).
The x402 instrument type carries ``payee_address`` and ``facilitator``. These
fields must survive the full sign -> parse -> verify round trip, because the
signed Payment Mandate is the sole authorization the x402 Credential Provider
acts on. If they are dropped before signing, the Credential Provider reads a
missing ``payee_address`` and falls back to a default payout address and a
hard-coded amount -- a fail-open on a payment path (issue #299 item 1).
"""

from __future__ import annotations

from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.mandate import SdJwtMandate
from ap2.sdk.payment_mandate_chain import PaymentMandateChain
from ap2.sdk.sdjwt import sd_jwt
from ap2.sdk.sdjwt.common import delegate_claims_from_model
from ap2.tests.conftest import make_cnf
from cryptography.hazmat.primitives.asymmetric import ec


_X402_PAYEE = '0xAbCd000000000000000000000000000000000001'
_X402_FACILITATOR = 'https://facilitator.example'
_SIGNED_AMOUNT = 199

# Sentinels standing in for the x402 Credential Provider fallbacks
# (server.py L148-160): a mismatch means the CP authorized fabricated values.
_DEFAULT_ADDR = '0x000000000000000000000000000000000000dead'
_FALLBACK_AMOUNT = 1250


def _x402_instrument() -> PaymentInstrument:
    return PaymentInstrument(
        id='x402-instrument-1',
        type='x402',
        payee_address=_X402_PAYEE,
        facilitator=_X402_FACILITATOR,
    )


def _closed_payment_mandate() -> PaymentMandate:
    return PaymentMandate(
        transaction_id='tx_x402',
        payee=Merchant(name='Shop', id='s-1'),
        payment_amount=Amount(amount=_SIGNED_AMOUNT, currency='USD'),
        payment_instrument=_x402_instrument(),
    )


def _extract_like_x402_cp(chain: PaymentMandateChain):
    """Verbatim mirror of x402_credentials_provider_mcp/server.py L148-160.

    Any deviation from the signed values here is the fail-open being exercised.
    """
    try:
        payee_address = chain.closed_mandate.payment_instrument.payee_address
        amount_cents = chain.closed_mandate.payment_amount.amount
        if not payee_address:
            payee_address = _DEFAULT_ADDR
    except AttributeError:
        payee_address = _DEFAULT_ADDR
        amount_cents = _FALLBACK_AMOUNT
    return payee_address, amount_cents


# ── Root cause: the pre-sign serialization drops the extension fields ──────


def test_model_dump_preserves_type_specific_extension_fields():
    """``model_dump`` (the pre-sign step) must keep x402 extension fields."""
    dumped = _x402_instrument().model_dump()
    assert dumped.get('payee_address') == _X402_PAYEE
    assert dumped.get('facilitator') == _X402_FACILITATOR


def test_delegate_claims_preserve_type_specific_extension_fields():
    """The delegate claims that actually get signed must carry the fields."""
    claims = delegate_claims_from_model(_x402_instrument())
    assert claims.get('payee_address') == _X402_PAYEE
    assert claims.get('facilitator') == _X402_FACILITATOR


# ── Full sign -> parse -> verify round trip ────────────────────────────────


def test_x402_extensions_survive_sign_verify_roundtrip(
    issuer_key, issuer_public_key
):
    """x402 extension fields survive create -> verify -> typed parse."""
    issuer = sd_jwt.create(
        payload=_closed_payment_mandate(), issuer_key=issuer_key
    )
    parsed = SdJwtMandate.from_sd_jwt(
        issuer.sd_jwt_issuance, issuer_public_key, PaymentMandate
    )
    instrument = parsed.mandate_payload.payment_instrument
    assert instrument.payee_address == _X402_PAYEE
    assert instrument.facilitator == _X402_FACILITATOR


# ── Kill-test: the x402 Credential Provider fail-open ──────────────────────


def test_x402_cp_sources_verified_destination_and_amount_not_fallback(
    issuer_key, issuer_public_key
):
    """After the round trip, the CP must read verified values, never fallbacks.

    Kill-test for the payment-path fail-open (issue #299 item 1): mirrors the
    Credential Provider's extraction. Without preserved extension fields the
    ``payee_address`` access raises ``AttributeError`` and the CP authorizes a
    default destination plus the hard-coded ``1250`` amount.
    """
    dummy = ec.generate_private_key(ec.SECP256R1())
    open_mandate = OpenPaymentMandate(
        constraints=[], cnf=make_cnf(dummy.public_key())
    )
    issuer = sd_jwt.create(
        payload=_closed_payment_mandate(), issuer_key=issuer_key
    )
    parsed = SdJwtMandate.from_sd_jwt(
        issuer.sd_jwt_issuance, issuer_public_key, PaymentMandate
    )
    chain = PaymentMandateChain(
        open_mandate=open_mandate, closed_mandate=parsed.mandate_payload
    )

    payee_address, amount_cents = _extract_like_x402_cp(chain)

    assert payee_address == _X402_PAYEE, (
        'x402 CP fell back to the default payout address instead of the '
        'verified, signed destination'
    )
    assert amount_cents == _SIGNED_AMOUNT
    assert amount_cents != _FALLBACK_AMOUNT, (
        'x402 CP authorized the hard-coded 1250 fallback amount'
    )
