"""Tests for the MandateClient facade (``ap2.sdk.mandate.MandateClient``)."""

import base64
import json

import pytest

from ap2.sdk.disclosure_metadata import (
    DisclosureMetadata,
    sd_claims_to_disclose,
)
from ap2.sdk.generated.checkout_mandate import CheckoutMandate
from ap2.sdk.generated.open_checkout_mandate import (
    AllowedMerchants,
    Item,
    LineItemRequirements,
    LineItems,
    OpenCheckoutMandate,
)
from ap2.sdk.generated.open_payment_mandate import (
    AllowedPayees,
    AmountRange,
    OpenPaymentMandate,
)
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.mandate import MandateClient
from ap2.sdk.sdjwt import compute_sd_hash, parse_token
from ap2.tests.conftest import make_cnf
from cryptography.hazmat.primitives.asymmetric import ec
from jwcrypto.jwk import JWK


def _decode_jwt_header(token: str) -> dict:
    jwt_part = token.split('~', maxsplit=1)[0]
    header_b64 = jwt_part.split('.')[0]
    padded = header_b64 + '=' * (-len(header_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def test_mandate_verification_unsupported_format_raises_error(
    issuer_key,
    issuer_public_key,
):
    """Verifying a token without the SD-JWT ~ separator raises NotImplementedError."""
    token = 'invalid_token_without_tilde'

    with pytest.raises(
        NotImplementedError,
        match='Only SD-JWT formats are currently supported for verification',
    ):
        MandateClient().verify(
            token=token,
            key_or_provider=issuer_public_key,
            payload_type=PaymentMandate,
        )


def test_holder_presentation_nonce_without_holder_key():
    """Providing nonce/aud without a holder_key raises ValueError."""
    issuer_priv = ec.generate_private_key(ec.SECP256R1())
    client = MandateClient()

    dummy_key = ec.generate_private_key(ec.SECP256R1())
    payload = OpenPaymentMandate(
        constraints=[],
        cnf=make_cnf(dummy_key.public_key()),
    )
    jwk_key = JWK.from_pyca(issuer_priv)
    sd_jwt_str = client.create(payloads=[payload], issuer_key=jwk_key)

    with pytest.raises(ValueError, match='nonce and aud require'):
        MandateClient().present(
            holder_key=None,
            mandate_token=sd_jwt_str,
            payloads=[payload],
            claims_to_disclose={},
            nonce='n',
            aud='a',
        )


def test_compute_sd_hash_of_issued_mandate(issuer_key):
    """compute_sd_hash of an issued mandate is a valid non-empty string."""
    payload = PaymentMandate(
        transaction_id='tx_hash',
        payee=Merchant(name='Shop', id='s-1'),
        payment_amount=Amount(amount=1000, currency='USD'),
        payment_instrument=PaymentInstrument(id='pi-1', type='credit'),
    )
    client = MandateClient()
    sd_jwt_str = client.create(payloads=[payload], issuer_key=issuer_key)

    h = compute_sd_hash(parse_token(sd_jwt_str))
    assert isinstance(h, str)
    assert len(h) > 0


# ── from_model / auto-SD tests ─────────────────────────────────────────


def test_from_model_checkout_mandate():
    """from_model detects x-selectively-disclosable-field on checkout_jwt."""
    model = CheckoutMandate(checkout_jwt='jwt', checkout_hash='hash')
    meta = DisclosureMetadata.from_model(model)
    assert meta is not None
    assert 'checkout_jwt' in meta.sd_keys
    assert 'checkout_hash' not in meta.sd_keys


def test_from_model_payment_mandate_no_annotations():
    """from_model returns None for PaymentMandate (no SD annotations)."""
    model = PaymentMandate(
        transaction_id='tx_1',
        payee=Merchant(name='Shop', id='s-1'),
        payment_amount=Amount(amount=1000, currency='USD'),
        payment_instrument=PaymentInstrument(id='pi-1', type='credit'),
    )
    assert DisclosureMetadata.from_model(model) is None


def test_from_model_open_payment_mandate_recursive():
    """from_model recurses into constraints to find AllowedPayee SD."""
    dummy_key = ec.generate_private_key(ec.SECP256R1())
    model = OpenPaymentMandate(
        constraints=[
            AmountRange(currency='USD', max=5000),
            AllowedPayees(
                allowed=[Merchant(id='m-1', name='Shop')],
            ),
        ],
        cnf=make_cnf(dummy_key.public_key()),
    )
    meta = DisclosureMetadata.from_model(model)
    assert meta is not None
    assert 'constraints' in meta.children
    constraint_meta = meta.children['constraints']
    assert 1 in constraint_meta.array_children
    payee_meta = constraint_meta.array_children[1]
    assert 'allowed' in payee_meta.children
    assert payee_meta.children['allowed'].disclose_all is True


def test_from_model_open_checkout_mandate_nested_line_items():
    """from_model reaches acceptable_items 4 levels deep."""
    dummy_key = ec.generate_private_key(ec.SECP256R1())
    model = OpenCheckoutMandate(
        constraints=[
            LineItems(
                items=[
                    LineItemRequirements(
                        id='line_1',
                        acceptable_items=[Item(id='SKU-1', title='Widget')],
                        quantity=1,
                    ),
                ]
            ),
            AllowedMerchants(
                allowed=[Merchant(id='m-1', name='Shop')],
            ),
        ],
        cnf=make_cnf(dummy_key.public_key()),
    )
    meta = DisclosureMetadata.from_model(model)
    assert meta is not None
    c = meta.children['constraints']
    line_items_meta = c.array_children[0]
    assert 'items' in line_items_meta.children
    items_meta = line_items_meta.children['items']
    assert 0 in items_meta.array_children
    assert (
        items_meta.array_children[0].children['acceptable_items'].disclose_all
    )


def test_sd_claims_to_disclose_checkout_mandate():
    """sd_claims_to_disclose returns the right dict for CheckoutMandate."""
    model = CheckoutMandate(checkout_jwt='jwt', checkout_hash='hash')
    claims = sd_claims_to_disclose(model)
    assert claims == {'checkout_jwt': True}


def test_sd_claims_to_disclose_open_payment():
    """sd_claims_to_disclose returns nested structure for AllowedPayee."""
    dummy_key = ec.generate_private_key(ec.SECP256R1())
    model = OpenPaymentMandate(
        constraints=[
            AmountRange(currency='USD', max=5000),
            AllowedPayees(
                allowed=[
                    Merchant(id='m-1', name='A'),
                    Merchant(id='m-2', name='B'),
                ],
            ),
        ],
        cnf=make_cnf(dummy_key.public_key()),
    )
    claims = sd_claims_to_disclose(model)
    assert 'constraints' in claims
    assert claims['constraints'][1] == {'allowed': [True, True]}


# ── claims_to_disclose: None vs {} vs explicit ─────────────────────────


def test_present_creates_closed_mandate_with_key_binding(
    issuer_key, issuer_public_key
):
    """Test that present can create a closed mandate bound to an open mandate with KB."""
    client = MandateClient()

    # 1. Create an Open Mandate
    holder_key = ec.generate_private_key(ec.SECP256R1())
    open_payload = OpenPaymentMandate(
        constraints=[],
        cnf=make_cnf(holder_key.public_key()),
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

    # present takes holder_key (to sign closed mandate)
    # and open_jwt (as mandate_token to bind to)
    holder_jwk = JWK.from_pyca(holder_key)
    closed_jwt = client.present(
        holder_key=holder_jwk,
        mandate_token=open_jwt,
        payloads=[closed_payload],
        nonce=nonce,
        aud=aud,
    )

    assert closed_jwt is not None
    assert '~' in closed_jwt

    # Verify that the closed mandate is bound to the open mandate
    # using the new unified verify API!

    key_calls = 0

    def key_provider(kid):
        nonlocal key_calls
        key_calls += 1
        if key_calls == 1:
            return issuer_public_key
        return holder_key.public_key()

    payloads = client.verify(
        token=closed_jwt,
        key_or_provider=key_provider,
        expected_nonce=nonce,
        expected_aud=aud,
    )

    assert len(payloads) == 2
    assert payloads[1]['transaction_id'] == 'tx_456'


# ── present() dispatches to the right primitive per payload shape ────────


def test_present_open_payload_creates_intermediate_kb_sd_jwt(issuer_key):
    """An open payload (has ``cnf``) creates an intermediate KB-SD-JWT."""
    holder_key = JWK.generate(kty='EC', crv='P-256')
    next_key = JWK.generate(kty='EC', crv='P-256')
    open_payload = OpenPaymentMandate(constraints=[], cnf=make_cnf(holder_key))
    open_jwt = MandateClient().create(
        payloads=[open_payload], issuer_key=issuer_key
    )

    delegation_payload = OpenPaymentMandate(
        constraints=[], cnf=make_cnf(next_key)
    )
    result = MandateClient().present(
        holder_key=holder_key,
        mandate_token=open_jwt,
        payloads=[delegation_payload],
        aud='https://cp-agent.example',
        nonce='n-1',
    )
    # New hop's header is typ=kb+sd-jwt+kb.
    new_hop = result.split('~~', 1)[1]
    assert _decode_jwt_header(new_hop)['typ'] == 'kb+sd-jwt+kb'


def test_present_closed_payload_creates_terminal_kb_sd_jwt(issuer_key):
    """A closed payload (no ``cnf``) creates a terminal KB-SD-JWT."""
    holder_key = JWK.generate(kty='EC', crv='P-256')
    open_payload = OpenPaymentMandate(constraints=[], cnf=make_cnf(holder_key))
    open_jwt = MandateClient().create(
        payloads=[open_payload], issuer_key=issuer_key
    )

    closed_payload = PaymentMandate(
        transaction_id='tx_dispatch',
        payee=Merchant(id='m-1', name='Shop'),
        payment_amount=Amount(amount=10, currency='USD'),
        payment_instrument=PaymentInstrument(id='pi-1', type='credit'),
    )
    result = MandateClient().present(
        holder_key=holder_key,
        mandate_token=open_jwt,
        payloads=[closed_payload],
        aud='merchant',
        nonce='m-n',
    )
    # New hop's header is typ=kb+sd-jwt (terminal).
    new_hop = result.split('~~', 1)[1]
    assert _decode_jwt_header(new_hop)['typ'] == 'kb+sd-jwt'


def test_present_hash_mode_plumbs_through_to_primitive(issuer_key):
    """``hash_mode='issuer_jwt_hash'`` shows up as issuer_jwt_hash in the new hop."""
    import base64 as _b64

    holder_key = JWK.generate(kty='EC', crv='P-256')
    open_payload = OpenPaymentMandate(constraints=[], cnf=make_cnf(holder_key))
    open_jwt = MandateClient().create(
        payloads=[open_payload], issuer_key=issuer_key
    )

    closed_payload = PaymentMandate(
        transaction_id='tx_hm',
        payee=Merchant(id='m-1', name='Shop'),
        payment_amount=Amount(amount=10, currency='USD'),
        payment_instrument=PaymentInstrument(id='pi-1', type='credit'),
    )
    result = MandateClient().present(
        holder_key=holder_key,
        mandate_token=open_jwt,
        payloads=[closed_payload],
        aud='merchant',
        nonce='m-n',
        hash_mode='issuer_jwt_hash',
    )
    new_hop_jwt = result.split('~~', 1)[1].split('~', 1)[0]
    payload_b64 = new_hop_jwt.split('.')[1]
    padded = payload_b64 + '=' * (-len(payload_b64) % 4)
    payload = json.loads(_b64.urlsafe_b64decode(padded))
    assert 'issuer_jwt_hash' in payload
    assert 'sd_hash' not in payload
