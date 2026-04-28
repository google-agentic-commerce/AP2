"""End-to-end privacy property: ``hash_mode='issuer_jwt_hash'`` lets the
next delegate redact disclosures from the preceding SD-JWT without breaking
chain verification.

Setup: Bank → SA → CP → Merchant, where SA's KB-SD-JWT+KB binds to Bank via
``issuer_jwt_hash`` (draft-gco-oauth-delegate-sd-jwt-00 §5.1.4). CP, while
forwarding to the Merchant, drops one of Bank's disclosures. Verification
MUST still pass. The parallel test flips SA to ``hash_mode='sd_hash'`` and
asserts that the same redaction breaks verification.
"""

from __future__ import annotations

import json

import pytest

from ap2.sdk.disclosure_metadata import DisclosureMetadata
from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.mandate import MandateClient
from ap2.sdk.sdjwt import kb_sd_jwt, parse_token, sd_jwt
from ap2.sdk.utils import b64url_decode
from ap2.tests.conftest import make_cnf, sample_payment_mandate
from cryptography.hazmat.primitives.asymmetric import ec
from jwcrypto.jwk import JWK


def _mkkey(kid: str) -> JWK:
    k = ec.generate_private_key(ec.SECP256R1())
    jwk = JWK.from_pyca(k)
    d = json.loads(jwk.export())
    d['kid'] = kid
    return JWK.from_json(json.dumps(d))


def _strip_tilde(s: str) -> str:
    return s[:-1] if s.endswith('~') else s


def _parse(token: str):
    return parse_token(token)


def _bank_open_with_sd(sa_pub: JWK) -> OpenPaymentMandate:
    """Bank issues an open mandate with amount & payee as SD fields."""
    return OpenPaymentMandate(
        constraints=[],
        cnf=make_cnf(sa_pub),
        payment_amount=Amount(amount=1000, currency='USD'),
        payee=Merchant(id='m-1', name='Shop'),
    )


def _find_disclosure_for(segment: str, claim_name: str) -> str:
    """Return the disclosure inside ``segment`` whose claim name is ``claim_name``."""
    for d in segment.split('~')[1:]:
        if not d:
            continue
        try:
            decoded = json.loads(b64url_decode(d).decode('utf-8'))
        except Exception:
            continue
        if (
            isinstance(decoded, list)
            and len(decoded) == 3
            and decoded[1] == claim_name
        ):
            return d
    raise AssertionError(
        f'disclosure for claim {claim_name!r} not found in segment'
    )


def _drop_disclosure(segment: str, disclosure: str) -> str:
    """Return ``segment`` with ``disclosure`` removed (trailing ``~`` preserved)."""
    head, tail = (
        segment.rsplit('~', 1) if segment.endswith('~') else (segment, None)
    )
    parts = head.split('~')
    parts = [p for p in parts if p != disclosure]
    rebuilt = '~'.join(parts)
    if tail is not None:
        rebuilt += '~'
    return rebuilt


def _build_three_hop_chain(
    bank_key: JWK,
    sa_key: JWK,
    cp_key: JWK,
    sa_to_cp_aud: str = 'cp',
    sa_to_cp_nonce: str = 'n-cp',
    cp_to_merchant_aud: str = 'merchant',
    cp_to_merchant_nonce: str = 'n-m',
    hash_mode: str = 'sd_hash',
) -> tuple[str, str, str]:
    """Return (bank_segment, sa_segment, cp_segment) for a Bank→SA→CP chain.

    ``hash_mode`` controls SA's KB-SD-JWT+KB binding mode against the Bank
    SD-JWT. CP's terminal hop always uses ``sd_hash`` (it is the last hop).
    """
    sa_pub = JWK.from_json(sa_key.export_public())
    cp_pub = JWK.from_json(cp_key.export_public())

    bank = sd_jwt.create(
        payload=_bank_open_with_sd(sa_pub),
        issuer_key=bank_key,
        sd=DisclosureMetadata(sd_keys=['payment_amount', 'payee']),
    ).sd_jwt_issuance

    sa = kb_sd_jwt.create(
        prev_token=_parse(bank),
        holder_key=sa_key,
        payload=OpenPaymentMandate(constraints=[], cnf=make_cnf(cp_pub)),
        aud=sa_to_cp_aud,
        nonce=sa_to_cp_nonce,
        hash_mode=hash_mode,
    ).sd_jwt_issuance

    cp = kb_sd_jwt.create(
        prev_token=_parse(sa),
        holder_key=cp_key,
        payload=sample_payment_mandate(),
        aud=cp_to_merchant_aud,
        nonce=cp_to_merchant_nonce,
        hash_mode='sd_hash',
    ).sd_jwt_issuance

    return bank, sa, cp


