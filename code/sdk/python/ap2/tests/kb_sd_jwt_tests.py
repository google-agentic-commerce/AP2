"""Tests for the terminal KB-SD-JWT primitive.

Covers the closing hop of a dSD-JWT chain: ``typ=kb+sd-jwt``, no ``cnf``,
both ``hash_mode`` options.
"""

from __future__ import annotations

import base64
import json

import pytest

from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate
from ap2.sdk.sdjwt import (
    compute_issuer_jwt_hash,
    compute_sd_hash,
    kb_sd_jwt,
    parse_token,
    sd_jwt,
)
from ap2.tests.conftest import make_cnf, sample_payment_mandate
from jwcrypto.jwk import JWK


def _decode_jwt_header(token: str) -> dict:
    jwt_part = token.split('~', maxsplit=1)[0]
    header_b64 = jwt_part.split('.')[0]
    padded = header_b64 + '=' * (-len(header_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def _decode_jwt_payload(token: str) -> dict:
    jwt_part = token.split('~', maxsplit=1)[0]
    payload_b64 = jwt_part.split('.')[1]
    padded = payload_b64 + '=' * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def _create(**kwargs):
    kwargs['prev_token'] = parse_token(kwargs['prev_token'])
    return kb_sd_jwt.create(**kwargs)


def _verify(token: str, prev_token: str, prev_issuer_key: JWK, **kwargs):
    parsed_prev = parse_token(prev_token)
    prev_issuer_pub = JWK.from_json(prev_issuer_key.export_public())
    prev_payload = sd_jwt.verify(parsed_prev.canonical, prev_issuer_pub)
    verified_prev = parsed_prev.with_verified_payload(prev_payload, [])
    return kb_sd_jwt.verify(
        parse_token(token),
        verified_prev,
        **kwargs,
    )


def _root_open(issuer_key, holder_jwk) -> str:
    """Helper: sign a root OpenPaymentMandate with ``holder_jwk`` bound to cnf."""
    return sd_jwt.create(
        payload=OpenPaymentMandate(constraints=[], cnf=make_cnf(holder_jwk)),
        issuer_key=issuer_key,
    ).sd_jwt_issuance


# ── Happy paths ──────────────────────────────────────────────────────────


def test_create_sets_typ_and_binding(issuer_key):
    """Header typ=kb+sd-jwt; payload has iat + sd_hash (aud/nonce optional)."""
    holder = JWK.generate(kty='EC', crv='P-256')
    prev = _root_open(issuer_key, holder)

    result = _create(
        prev_token=prev,
        holder_key=holder,
        payload=sample_payment_mandate(),
        aud='https://merchant.example',
        nonce='merchant-n1',
    )
    assert _decode_jwt_header(result.sd_jwt_issuance)['typ'] == 'kb+sd-jwt'
    payload = _decode_jwt_payload(result.sd_jwt_issuance)
    assert payload['aud'] == 'https://merchant.example'
    assert payload['nonce'] == 'merchant-n1'
    assert isinstance(payload['iat'], int)
    assert payload['sd_hash'] == compute_sd_hash(parse_token(prev))
    assert 'issuer_jwt_hash' not in payload


def test_create_requires_aud_nonce(issuer_key):
    """Terminal hop requires ``aud`` and ``nonce``."""
    holder = JWK.generate(kty='EC', crv='P-256')
    prev = _root_open(issuer_key, holder)
    with pytest.raises(ValueError, match='aud and nonce'):
        _create(
            prev_token=prev,
            holder_key=holder,
            payload=sample_payment_mandate(),
            aud='a',
            nonce='',
        )


def test_create_hash_mode_issuer_jwt_hash(issuer_key):
    holder = JWK.generate(kty='EC', crv='P-256')
    prev = _root_open(issuer_key, holder)
    result = _create(
        prev_token=prev,
        holder_key=holder,
        payload=sample_payment_mandate(),
        aud='a',
        nonce='n',
        hash_mode='issuer_jwt_hash',
    )
    payload = _decode_jwt_payload(result.sd_jwt_issuance)
    assert 'sd_hash' not in payload
    assert payload['issuer_jwt_hash'] == compute_issuer_jwt_hash(
        parse_token(prev)
    )


def test_verify_accepts_valid_hop(issuer_key):
    holder = JWK.generate(kty='EC', crv='P-256')
    prev = _root_open(issuer_key, holder)
    result = _create(
        prev_token=prev,
        holder_key=holder,
        payload=sample_payment_mandate(),
        aud='a',
        nonce='n',
    )
    _verify(
        result.sd_jwt_issuance,
        prev,
        issuer_key,
        expected_aud='a',
        expected_nonce='n',
    )


def test_verify_accepts_issuer_jwt_hash_mode(issuer_key):
    holder = JWK.generate(kty='EC', crv='P-256')
    prev = _root_open(issuer_key, holder)
    result = _create(
        prev_token=prev,
        holder_key=holder,
        payload=sample_payment_mandate(),
        aud='a',
        nonce='n',
        hash_mode='issuer_jwt_hash',
    )
    _verify(result.sd_jwt_issuance, prev, issuer_key)


# ── Negative cases ───────────────────────────────────────────────────────


def test_create_infers_intermediate_from_cnf(issuer_key):
    """Payloads with ``cnf`` become intermediate KB-SD-JWT+KB hops."""
    holder = JWK.generate(kty='EC', crv='P-256')
    prev = _root_open(issuer_key, holder)
    next_jwk = JWK.generate(kty='EC', crv='P-256')
    result = _create(
        prev_token=prev,
        holder_key=holder,
        payload=OpenPaymentMandate(constraints=[], cnf=make_cnf(next_jwk)),
        aud='a',
        nonce='n',
    )

    assert _decode_jwt_header(result.sd_jwt_issuance)['typ'] == 'kb+sd-jwt+kb'


def test_verify_rejects_wrong_key(issuer_key):
    holder = JWK.generate(kty='EC', crv='P-256')
    prev = _root_open(issuer_key, holder)
    wrong_holder = JWK.generate(kty='EC', crv='P-256')
    result = _create(
        prev_token=prev,
        holder_key=wrong_holder,
        payload=sample_payment_mandate(),
        aud='a',
        nonce='n',
    )
    with pytest.raises(Exception):
        _verify(result.sd_jwt_issuance, prev, issuer_key)


def test_verify_accepts_intermediate_typ(issuer_key):
    """Unified verifier accepts intermediate KB-SD-JWT+KB hops."""
    holder = JWK.generate(kty='EC', crv='P-256')
    prev = _root_open(issuer_key, holder)
    next_jwk = JWK.generate(kty='EC', crv='P-256')
    intermediate = _create(
        prev_token=prev,
        holder_key=holder,
        payload=OpenPaymentMandate(constraints=[], cnf=make_cnf(next_jwk)),
        aud='a',
        nonce='n',
    )
    payload = _verify(intermediate.sd_jwt_issuance, prev, issuer_key)
    assert payload['aud'] == 'a'


def test_verify_rejects_binding_mismatch(issuer_key):
    holder = JWK.generate(kty='EC', crv='P-256')
    prev = _root_open(issuer_key, holder)
    result = _create(
        prev_token=prev,
        holder_key=holder,
        payload=sample_payment_mandate(),
        aud='a',
        nonce='n',
    )
    other_prev = _root_open(issuer_key, holder)
    with pytest.raises(ValueError, match='sd_hash mismatch'):
        _verify(result.sd_jwt_issuance, other_prev, issuer_key)


def test_verify_rejects_aud_mismatch(issuer_key):
    holder = JWK.generate(kty='EC', crv='P-256')
    prev = _root_open(issuer_key, holder)
    result = _create(
        prev_token=prev,
        holder_key=holder,
        payload=sample_payment_mandate(),
        aud='correct',
        nonce='n',
    )
    with pytest.raises(ValueError, match='aud mismatch'):
        _verify(result.sd_jwt_issuance, prev, issuer_key, expected_aud='wrong')


def test_verify_rejects_nonce_mismatch(issuer_key):
    holder = JWK.generate(kty='EC', crv='P-256')
    prev = _root_open(issuer_key, holder)
    result = _create(
        prev_token=prev,
        holder_key=holder,
        payload=sample_payment_mandate(),
        aud='a',
        nonce='correct',
    )
    with pytest.raises(ValueError, match='nonce mismatch'):
        _verify(
            result.sd_jwt_issuance,
            prev,
            issuer_key,
            expected_aud='a',
            expected_nonce='wrong',
        )
