"""Tests for the DisclosureMetadata class."""

from typing import Any

import pytest

from ap2.sdk.disclosure_metadata import DisclosureMetadata
from sd_jwt.holder import SDJWTHolder
from sd_jwt.issuer import SDJWTIssuer
from sd_jwt.utils.demo_utils import get_jwk


# pytest relies on dependency injection using the variable names and this is a
# false positive warning.
# pylint: disable=redefined-outer-name


@pytest.fixture
def user_claims() -> dict[str, Any]:
    """Fixture providing standard user claims for tests."""
    return {
        'sub': 'user_1',
        'given_name': 'John',
        'family_name': 'Doe',
        'address': {
            'street': '123 Main St',
            'city': 'Anytown',
            'country': 'US',
        },
        'credentials': ['degree', 'license'],
    }


@pytest.fixture
def jwk_keys() -> dict[str, Any]:
    """Fixture generating test ECDSA keys."""
    return get_jwk({'key_size': 256, 'kty': 'EC'}, no_randomness=False)


@pytest.fixture
def issuer_key(jwk_keys: dict[str, Any]) -> Any:
    """Fixture providing the issuer private key."""
    return jwk_keys['issuer_key']


@pytest.fixture
def holder_key(jwk_keys: dict[str, Any]) -> Any:
    """Fixture providing the holder private key."""
    return jwk_keys['holder_key']


def test_simple_dict_sd(user_claims: dict[str, Any], issuer_key: Any):
    meta = DisclosureMetadata(sd_keys=['given_name', 'address'])

    sd_claims = meta.apply(user_claims)
    issuer = SDJWTIssuer(sd_claims, issuer_key)
    payload = issuer.sd_jwt_payload

    assert '_sd' in payload
    assert 'given_name' not in payload
    assert 'address' not in payload
    assert 'family_name' in payload
    assert any(d.key == 'given_name' for d in issuer.ii_disclosures)
    assert any(d.key == 'address' for d in issuer.ii_disclosures)


def test_nested_disclose_all(user_claims: dict[str, Any], issuer_key: Any):
    meta = DisclosureMetadata(
        children={'address': DisclosureMetadata(disclose_all=True)}
    )

    sd_claims = meta.apply(user_claims)
    issuer = SDJWTIssuer(sd_claims, issuer_key)
    payload = issuer.sd_jwt_payload

    assert 'address' in payload
    address_claim = payload['address']

    assert '_sd' in address_claim
    assert 'street' not in address_claim
    assert any(d.key == 'street' for d in issuer.ii_disclosures)


def test_array_indices(user_claims: dict[str, Any], issuer_key: Any):
    meta = DisclosureMetadata(
        children={'credentials': DisclosureMetadata(sd_array_indices=[0])}
    )

    sd_claims = meta.apply(user_claims)
    issuer = SDJWTIssuer(sd_claims, issuer_key)
    payload = issuer.sd_jwt_payload

    assert 'credentials' in payload
    creds = payload['credentials']

    assert isinstance(creds[0], dict)
    assert '...' in creds[0]
    assert creds[1] == 'license'


def test_full_roundtrip_holder(user_claims: dict[str, Any], issuer_key: Any):
    meta = DisclosureMetadata(
        sd_keys=['given_name'],
        children={'address': DisclosureMetadata(disclose_all=True)},
    )
    sd_claims = meta.apply(user_claims)
    issuer = SDJWTIssuer(sd_claims, issuer_key)
    issued_jwt = issuer.sd_jwt_issuance

    holder = SDJWTHolder(issued_jwt)
    present_claims = {'given_name': True, 'address': {'city': True}}
    holder.create_presentation(present_claims)
    presentation = holder.sd_jwt_presentation

    assert '~' in presentation


def test_recursive_list_of_objects(issuer_key: Any):
    data = {'list': [{'id': 1, 'secret': 'A'}, {'id': 2, 'secret': 'B'}]}

    meta = DisclosureMetadata(
        children={
            'list': DisclosureMetadata(
                all_array_children=DisclosureMetadata(sd_keys=['secret'])
            )
        }
    )

    sd_claims = meta.apply(data)
    issuer = SDJWTIssuer(sd_claims, issuer_key)
    list_payload = issuer.sd_jwt_payload['list']

    assert list_payload[0]['id'] == 1
    assert 'secret' not in list_payload[0]
    assert '_sd' in list_payload[0]
    assert list_payload[1]['id'] == 2
    assert 'secret' not in list_payload[1]
    assert '_sd' in list_payload[1]


def test_missing_keys_ignored(issuer_key: Any):
    data = {'a': 1}
    meta = DisclosureMetadata(sd_keys=['a', 'b'])

    sd_claims = meta.apply(data)
    issuer = SDJWTIssuer(sd_claims, issuer_key)
    payload = issuer.sd_jwt_payload

    assert 'a' not in payload
    assert '_sd' in payload


