"""Consumer/verifier for the versioned delegate-SD-JWT golden vectors.

Loads the frozen golden set
(``delegate_sd_jwt_vectors/delegate_sd_jwt_vectors.json``) and, for every
vector, asserts:

1. the on-wire shape invariants (RFC 9901 + the dSD-JWT ``~~`` chain wire):
   a single SD-JWT ends with exactly one ``~`` and has zero ``~~`` joins; an
   N-segment chain has exactly N-1 ``~~`` joins and still ends with ``~``;
2. that the vector VERIFIES against the real AP2 reference SDK
   (``ap2.sdk.MandateClient``) using the embedded root public key; and
3. that the resolved payloads carry the expected, byte-exact claim values.

These vectors are frozen artifacts (see ``generate_vectors.py`` for the
reproducibility model); this test reads them, it never regenerates them.
"""

from __future__ import annotations

import json
import pathlib

from typing import Any

import pytest

from ap2.sdk.generated.open_checkout_mandate import OpenCheckoutMandate
from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate
from ap2.sdk.mandate import MandateClient
from jwcrypto.jwk import JWK


_VECTORS_PATH = (
    pathlib.Path(__file__).parent
    / 'delegate_sd_jwt_vectors'
    / 'delegate_sd_jwt_vectors.json'
)

# Root open-mandate model keyed by its ``vct``, for typed single-token verify.
_VCT_TO_MODEL = {
    'mandate.payment.open.1': OpenPaymentMandate,
    'mandate.checkout.open.1': OpenCheckoutMandate,
}


def _load() -> dict[str, Any]:
    return json.loads(_VECTORS_PATH.read_text())


_DATA = _load()
_VECTORS = _DATA['vectors']
_IDS = [v['id'] for v in _VECTORS]


def test_vector_file_version_metadata():
    """The frozen set carries its keyed version metadata (issue #303)."""
    version = _DATA['version']
    assert version['vector_set'] == 'ap2-delegate-sd-jwt/v1'
    assert (
        version['delegate_sd_jwt_draft'] == 'draft-gco-oauth-delegate-sd-jwt-00'
    )
    assert version['ap2_reference_commit'] == (
        'e1ea56db72a6385bce3e5c1112b3a56ce60acb43'
    )
    assert _VECTORS, 'vector set must be non-empty'


@pytest.mark.parametrize('vector', _VECTORS, ids=_IDS)
def test_wire_shape_invariants(vector: dict[str, Any]):
    """RFC 9901 + dSD-JWT ``~~`` wire invariants hold for each vector."""
    token = vector['compact_serialization']
    exp = vector['expected']

    # A single SD-JWT ends with exactly one '~'; a chain's final hop does too.
    assert token.endswith('~'), 'compact serialization must end with ~'
    assert exp['ends_with_tilde'] is True

    # An N-segment chain is joined by exactly N-1 '~~'.
    segments = token.split('~~')
    assert len(segments) == exp['hop_count']
    assert token.count('~~') == exp['double_tilde_joins']
    assert exp['double_tilde_joins'] == exp['hop_count'] - 1

    # A single SD-JWT (one segment) must carry no chain join.
    if exp['hop_count'] == 1:
        assert '~~' not in token

    # Every segment is a well-formed SD-JWT: a 3-part JWT followed by zero or
    # more disclosures. The cnf disclosure guarantees the delegation path never
    # emits a zero-disclosure segment for the delegating (open) hops.
    for i, seg in enumerate(segments):
        is_final = i == len(segments) - 1
        # Re-attach the '~' that ~~-joining strips from non-final segments.
        canonical = seg if (is_final or seg.endswith('~')) else seg + '~'
        head = canonical.split('~', 1)[0]
        assert len(head.split('.')) == 3, f'segment {i} is not a compact JWT'


@pytest.mark.parametrize('vector', _VECTORS, ids=_IDS)
def test_vector_verifies_against_sdk(vector: dict[str, Any]):
    """Each frozen vector verifies against the real AP2 SDK verifier."""
    token = vector['compact_serialization']
    root_pub = JWK.from_json(json.dumps(vector['root_public_jwk']))
    ver = vector['verification']
    client = MandateClient()

    if vector['expected']['hop_count'] == 1:
        # Single token: typed verify via the public MandateClient API.
        first_vct = vector['expected']['payload_assertions'][0]
        assert first_vct['path'] == [0, 'vct']
        model = _VCT_TO_MODEL[first_vct['equals']]
        mandate = client.verify(
            token=token,
            key_or_provider=root_pub,
            payload_type=model,
            expected_aud=ver['expected_aud'],
            expected_nonce=ver['expected_nonce'],
        )
        payloads = [mandate.mandate_payload.model_dump(by_alias=True)]
    else:
        # Chain: root hop keyed by the embedded root public key; aud/nonce
        # enforced on the terminal hop.
        payloads = client.verify(
            token=token,
            key_or_provider=lambda _t: root_pub,
            expected_aud=ver['expected_aud'],
            expected_nonce=ver['expected_nonce'],
        )

    assert len(payloads) == vector['expected']['hop_count']
    _check_assertions(payloads, vector['expected']['payload_assertions'])


def _check_assertions(
    payloads: list[dict[str, Any]],
    assertions: list[dict[str, Any]],
) -> None:
    """Walk each ``[index, key, ...]`` path and enforce its expectation."""
    for a in assertions:
        path = a['path']
        node: Any = payloads[path[0]]
        missing = False
        for key in path[1:]:
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                missing = True
                break
        if a.get('absent'):
            assert missing or node is None, f'{path} should be absent'
        elif a.get('present'):
            assert not missing and node is not None, f'{path} should be present'
        else:
            assert not missing, f'{path} missing; cannot equal {a["equals"]!r}'
            assert node == a['equals'], f'{path}: {node!r} != {a["equals"]!r}'


def test_multi_hop_chain_is_the_bank_sa_cp_merchant_flow():
    """The multi-hop vector is a genuine 3-party delegation chain."""
    vector = next(v for v in _VECTORS if v['id'] == 'multi-hop-payment-chain')
    assert vector['expected']['hop_count'] == 3
    assert vector['expected']['double_tilde_joins'] == 2
    assert vector['delegation_kids'] == ['user-root', 'agent-sa', 'provider-cp']
