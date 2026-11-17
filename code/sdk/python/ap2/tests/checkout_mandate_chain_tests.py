"""Tests for CheckoutMandateChain (ap2.sdk.checkout_mandate_chain)."""

import pytest

from ap2.sdk.checkout_mandate_chain import CheckoutMandateChain
from ap2.sdk.generated.checkout_mandate import CheckoutMandate
from ap2.sdk.generated.open_checkout_mandate import (
    AllowedMerchants,
    LineItemRequirements,
    LineItems,
    OpenCheckoutMandate,
)
from ap2.sdk.generated.open_checkout_mandate import (
    Item as MandateItem,
)
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.utils import compute_sha256_b64url
from ap2.tests.conftest import make_checkout_jwt, make_cnf, make_line_item
from cryptography.hazmat.primitives.asymmetric import ec


_DUMMY_KEY = ec.generate_private_key(ec.SECP256R1())


def test_checkout_chain_parse_wrong_payload_count():
    """parse() requires exactly 2 payloads."""
    with pytest.raises(ValueError, match='exactly 2'):
        CheckoutMandateChain.parse([{}])


def test_checkout_chain_verify_constraint_violation():
    """CheckoutMandateChain.verify() catches merchant not in allowed list."""
    checkout_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-wrong', name='Evil Store'),
    )
    payloads = [
        OpenCheckoutMandate(
            constraints=[
                AllowedMerchants(
                    allowed=[Merchant(id='m-1', name='Good Store')],
                ),
            ],
            cnf=make_cnf(_DUMMY_KEY.public_key()),
        ),
        CheckoutMandate(
            checkout_jwt=checkout_jwt,
            checkout_hash='hash',
        ),
    ]
    chain = CheckoutMandateChain.parse(payloads)
    violations = chain.verify(checkout_jwt=checkout_jwt)
    assert any('not in allowed list' in v for v in violations)


def test_checkout_chain_hash_mismatch():
    """Checkout mandate rejected if expected checkout hash doesn't match."""
    expected_hash = 'expected_hash'
    checkout_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Good Store'),
    )
    payloads = [
        OpenCheckoutMandate(
            constraints=[],
            cnf=make_cnf(_DUMMY_KEY.public_key()),
        ),
        CheckoutMandate(
            checkout_jwt=checkout_jwt,
            # Tied to checkout_jwt, so only the expected_checkout_hash
            # comparison below should produce a violation.
            checkout_hash=compute_sha256_b64url(checkout_jwt),
        ),
    ]
    chain = CheckoutMandateChain.parse(payloads)
    violations = chain.verify(
        expected_checkout_hash=expected_hash, checkout_jwt=checkout_jwt
    )
    assert len(violations) == 1
    assert 'Checkout checkout_hash mismatch' in violations[0]


def test_checkout_chain_rejects_checkout_hash_not_tied_to_checkout_jwt():
    """verify() must reject a closed_mandate whose checkout_hash does not
    correspond to the checkout_jwt it is presented with, even when no
    expected_checkout_hash is supplied by the caller.

    checkout_hash is meant to bind the closed mandate to one specific
    checkout_jwt (see the merchant sample's
    ``checkout_hash = _compute_sha256_b64url(checkout_jwt)``). Without
    verify() checking that binding itself, a party holding a validly-signed
    CheckoutMandateChain for one checkout could substitute a *different*
    checkout_jwt (e.g. a cheaper cart, or one for a different merchant) and
    verify() would accept it as long as the caller happens not to pass
    expected_checkout_hash from its own already-trusted source - the field
    is otherwise decorative.
    """
    real_checkout_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Good Store'),
    )
    substituted_checkout_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-evil', name='Evil Store'),
    )
    payloads = [
        OpenCheckoutMandate(
            constraints=[],
            cnf=make_cnf(_DUMMY_KEY.public_key()),
        ),
        CheckoutMandate(
            # checkout_hash was computed over real_checkout_jwt at issuance
            # time, NOT over substituted_checkout_jwt.
            checkout_jwt=real_checkout_jwt,
            checkout_hash=compute_sha256_b64url(real_checkout_jwt),
        ),
    ]
    chain = CheckoutMandateChain.parse(payloads)
    # No expected_checkout_hash supplied: verify() must still catch that
    # substituted_checkout_jwt was never the checkout this chain committed to.
    violations = chain.verify(checkout_jwt=substituted_checkout_jwt)
    assert any('checkout_hash' in v for v in violations)


def test_full_checkout_end_to_end(
    user_key,
    user_public_key,
    agent_key,
    holder,
):
    """Full end-to-end for checkout mandate chain."""
    open_tok = holder.create(
        payloads=[
            OpenCheckoutMandate(
                constraints=[],
                cnf=make_cnf(agent_key),
            )
        ],
        issuer_key=user_key,
    )
    checkout_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Store'),
        line_items=[
            make_line_item('item-1', 'Widget', quantity=1, unit_price=1000),
        ],
    )
    tok_chain = holder.present(
        holder_key=agent_key,
        mandate_token=open_tok,
        payloads=[
            CheckoutMandate(
                checkout_jwt=checkout_jwt,
                checkout_hash=compute_sha256_b64url(checkout_jwt),
            )
        ],
        aud='merchant',
        nonce='merchant-nonce',
    )

    payloads = holder.verify(
        token=tok_chain,
        key_or_provider=lambda _token: user_public_key,
    )
    chain = CheckoutMandateChain.parse(payloads)
    violations = chain.verify(checkout_jwt=checkout_jwt)
    assert violations == []


def test_checkout_line_items_constraint():
    """Line-item constraints validated via checkout JWT."""
    checkout_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Store'),
        line_items=[
            make_line_item('SKU-A', 'Widget', quantity=2, unit_price=500),
        ],
    )
    payloads = [
        OpenCheckoutMandate(
            constraints=[
                LineItems(
                    items=[
                        LineItemRequirements(
                            id='req-1',
                            acceptable_items=[
                                MandateItem(id='SKU-A', title='Widget')
                            ],
                            quantity=2,
                        ),
                    ]
                ),
            ],
            cnf=make_cnf(_DUMMY_KEY.public_key()),
        ),
        CheckoutMandate(
            checkout_jwt=checkout_jwt,
            checkout_hash=compute_sha256_b64url(checkout_jwt),
        ),
    ]
    chain = CheckoutMandateChain.parse(payloads)
    violations = chain.verify(checkout_jwt=checkout_jwt)
    assert violations == []


def test_checkout_fields_parsed():
    """UCP Checkout fields are correctly extracted from JWT."""
    checkout_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Good Store'),
        line_items=[
            make_line_item('item-1', 'Widget', quantity=2, unit_price=1500),
        ],
    )
    chain = CheckoutMandateChain(
        open_mandate=OpenCheckoutMandate(
            constraints=[], cnf=make_cnf(_DUMMY_KEY.public_key())
        ),
        closed_mandate=CheckoutMandate(
            checkout_jwt=checkout_jwt, checkout_hash='h'
        ),
    )
    checkout = chain.extract_parsed_checkout_object(checkout_jwt)
    assert checkout.id == 'chk_test'
    assert checkout.merchant.id == 'm-1'
    assert checkout.status.value == 'incomplete'
    assert checkout.currency == 'USD'
    assert len(checkout.line_items) == 1
    assert checkout.line_items[0].item.id == 'item-1'
    assert checkout.line_items[0].quantity == 2