# ── Positive property: issuer_jwt_hash permits downstream redaction ──────


def test_issuer_jwt_hash_allows_cp_to_drop_bank_disclosure():
    """Bank->SA(issuer_jwt_hash)->CP: CP drops d_amount, chain still verifies."""
    bank_key = _mkkey('bank')
    sa_key = _mkkey('sa')
    cp_key = _mkkey('cp')

    bank_seg, sa_seg, cp_seg = _build_three_hop_chain(
        bank_key, sa_key, cp_key, hash_mode='issuer_jwt_hash'
    )

    amount_disclosure = _find_disclosure_for(bank_seg, 'payment_amount')
    redacted_bank = _drop_disclosure(bank_seg, amount_disclosure)
    assert amount_disclosure in bank_seg
    assert amount_disclosure not in redacted_bank

    chain = f'{_strip_tilde(redacted_bank)}~~{_strip_tilde(sa_seg)}~~{cp_seg}'

    bank_pub = JWK.from_json(bank_key.export_public())
    payloads = MandateClient().verify(
        token=chain,
        key_or_provider=lambda _token: bank_pub,
        expected_aud='merchant',
        expected_nonce='n-m',
    )
    assert len(payloads) == 3
    # The dropped disclosure is not visible to the verifier.
    assert 'payment_amount' not in payloads[0]


# ── Negative property: sd_hash locks in the preceding disclosures ────────


def test_sd_hash_mode_rejects_cp_dropping_bank_disclosure():
    """Same setup with hash_mode='sd_hash' on SA -> chain no longer verifies."""
    bank_key = _mkkey('bank')
    sa_key = _mkkey('sa')
    cp_key = _mkkey('cp')

    bank_seg, sa_seg, cp_seg = _build_three_hop_chain(
        bank_key, sa_key, cp_key, hash_mode='sd_hash'
    )

    amount_disclosure = _find_disclosure_for(bank_seg, 'payment_amount')
    redacted_bank = _drop_disclosure(bank_seg, amount_disclosure)

    chain = f'{_strip_tilde(redacted_bank)}~~{_strip_tilde(sa_seg)}~~{cp_seg}'

    bank_pub = JWK.from_json(bank_key.export_public())
    with pytest.raises(ValueError, match='sd_hash mismatch'):
        MandateClient().verify(
            token=chain,
            key_or_provider=lambda _token: bank_pub,
            expected_aud='merchant',
            expected_nonce='n-m',
        )


# ── Control: issuer_jwt_hash without redaction still verifies ────────────


def test_issuer_jwt_hash_chain_without_redaction_verifies():
    """Emit issuer_jwt_hash but forward every disclosure: still valid."""
    bank_key = _mkkey('bank')
    sa_key = _mkkey('sa')
    cp_key = _mkkey('cp')

    bank_seg, sa_seg, cp_seg = _build_three_hop_chain(
        bank_key, sa_key, cp_key, hash_mode='issuer_jwt_hash'
    )
    chain = f'{_strip_tilde(bank_seg)}~~{_strip_tilde(sa_seg)}~~{cp_seg}'

    bank_pub = JWK.from_json(bank_key.export_public())
    payloads = MandateClient().verify(
        token=chain,
        key_or_provider=lambda _token: bank_pub,
        expected_aud='merchant',
        expected_nonce='n-m',
    )
    assert len(payloads) == 3
