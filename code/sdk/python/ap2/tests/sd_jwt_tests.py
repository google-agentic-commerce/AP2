"""Tests for the root SD-JWT primitive (``ap2.sdk.sdjwt.sd_jwt``)."""

from __future__ import annotations

import hashlib
import re

import pytest

from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.mandate import SdJwtMandate
from ap2.sdk.sdjwt import (
    compute_issuer_jwt_hash,
    compute_sd_hash,
    parse_token,
    sd_jwt,
)
from ap2.sdk.utils import b64url_encode
from ap2.tests.conftest import fake_sd_jwt, make_cnf
from cryptography.hazmat.primitives.asymmetric import ec


def _payment_payload():
    return PaymentMandate(
        transaction_id='tx_123',
        payee=Merchant(name='Shop', id='shop_id'),
        payment_amount=Amount(amount=10050, currency='USD'),
        payment_instrument=PaymentInstrument(id='123', type='credit'),
    )


# ── sd_jwt.create / sd_jwt.verify round-trip ─────────────────────────────


def test_create_then_verify_roundtrip(issuer_key, issuer_public_key):
    """A freshly-created SD-JWT verifies with the issuer's public key."""
    issuer = sd_jwt.create(payload=_payment_payload(), issuer_key=issuer_key)
    resolved = sd_jwt.verify(issuer.sd_jwt_issuance, issuer_public_key)
    assert 'delegate_payload' in resolved
    disclosed = [i for i in resolved['delegate_payload'] if isinstance(i, dict)]
    assert len(disclosed) == 1
    assert disclosed[0]['transaction_id'] == 'tx_123'


def test_verify_wrong_key_raises(issuer_key):
    """Verification with the wrong public key raises."""
    issuer = sd_jwt.create(payload=_payment_payload(), issuer_key=issuer_key)
    wrong_key = ec.generate_private_key(ec.SECP256R1()).public_key()
    with pytest.raises(Exception):
        sd_jwt.verify(issuer.sd_jwt_issuance, wrong_key)


def test_create_rejects_non_basemodel_payload(issuer_key):
    """``create`` refuses non-Pydantic payloads."""
    with pytest.raises(TypeError, match='pydantic.BaseModel'):
        sd_jwt.create(payload={'vct': 'x'}, issuer_key=issuer_key)


def test_create_emits_no_kb_binding_claims(issuer_key, issuer_public_key):
    """Root SD-JWT carries no ``iat``/``aud``/``nonce``/``sd_hash`` claims."""
    issuer = sd_jwt.create(payload=_payment_payload(), issuer_key=issuer_key)
    resolved = sd_jwt.verify(issuer.sd_jwt_issuance, issuer_public_key)
    assert 'iat' not in resolved
    assert 'aud' not in resolved
    assert 'nonce' not in resolved
    assert 'sd_hash' not in resolved
    assert 'issuer_jwt_hash' not in resolved


# ── SdJwtMandate typed wrapper (uses sd_jwt.verify under the hood) ───────


def test_sdjwt_mandate_from_sd_jwt_happy(issuer_key, issuer_public_key):
    """``SdJwtMandate.from_sd_jwt`` parses the payload back into its type."""
    issuer = sd_jwt.create(payload=_payment_payload(), issuer_key=issuer_key)
    parsed = SdJwtMandate.from_sd_jwt(
        issuer.sd_jwt_issuance, issuer_public_key, PaymentMandate
    )
    assert isinstance(parsed.mandate_payload, PaymentMandate)
    assert parsed.mandate_payload.transaction_id == 'tx_123'
    assert parsed.is_valid()
    assert '~' in parsed.serialized


def test_sdjwt_mandate_wrong_key_raises(issuer_key):
    """A wrong public key fails the ``from_sd_jwt`` factory."""
    issuer = sd_jwt.create(payload=_payment_payload(), issuer_key=issuer_key)
    wrong_key = ec.generate_private_key(ec.SECP256R1()).public_key()
    with pytest.raises(Exception):
        SdJwtMandate.from_sd_jwt(
            issuer.sd_jwt_issuance, wrong_key, PaymentMandate
        )


def test_sdjwt_mandate_malformed_token_raises():
    """Malformed tokens are rejected."""
    key = ec.generate_private_key(ec.SECP256R1()).public_key()
    with pytest.raises(Exception):
        SdJwtMandate.from_sd_jwt('not-a-valid-sd-jwt~', key, PaymentMandate)


