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
            checkout_hash=compute_sha256_b64url(checkout_jwt),
        ),
    ]
    chain = CheckoutMandateChain.parse(payloads)
    violations = chain.verify(checkout_jwt=checkout_jwt)
    assert any('not in allowed list' in v for v in violations)
    assert not any('checkout_hash mismatch' in v for v in violations)


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
            checkout_hash=compute_sha256_b64url(checkout_jwt),
        ),
    ]
    chain = CheckoutMandateChain.parse(payloads)
    violations = chain.verify(
        expected_checkout_hash=expected_hash, checkout_jwt=checkout_jwt
    )
    assert len(violations) == 1
    assert 'Checkout checkout_hash mismatch' in violations[0]
    assert 'expected expected_hash' in violations[0]


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


def _bound_chain(checkout_jwt: str) -> CheckoutMandateChain:
    """Build a chain whose closed mandate is bound to ``checkout_jwt``."""
    return CheckoutMandateChain(
        open_mandate=OpenCheckoutMandate(
            constraints=[], cnf=make_cnf(_DUMMY_KEY.public_key())
        ),
        closed_mandate=CheckoutMandate(
            checkout_jwt=checkout_jwt,
            checkout_hash=compute_sha256_b64url(checkout_jwt),
        ),
    )


def test_checkout_binding_matching_checkout_passes():
    """The Checkout JWT the closed mandate is bound to verifies cleanly."""
    checkout_a_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Store'),
        checkout_id='chk_a',
    )
    chain = _bound_chain(checkout_a_jwt)
    assert chain.verify(checkout_jwt=checkout_a_jwt) == []


def test_checkout_binding_rejects_other_checkout_without_expected_hash():
    """A different Checkout JWT is rejected with no caller-supplied hash.

    This is the regression anchor: the closed mandate is bound to checkout A,
    checkout B is presented for verification, and no
    ``expected_checkout_hash`` is supplied. Before the binding fix verify()
    never derived the hash itself, so this returned no violations.
    """
    checkout_a_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Store'),
        checkout_id='chk_a',
    )
    checkout_b_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Store'),
        checkout_id='chk_b',
    )
    assert checkout_a_jwt != checkout_b_jwt

    chain = _bound_chain(checkout_a_jwt)

    violations = chain.verify(checkout_jwt=checkout_b_jwt)

    assert any('checkout_hash mismatch' in v for v in violations)


def test_checkout_chain_rejects_internally_inconsistent_closed_mandate():
    """A closed mandate whose own jwt and hash disagree is rejected.

    Here the presented checkout is the closed mandate's own ``checkout_jwt``,
    so the two execution contexts agree. The mandate is nonetheless invalid
    because its ``checkout_hash`` records a different checkout, meaning it was
    never bound to the checkout it carries.
    """
    checkout_a_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Store'),
        checkout_id='chk_a',
    )
    checkout_b_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Store'),
        checkout_id='chk_b',
    )
    chain = CheckoutMandateChain(
        open_mandate=OpenCheckoutMandate(
            constraints=[], cnf=make_cnf(_DUMMY_KEY.public_key())
        ),
        closed_mandate=CheckoutMandate(
            checkout_jwt=checkout_a_jwt,
            checkout_hash=compute_sha256_b64url(checkout_b_jwt),
        ),
    )
    # The presented checkout matches the mandate's embedded checkout exactly.
    assert chain.closed_mandate.checkout_jwt == checkout_a_jwt

    violations = chain.verify(checkout_jwt=checkout_a_jwt)

    assert any('checkout_hash mismatch' in v for v in violations)


def test_checkout_binding_not_skipped_when_expected_hash_agrees():
    """A caller-supplied hash cannot mask a mismatched presented checkout.

    The caller passes the closed mandate's own checkout_hash, so the optional
    consistency assertion is satisfied. The derived binding check must still
    reject the mismatched checkout.
    """
    checkout_a_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Store'),
        checkout_id='chk_a',
    )
    checkout_b_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Store'),
        checkout_id='chk_b',
    )
    chain = _bound_chain(checkout_a_jwt)

    violations = chain.verify(
        expected_checkout_hash=chain.closed_mandate.checkout_hash,
        checkout_jwt=checkout_b_jwt,
    )

    assert any('checkout_hash mismatch' in v for v in violations)


def test_checkout_binding_reported_with_constraints_satisfied():
    """Binding failure is reported even when open constraints all pass."""
    checkout_a_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Good Store'),
        checkout_id='chk_a',
    )
    checkout_b_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Good Store'),
        checkout_id='chk_b',
    )
    chain = CheckoutMandateChain(
        open_mandate=OpenCheckoutMandate(
            constraints=[
                AllowedMerchants(
                    allowed=[Merchant(id='m-1', name='Good Store')],
                ),
            ],
            cnf=make_cnf(_DUMMY_KEY.public_key()),
        ),
        closed_mandate=CheckoutMandate(
            checkout_jwt=checkout_a_jwt,
            checkout_hash=compute_sha256_b64url(checkout_a_jwt),
        ),
    )

    violations = chain.verify(checkout_jwt=checkout_b_jwt)

    assert not any('not in allowed list' in v for v in violations)
    assert any('checkout_hash mismatch' in v for v in violations)


def test_checkout_binding_does_not_leak_checkout_jwt():
    """The mismatch violation does not embed the Checkout JWT contents."""
    checkout_a_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Store'),
        checkout_id='chk_a',
    )
    checkout_b_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Store'),
        checkout_id='chk_b',
    )
    chain = _bound_chain(checkout_a_jwt)

    violations = chain.verify(checkout_jwt=checkout_b_jwt)

    assert violations
    for violation in violations:
        assert checkout_b_jwt not in violation
        assert checkout_a_jwt not in violation


def test_checkout_binding_missing_checkout_jwt_still_fails():
    """A missing Checkout JWT remains fail-closed."""
    checkout_a_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Store'),
        checkout_id='chk_a',
    )
    chain = _bound_chain(checkout_a_jwt)

    violations = chain.verify(checkout_jwt=None)

    assert any('checkout_jwt is required' in v for v in violations)


def test_checkout_binding_malformed_checkout_jwt_still_fails():
    """A malformed Checkout JWT remains fail-closed."""
    checkout_a_jwt = make_checkout_jwt(
        merchant=Merchant(id='m-1', name='Store'),
        checkout_id='chk_a',
    )
    chain = _bound_chain(checkout_a_jwt)

    violations = chain.verify(checkout_jwt='not-a-jwt')

    assert any('Malformed checkout_jwt' in v for v in violations)
