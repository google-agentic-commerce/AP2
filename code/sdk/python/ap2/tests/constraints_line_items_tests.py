"""Tests for checking line items checkout constraints."""

from typing import Any

from ap2.sdk.constraints import check_checkout_constraints
from ap2.sdk.generated.open_checkout_mandate import (
    Item as MandateItem,
)
from ap2.sdk.generated.open_checkout_mandate import (
    LineItemRequirements,
    LineItems,
    OpenCheckoutMandate,
)
from ap2.sdk.generated.types.checkout import Checkout, Status
from ap2.sdk.generated.types.item import Item
from ap2.sdk.generated.types.jwk import JsonWebKey
from ap2.sdk.generated.types.line_item import LineItem
from ap2.sdk.generated.types.link import Link
from ap2.sdk.generated.types.total import Total
from ap2.sdk.utils import ec_key_to_jwk
from cryptography.hazmat.primitives.asymmetric import ec


_DUMMY_KEY = ec.generate_private_key(ec.SECP256R1())
_CNF: JsonWebKey = {
    'jwk': ec_key_to_jwk(_DUMMY_KEY.public_key()).model_dump(exclude_none=True)
}

_DEFAULT_LINKS = [
    Link(type='privacy_policy', url='https://example.com/privacy'),
]


def _open_checkout(**kw):
    defaults = dict(constraints=[], cnf=_CNF)
    defaults.update(kw)
    return OpenCheckoutMandate(**defaults)


def _make_checkout_with_items(items: list[dict[str, Any]]) -> Checkout:
    """Builds a UCP Checkout from simplified item dicts.

    Each dict has ``sku`` and ``qty`` keys.  Uses ``model_construct`` to
    bypass validation for edge-case tests (e.g. zero-quantity items).

    Args:
      items: A list of dictionaries, where each dict has "sku" and "qty" keys.

    Returns:
      A Checkout object.
    """
    line_items = []
    for i, d in enumerate(items):
        li = LineItem.model_construct(
            id=f'li_{i}',
            item=Item.model_construct(
                id=d['sku'],
                title=d['sku'],
                price=0,
            ),
            quantity=d['qty'],
            totals=[],
        )
        line_items.append(li)
    return Checkout.model_construct(
        id='chk_test',
        line_items=line_items,
        status=Status.incomplete,
        currency='USD',
        totals=[
            Total(type='subtotal', amount=0),
            Total(type='total', amount=0),
        ],
        links=_DEFAULT_LINKS,
    )


def _li(sku: str, qty: int = 1) -> dict[str, Any]:
    return {'sku': sku, 'qty': qty}


def _req(req_id: str, skus: list[str], qty: int) -> LineItemRequirements:
    return LineItemRequirements(
        id=req_id,
        acceptable_items=[MandateItem(id=s, title=s) for s in skus],
        quantity=qty,
    )


def test_line_items_single_sku_valid():
    """Single requirement, single matching SKU within quantity."""
    constraint = LineItems(items=[_req('r1', ['A'], 3)])
    checkout = _make_checkout_with_items([_li('A', 2)])
    violations = check_checkout_constraints(
        _open_checkout(constraints=[constraint]),
        checkout,
    )
    assert violations == []


def test_line_items_single_sku_over_quantity():
    """Cart exceeds requirement quantity."""
    constraint = LineItems(items=[_req('r1', ['A'], 2)])
    checkout = _make_checkout_with_items([_li('A', 3)])
    violations = check_checkout_constraints(
        _open_checkout(constraints=[constraint]),
        checkout,
    )
    assert violations
    assert any('could not be assigned' in v for v in violations)


def test_line_items_disallowed_sku():
    """Cart contains a SKU not in any requirement."""
    constraint = LineItems(items=[_req('r1', ['A'], 5)])
    checkout = _make_checkout_with_items([_li('Z', 1)])
    violations = check_checkout_constraints(
        _open_checkout(constraints=[constraint]),
        checkout,
    )
    assert any('not in any requirement' in v for v in violations)


def test_line_items_competing_skus_same_slot():
    """B and C compete for the same slot, so {B:1, C:1} fails.

    Constraint: Req1(A, qty=1), Req2(B||C, qty=1)
    Cart: {B:1, C:1}
    This must FAIL because Req2 can absorb only 1 unit total, and Req1
    only accepts A. So one of B or C has no slot.
    """
    constraint = LineItems(
        items=[
            _req('r1', ['A'], 1),
            _req('r2', ['B', 'C'], 1),
        ]
    )
    checkout = _make_checkout_with_items([_li('B', 1), _li('C', 1)])
    violations = check_checkout_constraints(
        _open_checkout(constraints=[constraint]),
        checkout,
    )
    assert violations
    assert any('could not be assigned' in v for v in violations)


def test_line_items_competing_skus_valid():
    """Same constraint as above, but cart {A:1, B:1} is valid."""
    constraint = LineItems(
        items=[
            _req('r1', ['A'], 1),
            _req('r2', ['B', 'C'], 1),
        ]
    )
    checkout = _make_checkout_with_items([_li('A', 1), _li('B', 1)])
    violations = check_checkout_constraints(
        _open_checkout(constraints=[constraint]),
        checkout,
    )
    assert violations == []