def test_parse_token_rejects_leading_separator():
    """Malformed tokens must not be silently canonicalized."""
    token = fake_sd_jwt({'vct': 'test'})
    with pytest.raises(ValueError, match='empty issuer JWT'):
        parse_token(f'~{token}')


def test_parse_token_rejects_empty_disclosure_segment():
    """Empty disclosure segments are malformed SD-JWT input."""
    token = fake_sd_jwt({'vct': 'test'})
    with pytest.raises(ValueError, match='empty disclosure segment'):
        parse_token(token[:-1] + '~~')


def test_parse_token_rejects_malformed_kb_jwt():
    """Malformed KB-JWT segments are rejected explicitly."""
    token = fake_sd_jwt({'vct': 'test'})
    with pytest.raises(ValueError, match='Malformed KB-JWT'):
        parse_token(token + 'not-a-kb-jwt')


# ── Hashing helpers ──────────────────────────────────────────────────────


def test_compute_sd_hash_is_nonempty_base64url():
    """``compute_sd_hash`` returns a non-empty base64url string."""
    token = fake_sd_jwt({'vct': 'test'})
    h = compute_sd_hash(parse_token(token))
    assert h and re.fullmatch(r'[A-Za-z0-9_-]+', h)


def test_compute_sd_hash_strips_trailing_kb_jwt():
    """Appending a KB-JWT does not change the SD-JWT hash (KB-JWT stripped)."""
    base = fake_sd_jwt({'vct': 'test'})
    with_kb = base + 'kb.jwt.here'
    assert compute_sd_hash(parse_token(base)) == compute_sd_hash(
        parse_token(with_kb)
    )


def test_compute_sd_hash_covers_disclosures():
    """Changing a disclosure changes ``sd_hash``."""
    base = fake_sd_jwt({'vct': 'test'})
    # Append a fake disclosure segment.
    with_extra_disc = base[:-1] + '~ZmFrZS1kaXNjbG9zdXJl~'
    assert compute_sd_hash(parse_token(base)) != compute_sd_hash(
        parse_token(with_extra_disc)
    )


def test_compute_sd_hash_uses_sd_alg_from_payload():
    token = fake_sd_jwt({'vct': 'test', '_sd_alg': 'sha-512'})
    expected = b64url_encode(hashlib.sha512(token.encode('ascii')).digest())
    assert compute_sd_hash(parse_token(token)) == expected


def test_compute_issuer_jwt_hash_is_nonempty():
    token = fake_sd_jwt({'vct': 'test'})
    h = compute_issuer_jwt_hash(parse_token(token))
    assert h and re.fullmatch(r'[A-Za-z0-9_-]+', h)


def test_compute_issuer_jwt_hash_ignores_disclosures():
    """``issuer_jwt_hash`` does NOT change when disclosures are added/removed."""
    base = fake_sd_jwt({'vct': 'test'})
    with_extra_disc = base[:-1] + '~ZmFrZS1kaXNjbG9zdXJl~'
    assert compute_issuer_jwt_hash(
        parse_token(base)
    ) == compute_issuer_jwt_hash(parse_token(with_extra_disc))


def test_compute_issuer_jwt_hash_differs_from_sd_hash_when_disclosures_present():
    """The two hashes must differ once disclosures exist."""
    token = fake_sd_jwt({'vct': 'test'})
    token_with_disc = token[:-1] + '~ZmFrZS1kaXNjbG9zdXJl~'
    assert compute_sd_hash(
        parse_token(token_with_disc)
    ) != compute_issuer_jwt_hash(parse_token(token_with_disc))


def test_compute_issuer_jwt_hash_uses_sd_alg_from_payload():
    token = fake_sd_jwt({'vct': 'test', '_sd_alg': 'sha-384'})
    jwt_part = token.split('~', maxsplit=1)[0]
    expected = b64url_encode(hashlib.sha384(jwt_part.encode('ascii')).digest())
    assert compute_issuer_jwt_hash(parse_token(token)) == expected


# ── Auto-SD from Pydantic model annotations ──────────────────────────────


def test_create_picks_up_sd_annotations(issuer_key, issuer_public_key):
    """``sd=None`` auto-derives SD metadata from the model's annotations."""
    dummy_key = ec.generate_private_key(ec.SECP256R1())
    model = OpenPaymentMandate(
        constraints=[], cnf=make_cnf(dummy_key.public_key())
    )
    issuer = sd_jwt.create(payload=model, issuer_key=issuer_key)
    resolved = sd_jwt.verify(issuer.sd_jwt_issuance, issuer_public_key)
    assert 'delegate_payload' in resolved
