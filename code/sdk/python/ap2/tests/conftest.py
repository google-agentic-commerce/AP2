"""Shared fixtures and helpers for AP2 SDK tests."""

import json

from typing import Any

import pytest

from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.checkout import Checkout, Status
from ap2.sdk.generated.types.item import Item
from ap2.sdk.generated.types.line_item import LineItem
from ap2.sdk.generated.types.link import Link
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.generated.types.total import Total
from ap2.sdk.mandate import MandateClient
from ap2.sdk.utils import b64url_encode, ec_key_to_jwk
from cryptography.hazmat.primitives.asymmetric import ec
from jwcrypto.jwk import JWK


@pytest.fixture
def issuer_key():
    """JWK usable as an issuer/agent signing key."""
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = JWK.from_pyca(key)
    jwk_dict = json.loads(jwk.export())
    jwk_dict['kid'] = 'issuer-key-1'
    return JWK.from_json(json.dumps(jwk_dict))


@pytest.fixture
def issuer_public_key(issuer_key):
    return JWK.from_json(issuer_key.export_public())


@pytest.fixture
def agent_key():
    """Agent's JWK signing key."""
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = JWK.from_pyca(key)
    jwk_dict = json.loads(jwk.export())
    jwk_dict['kid'] = 'agent-key-1'
    return JWK.from_json(json.dumps(jwk_dict))


@pytest.fixture
def agent_public_key(agent_key):
    return JWK.from_json(agent_key.export_public())


@pytest.fixture
def user_key():
    """User's JWK signing key."""
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = JWK.from_pyca(key)
    jwk_dict = json.loads(jwk.export())
    jwk_dict['kid'] = 'user-key-1'
    return JWK.from_json(json.dumps(jwk_dict))


@pytest.fixture
def user_public_key(user_key):
    return JWK.from_json(user_key.export_public())


@pytest.fixture
def mandate_client():
    """Stateless MandateClient for creating/verifying mandates."""
    return MandateClient()


@pytest.fixture
def holder():
    """Fixture to provide a client acting as holder."""
    return MandateClient()


def make_cnf(key: Any) -> dict[str, Any]:
    """Build a ``cnf`` dict from a JWK or raw EC public key."""
    if isinstance(key, JWK):
        return {'jwk': json.loads(key.export_public())}
    if isinstance(key, ec.EllipticCurvePublicKey):
        return {'jwk': ec_key_to_jwk(key).model_dump(exclude_none=True)}
    raise TypeError(f'Unsupported key type for make_cnf: {type(key)}')


def sample_payment_mandate(**overrides):
    """Build a PaymentMandate with sensible defaults."""
    defaults = dict(
        transaction_id='tx_1',
        payee=Merchant(name='Shop', id='s-1'),
        payment_amount=Amount(amount=1000, currency='USD'),
        payment_instrument=PaymentInstrument(id='pi-1', type='credit'),
    )
    defaults.update(overrides)
    return PaymentMandate(**defaults)


def fake_sd_jwt(payload_dict: dict) -> str:
    """Build a minimal unsigned SD-JWT-shaped string for non-verification tests."""
    hdr = b64url_encode(json.dumps({'alg': 'none'}).encode())
    body = b64url_encode(json.dumps(payload_dict).encode())
    return f'{hdr}.{body}.fakesig~'


def make_line_item(
    sku: str,
    title: str = '',
    quantity: int = 1,
    unit_price: int = 0,
    li_id: str | None = None,
) -> LineItem:
    """Build a UCP LineItem from product attributes."""
    return LineItem(
        id=li_id or f'li_{sku}',
        item=Item(id=sku, title=title or sku, price=unit_price),
        quantity=quantity,
        totals=[
            Total(type='subtotal', amount=unit_price * quantity),
            Total(type='total', amount=unit_price * quantity),
        ],
    )


_DEFAULT_LINKS = [
    Link(type='privacy_policy', url='https://example.com/privacy'),
    Link(type='terms_of_service', url='https://example.com/tos'),
]


def make_checkout_jwt(
    merchant: Merchant | None = None,
    line_items: list[LineItem] | None = None,
    checkout_id: str = 'chk_test',
    currency: str = 'USD',
    status: Status = Status.incomplete,
) -> str:
    """Build a fake checkout JWT with a UCP Checkout payload."""
    items = line_items or []
    subtotal = sum(li.item.price * li.quantity for li in items)
    checkout = Checkout(
        id=checkout_id,
        merchant=merchant,
        line_items=items,
        status=status,
        currency=currency,
        totals=[
            Total(type='subtotal', amount=subtotal),
            Total(type='total', amount=subtotal),
        ],
        links=_DEFAULT_LINKS,
    )
    json_payload = checkout.model_dump_json(exclude_none=True)
    body_b64 = b64url_encode(json_payload.encode('utf-8'))
    return f'hdr.{body_b64}.sig'