def test_line_items_sku_shared_across_requirements():
    """SKU A appears in two requirements; total capacity is the sum."""
    constraint = LineItems(
        items=[
            _req('r1', ['A'], 2),
            _req('r2', ['A', 'B'], 3),
        ]
    )
    checkout = _make_checkout_with_items([_li('A', 5)])
    violations = check_checkout_constraints(
        _open_checkout(constraints=[constraint]),
        checkout,
    )
    assert violations == []


def test_line_items_sku_shared_exceeds_total_capacity():
    """SKU A in two slots (cap 2+3=5) but cart has 6."""
    constraint = LineItems(
        items=[
            _req('r1', ['A'], 2),
            _req('r2', ['A', 'B'], 3),
        ]
    )
    checkout = _make_checkout_with_items([_li('A', 6)])
    violations = check_checkout_constraints(
        _open_checkout(constraints=[constraint]),
        checkout,
    )
    assert violations
    assert any('could not be assigned' in v for v in violations)


def test_line_items_wildcard_requirement():
    """Empty acceptable_items acts as wildcard (any SKU accepted)."""
    constraint = LineItems(
        items=[
            LineItemRequirements(id='wild', acceptable_items=[], quantity=10),
        ]
    )
    checkout = _make_checkout_with_items([_li('ANY', 5)])
    violations = check_checkout_constraints(
        _open_checkout(constraints=[constraint]),
        checkout,
    )
    assert violations == []


def test_line_items_complex_multi_slot_routing():
    """Complex scenario requiring flow to find a valid assignment.

    Req1(A||B, qty=1), Req2(B||C, qty=1), Req3(C||D, qty=1)
    Cart: {A:1, B:1, C:1}
    Valid assignment: A→Req1, B→Req2, C→Req3
    """
    constraint = LineItems(
        items=[
            _req('r1', ['A', 'B'], 1),
            _req('r2', ['B', 'C'], 1),
            _req('r3', ['C', 'D'], 1),
        ]
    )
    checkout = _make_checkout_with_items(
        [_li('A', 1), _li('B', 1), _li('C', 1)]
    )
    violations = check_checkout_constraints(
        _open_checkout(constraints=[constraint]),
        checkout,
    )
    assert violations == []


def test_line_items_complex_routing_fails():
    """No valid assignment exists.

    Req1(A, qty=1), Req2(A, qty=1)
    Cart: {A:1, B:1}
    A fills one req, but B has no slot.
    """
    constraint = LineItems(
        items=[
            _req('r1', ['A'], 1),
            _req('r2', ['A'], 1),
        ]
    )
    checkout = _make_checkout_with_items([_li('A', 1), _li('B', 1)])
    violations = check_checkout_constraints(
        _open_checkout(constraints=[constraint]),
        checkout,
    )
    assert violations
    assert any('B' in v for v in violations)


def test_line_items_empty_cart():
    """Empty cart always violates a line_items constraint."""
    constraint = LineItems(items=[_req('r1', ['A'], 1)])
    checkout = _make_checkout_with_items([])
    violations = check_checkout_constraints(
        _open_checkout(constraints=[constraint]),
        checkout,
    )
    assert any('Empty cart' in v for v in violations)


def test_line_items_partial_quantity_routing():
    """SKU quantity split across multiple requirements.

    Req1(A||B, qty=2), Req2(A||C, qty=3)
    Cart: {A:4, C:1}
    Valid: A→Req1(2) + A→Req2(2), C→Req2(1) = total 5
    """
    constraint = LineItems(
        items=[
            _req('r1', ['A', 'B'], 2),
            _req('r2', ['A', 'C'], 3),
        ]
    )
    checkout = _make_checkout_with_items([_li('A', 4), _li('C', 1)])
    violations = check_checkout_constraints(
        _open_checkout(constraints=[constraint]),
        checkout,
    )
    assert violations == []


def test_line_items_duplicate_sku_entries():
    """Duplicate SKU entries in cart should be merged."""
    constraint = LineItems(items=[_req('r1', ['A'], 3)])
    # Cart has two entries for A, total quantity = 3
    checkout = _make_checkout_with_items([_li('A', 1), _li('A', 2)])
    violations = check_checkout_constraints(
        _open_checkout(constraints=[constraint]),
        checkout,
    )
    assert violations == []


def test_line_items_zero_quantity_item():
    """Zero-quantity items should be effectively ignored."""
    constraint = LineItems(items=[_req('r1', ['A'], 2)])
    checkout = _make_checkout_with_items([_li('A', 2), _li('B', 0)])
    violations = check_checkout_constraints(
        _open_checkout(constraints=[constraint]),
        checkout,
    )
    assert violations == []


def test_line_items_cart_smaller_than_total_capacity():
    """Cart size smaller than sum of all requirement capacities is valid."""
    constraint = LineItems(
        items=[
            _req('r1', ['A'], 5),
            _req('r2', ['B'], 5),
        ]
    )
    checkout = _make_checkout_with_items([_li('A', 1), _li('B', 1)])
    violations = check_checkout_constraints(
        _open_checkout(constraints=[constraint]),
        checkout,
    )
    assert violations == []