def test_apply_scalar_returns_as_is():
    """apply on a non-dict, non-list value returns it unchanged."""
    meta = DisclosureMetadata(sd_keys=['x'])
    assert meta.apply(42) == 42
    assert meta.apply('hello') == 'hello'
    assert meta.apply(None) is None


def test_apply_empty_dict():
    """apply on an empty dict returns an empty dict."""
    meta = DisclosureMetadata(sd_keys=['x'])
    assert meta.apply({}) == {}


def test_apply_empty_list():
    """apply on an empty list returns an empty list."""
    meta = DisclosureMetadata(sd_array_indices=[0])
    assert meta.apply([]) == []


def test_disclose_all_at_root(user_claims: dict[str, Any], issuer_key: Any):
    """disclose_all at the root level wraps every key."""
    meta = DisclosureMetadata(disclose_all=True)
    sd_claims = meta.apply(user_claims)
    issuer = SDJWTIssuer(sd_claims, issuer_key)
    payload = issuer.sd_jwt_payload

    for key in user_claims:
        assert key not in payload
    assert '_sd' in payload


def test_array_children_index_specific(issuer_key: Any):
    """array_children applies metadata to a specific index only."""
    data = {'items': [{'id': 1, 'secret': 'A'}, {'id': 2, 'secret': 'B'}]}
    meta = DisclosureMetadata(
        children={
            'items': DisclosureMetadata(
                array_children={0: DisclosureMetadata(sd_keys=['secret'])}
            )
        }
    )
    sd_claims = meta.apply(data)
    issuer = SDJWTIssuer(sd_claims, issuer_key)
    items = issuer.sd_jwt_payload['items']

    assert '_sd' in items[0]
    assert 'secret' not in items[0]
    assert items[1]['secret'] == 'B'


def test_from_dict_empty():
    """from_dict with empty dict returns default DisclosureMetadata."""
    meta = DisclosureMetadata.from_dict({})
    assert meta.sd_keys == []
    assert meta.children == {}
    assert meta.disclose_all is False


def test_from_dict_with_sd_keys():
    """from_dict reconstructs sd_keys."""
    meta = DisclosureMetadata.from_dict({'sd_keys': ['a', 'b']})
    assert meta.sd_keys == ['a', 'b']


def test_from_dict_with_nested_children():
    """from_dict reconstructs nested children."""
    meta = DisclosureMetadata.from_dict(
        {
            'children': {
                'address': {'sd_keys': ['street'], 'disclose_all': False},
            },
        }
    )
    assert 'address' in meta.children
    assert meta.children['address'].sd_keys == ['street']


def test_from_dict_with_array_children():
    """from_dict reconstructs array_children with integer keys."""
    meta = DisclosureMetadata.from_dict(
        {
            'array_children': {
                '0': {'sd_keys': ['secret']},
            },
        }
    )
    assert 0 in meta.array_children
    assert meta.array_children[0].sd_keys == ['secret']


def test_from_dict_with_all_array_children():
    """from_dict reconstructs all_array_children."""
    meta = DisclosureMetadata.from_dict(
        {
            'all_array_children': {'sd_keys': ['x']},
        }
    )
    assert meta.all_array_children is not None
    assert meta.all_array_children.sd_keys == ['x']


def test_from_dict_roundtrip():
    """from_dict(asdict(meta)) reproduces the original metadata."""
    from dataclasses import asdict

    original = DisclosureMetadata(
        sd_keys=['a'],
        sd_array_indices=[0, 2],
        children={'nested': DisclosureMetadata(disclose_all=True)},
    )
    rebuilt = DisclosureMetadata.from_dict(asdict(original))
    assert rebuilt.sd_keys == original.sd_keys
    assert rebuilt.sd_array_indices == original.sd_array_indices
    assert rebuilt.children['nested'].disclose_all is True


def test_create_sd_jwt_without_metadata(issuer_key: Any):
    """SDJWTIssuer without metadata produces a plain JWT (no disclosures)."""
    claims = {'sub': 'user-1', 'name': 'Test'}
    issuer = SDJWTIssuer(
        user_claims=claims,
        issuer_key=issuer_key,
    )
    assert 'sub' in issuer.sd_jwt_payload
    assert 'name' in issuer.sd_jwt_payload
    assert '_sd' not in issuer.sd_jwt_payload


def test_create_sd_jwt_with_metadata(issuer_key: Any):
    """SDJWTIssuer with metadata applies selective disclosure."""
    sd_meta = DisclosureMetadata(sd_keys=['name'])
    user_claims = {'sub': 'user-1', 'name': 'Test'}
    sd_claims = sd_meta.apply(user_claims)
    issuer = SDJWTIssuer(
        user_claims=sd_claims,
        issuer_key=issuer_key,
    )
    assert 'sub' in issuer.sd_jwt_payload
    assert 'name' not in issuer.sd_jwt_payload
    assert '_sd' in issuer.sd_jwt_payload
