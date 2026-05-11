"""Tests for dSD-JWT chain verification (ap2.sdk.sdjwt.chain.verify_chain)."""

import base64
import datetime
import json
import re
import time

import pytest

from ap2.sdk.disclosure_metadata import DisclosureMetadata
from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.mandate import MandateClient
from ap2.sdk.sdjwt import chain as chain_mod
from ap2.sdk.sdjwt import (
    common,
    compute_sd_hash,
    kb_sd_jwt,
    parse_token,
    sd_jwt,
)
from ap2.sdk.sdjwt.chain import verify_chain as verify_delegate_sd_jwt
from ap2.sdk.utils import b64url_decode, b64url_encode, ec_key_to_jwk
from ap2.tests.conftest import (
    fake_sd_jwt,
    make_cnf,
    sample_payment_mandate,
)
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jwcrypto.jwk import JWK
from sd_jwt.issuer import SDJWTIssuer


def _parse(token: str) -> common.ParsedToken:
    return parse_token(token)


def _parse_many(tokens: list[str]) -> list[common.ParsedToken]:
    return [_parse(token) for token in tokens]


# ── Helper functions for X.509 Tests ─────────────────────────────────────


def _generate_test_cert(
    common_name: str,
    issuer_name: x509.Name | None = None,
    issuer_key: ec.EllipticCurvePrivateKey | None = None,
) -> tuple[ec.EllipticCurvePrivateKey, x509.Name, x509.Certificate]:
    """Helper to generate a temporary ECDSA keypair and X.509 Certificate."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name(
        [x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, common_name)]
    )

    # Self-sign if no issuer is provided (i.e., this is a Root CA)
    if not issuer_name or not issuer_key:
        issuer_name = name
        issuer_key = key

    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(issuer_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(
            datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1)
        )
        .sign(issuer_key, hashes.SHA256())
    )
    return key, name, cert


# ── Utility function tests ───────────────────────────────────────────────


def test_b64url_roundtrip():
    """Encode then decode returns the original bytes."""
    data = b'hello world \x00\xff'
    assert b64url_decode(b64url_encode(data)) == data


def test_ec_key_to_jwk():
    """ec_key_to_jwk returns a valid JwkPublicKey for a P-256 key."""
    key = ec.generate_private_key(ec.SECP256R1())
    jwk = ec_key_to_jwk(key.public_key())
    assert jwk.kty == 'EC'
    assert jwk.crv == 'P-256'
    assert len(jwk.x) == 43
    assert len(jwk.y) == 43


def test_ec_key_to_jwk_rejects_non_p256():
    """A P-384 key is rejected by ec_key_to_jwk."""
    key = ec.generate_private_key(ec.SECP384R1())
    with pytest.raises(ValueError, match='Expected uncompressed P-256 point'):
        ec_key_to_jwk(key.public_key())


# ── compute_sd_hash ──────────────────────────────────────────────────────


def test_compute_sd_hash_roundtrip():
    """compute_sd_hash returns a non-empty base64url string."""
    token = fake_sd_jwt({'vct': 'test'})
    h = compute_sd_hash(_parse(token))
    assert h
    assert isinstance(h, str)
    assert re.fullmatch(r'[A-Za-z0-9_-]+', h)


def test_compute_sd_hash_strips_kb_jwt():
    """Appending a KB-JWT does not change the hash (it is stripped)."""
    base = fake_sd_jwt({'vct': 'test'})
    with_kb = base + 'kb.jwt.here'
    assert compute_sd_hash(_parse(base)) == compute_sd_hash(_parse(with_kb))


def test_disclosures_are_resolved_per_token():
    """A token only resolves `_sd` digests from its own disclosures."""
    disclosure = b64url_encode(
        json.dumps(['salt', 'secret', {'ok': True}]).encode()
    )
    digest = common.compute_disclosure_digest(disclosure, sd_alg=None)
    item = {'_sd': [digest]}

    token_with_disclosure = parse_token(
        fake_sd_jwt({'vct': 'test'})[:-1] + f'~{disclosure}~'
    )
    token_without_disclosure = parse_token(fake_sd_jwt({'vct': 'test'}))

    assert chain_mod._resolve_delegate_items(
        [item.copy()], token_with_disclosure, 0
    )[0]['secret'] == {'ok': True}
    assert (
        'secret'
        not in chain_mod._resolve_delegate_items(
            [item.copy()], token_without_disclosure, 1
        )[0]
    )


# ── verify_delegate_sd_jwt: single token ─────────────────────────────────


def test_verify_single_token_with_key(user_key, user_public_key):
    """A single token is verified when its issuer key is provided."""
    client = MandateClient()
    token = client.create(
        payloads=[
            OpenPaymentMandate(
                constraints=[],
                cnf=make_cnf(user_key),
            )
        ],
        issuer_key=user_key,
    )
    payloads = client.verify(
        token=token,
        key_or_provider=user_public_key,
        payload_type=OpenPaymentMandate,
    )
    assert payloads.mandate_payload.vct == 'mandate.payment.open.1'


def test_verify_single_token_wrong_key(user_key):
    """Verification with the wrong key raises."""
    client = MandateClient()
    token = client.create(
        payloads=[
            OpenPaymentMandate(
                constraints=[],
                cnf=make_cnf(user_key),
            )
        ],
        issuer_key=user_key,
    )
    wrong_key = ec.generate_private_key(ec.SECP256R1()).public_key()
    with pytest.raises(Exception):
        client.verify(
            token=token,
            key_or_provider=lambda _token: wrong_key,
        )


# ── verify_delegate_sd_jwt: delegation chain ─────────────────────────────


def test_delegation_chain_cnf_binding(
    user_key,
    user_public_key,
    agent_key,
    holder,
):
    """Open mandate verified with provider key; closed verified via cnf.jwk."""
    client = MandateClient()
    open_tok = client.create(
        payloads=[
            OpenPaymentMandate(
                constraints=[],
                cnf=make_cnf(agent_key),
            )
        ],
        issuer_key=user_key,
    )
    tok_chain = holder.present(
        holder_key=agent_key,
        mandate_token=open_tok,
        payloads=[sample_payment_mandate()],
        aud='merchant',
        nonce='merchant-nonce',
    )

    payloads = holder.verify(
        token=tok_chain,
        key_or_provider=lambda _token: user_public_key,
    )
    assert len(payloads) == 2
    assert payloads[0]['vct'] == 'mandate.payment.open.1'
    assert payloads[1]['transaction_id'] == 'tx_1'


def test_delegation_chain_cnf_mismatch(
    user_key,
    user_public_key,
    agent_key,
    holder,
):
    """A closed mandate signed by the wrong key is rejected via cnf mismatch."""
    other_jwk = JWK.generate(kty='EC', crv='P-256')

    client = MandateClient()
    open_tok = client.create(
        payloads=[
            OpenPaymentMandate(
                constraints=[],
                cnf=make_cnf(agent_key),
            )
        ],
        issuer_key=user_key,
    )
    tok_chain = holder.present(
        holder_key=other_jwk,
        mandate_token=open_tok,
        payloads=[sample_payment_mandate()],
        aud='merchant',
        nonce='merchant-nonce',
    )

    with pytest.raises(Exception):
        holder.verify(
            token=tok_chain,
            key_or_provider=lambda _token: user_public_key,
        )


# ── verify_delegate_sd_jwt: temporal validity ─────────────────────────────


def test_temporal_expired_token(user_key, user_public_key, holder):
    """A token whose exp is in the distant past is rejected."""
    payload = OpenPaymentMandate(
        constraints=[],
        cnf=make_cnf(user_key),
    )
    claims = payload.model_dump(by_alias=True, exclude_none=True)
    claims['exp'] = 1000

    issuer = SDJWTIssuer(
        user_claims=claims,
        issuer_key=user_key,
        extra_header_parameters={'kid': 'user-key-1'},
    )
    with pytest.raises(ValueError, match='expired'):
        holder.verify(
            token=issuer.sd_jwt_issuance,
            key_or_provider=user_public_key,
            payload_type=OpenPaymentMandate,
        )


def test_temporal_future_iat(user_key, user_public_key, holder):
    """A token whose iat is far in the future is rejected."""
    payload = OpenPaymentMandate(
        constraints=[],
        cnf=make_cnf(user_key),
    )
    claims = payload.model_dump(by_alias=True, exclude_none=True)
    claims['iat'] = 9999999999

    issuer = SDJWTIssuer(
        user_claims=claims,
        issuer_key=user_key,
        extra_header_parameters={'kid': 'user-key-1'},
    )
    with pytest.raises(ValueError, match='in the future'):
        holder.verify(
            token=issuer.sd_jwt_issuance,
            key_or_provider=user_public_key,
            payload_type=OpenPaymentMandate,
        )


def test_temporal_clock_skew_within_tolerance(
    user_key,
    user_public_key,
    holder,
):
    """A token expired barely in the past passes with default 300s skew."""
    now = int(time.time())
    payload = OpenPaymentMandate(
        constraints=[],
        cnf=make_cnf(user_key),
    )
    claims = payload.model_dump(by_alias=True, exclude_none=True)
    claims['exp'] = now - 100

    issuer = SDJWTIssuer(
        user_claims=claims,
        issuer_key=user_key,
        extra_header_parameters={'kid': 'user-key-1'},
    )
    payloads = verify_delegate_sd_jwt(
        tokens=_parse_many([issuer.sd_jwt_issuance]),
        public_key_provider=lambda _token: user_public_key,
    )
    assert len(payloads) == 1


def test_delegation_chain_selective_disclosure(
    user_key,
    user_public_key,
    agent_key,
    holder,
):
    """Verify that only specified claims are disclosed in the presentation."""
    client = MandateClient()

    payload = OpenPaymentMandate(
        constraints=[],
        cnf=make_cnf(agent_key),
        payment_amount=Amount(amount=1000, currency='USD'),
        payee=Merchant(name='Shop', id='s-1'),
    )
    open_tok = client.create(
        payloads=[payload],
        issuer_key=user_key,
        sd=DisclosureMetadata(sd_keys=['payee', 'payment_amount']),
    )

    closed_payload = sample_payment_mandate(
        payment_amount=Amount(amount=1000, currency='USD')
    )

    presentation_token = holder.present(
        holder_key=agent_key,
        mandate_token=open_tok,
        payloads=[closed_payload],
        claims_to_disclose={
            'payment_amount': True,
        },
        aud='merchant',
        nonce='merchant-nonce',
    )

    payloads = client.verify(
        token=presentation_token,
        key_or_provider=lambda _token: user_public_key,
    )

    assert len(payloads) == 2
    assert payloads[0]['payment_amount']['amount'] == 1000
    assert 'payee' not in payloads[0]


# ── verify_delegate_sd_jwt: x5c chain verification ────────────────────────


def test_verify_x5c_chain_anchors_to_root():
    """Test that x5c chain is verified when the last cert is signed by a trusted root."""
    root_key, root_name, root_cert = _generate_test_cert('Root CA')
    leaf_key, _, leaf_cert = _generate_test_cert('Leaf', root_name, root_key)

    leaf_jwk = JWK.from_pyca(leaf_key)
    leaf_cert_b64 = base64.b64encode(
        leaf_cert.public_bytes(serialization.Encoding.DER)
    ).decode('utf-8')

    claims = {'vct': 'mandate.payment.open.1', 'iat': int(time.time())}
    issuer = SDJWTIssuer(
        user_claims=claims,
        issuer_key=leaf_jwk,
        extra_header_parameters={'x5c': [leaf_cert_b64]},
    )

    payloads = verify_delegate_sd_jwt(
        tokens=_parse_many([issuer.sd_jwt_issuance]),
        public_key_provider=chain_mod.X5cOrKidPublicKeyProvider(
            lambda _kid: None, trusted_roots=[root_cert]
        ),
    )
    assert len(payloads) == 1
    assert payloads[0]['vct'] == 'mandate.payment.open.1'


def test_verify_x5c_chain_anchors_via_intermediate():
    """Test that x5c chain is verified when an intermediate cert is signed by a trusted root."""
    root_key, root_name, root_cert = _generate_test_cert('Root CA')
    int_key, int_name, int_cert = _generate_test_cert(
        'Intermediate', root_name, root_key
    )
    leaf_key, _, leaf_cert = _generate_test_cert('Leaf', int_name, int_key)

    leaf_jwk = JWK.from_pyca(leaf_key)
    leaf_cert_b64 = base64.b64encode(
        leaf_cert.public_bytes(serialization.Encoding.DER)
    ).decode('utf-8')
    int_cert_b64 = base64.b64encode(
        int_cert.public_bytes(serialization.Encoding.DER)
    ).decode('utf-8')

    claims = {'vct': 'mandate.payment.open.1', 'iat': int(time.time())}
    issuer = SDJWTIssuer(
        user_claims=claims,
        issuer_key=leaf_jwk,
        extra_header_parameters={'x5c': [leaf_cert_b64, int_cert_b64]},
    )

    payloads = verify_delegate_sd_jwt(
        tokens=_parse_many([issuer.sd_jwt_issuance]),
        public_key_provider=chain_mod.X5cOrKidPublicKeyProvider(
            lambda _kid: None, trusted_roots=[root_cert]
        ),
    )
    assert len(payloads) == 1
    assert payloads[0]['vct'] == 'mandate.payment.open.1'


def test_verify_x5c_chain_fails_no_trusted_root():
    """Test that x5c chain fails verification when no cert is signed by a trusted root."""
    untrusted_root_key, untrusted_root_name, _ = _generate_test_cert(
        'Untrusted Root'
    )
    leaf_key, _, leaf_cert = _generate_test_cert(
        'Leaf', untrusted_root_name, untrusted_root_key
    )

    leaf_jwk = JWK.from_pyca(leaf_key)
    leaf_cert_b64 = base64.b64encode(
        leaf_cert.public_bytes(serialization.Encoding.DER)
    ).decode('utf-8')

    claims = {'vct': 'mandate.payment.open.1', 'iat': int(time.time())}
    issuer = SDJWTIssuer(
        user_claims=claims,
        issuer_key=leaf_jwk,
        extra_header_parameters={'x5c': [leaf_cert_b64]},
    )

    # Generate a completely unrelated trusted root
    _, _, unrelated_root_cert = _generate_test_cert('Unrelated Trusted Root')

    # Verify should fail because the leaf chains to the Untrusted Root, not the
    # Unrelated Root
    with pytest.raises(
        ValueError, match='Certificate chain does not chain to a trusted root'
    ):
        verify_delegate_sd_jwt(
            tokens=_parse_many([issuer.sd_jwt_issuance]),
            public_key_provider=chain_mod.X5cOrKidPublicKeyProvider(
                lambda _kid: None, trusted_roots=[unrelated_root_cert]
            ),
        )


# ── Bank -> SA -> CP -> Merchant (3-step example, byte-for-byte) ─────────


def _mk_signing_jwk(kid: str) -> JWK:
    """Helper: generate a fresh P-256 signing JWK with ``kid`` stamped on it."""
    k = ec.generate_private_key(ec.SECP256R1())
    jwk = JWK.from_pyca(k)
    d = json.loads(jwk.export())
    d['kid'] = kid
    return JWK.from_json(json.dumps(d))


def test_three_step_bank_sa_cp_merchant_flow():
    """Mirror the flow documented in the SDK plan, token-by-token.

    Step 1: Bank issues the open mandate to the user/SA (root SD-JWT,
            ``<Bank_SD-JWT>~[d]~``).
    Step 2: SA delegates to CP by appending a KB-SD-JWT+KB
            (``<Bank_SD-JWT>~[d]~~<SA_KB-SD-JWT+KB>[d]~``).
    Step 3: CP closes the chain for the Merchant by appending a terminal
            KB-SD-JWT
            (``<Bank_SD-JWT>~[d]~~<SA_KB-SD-JWT+KB>[d]~~<CP_KB-SD-JWT>[d]~``).

    The Merchant verifier walks the chain from the Bank root, checking
    each hop's ``cnf`` delegation and ``sd_hash`` binding, and enforces
    ``aud``/``nonce`` on the final CP -> Merchant hop.
    """
    bank_key = _mk_signing_jwk('bank-1')
    sa_key = _mk_signing_jwk('sa-1')
    cp_key = _mk_signing_jwk('cp-1')
    bank_pub = JWK.from_json(bank_key.export_public())
    sa_pub = JWK.from_json(sa_key.export_public())
    cp_pub = JWK.from_json(cp_key.export_public())

    # Step 1 — Bank issues open mandate bound to SA's key.
    bank_segment = sd_jwt.create(
        payload=OpenPaymentMandate(
            constraints=[],
            cnf=make_cnf(sa_pub),
            payment_amount=Amount(amount=2500, currency='USD'),
            payee=Merchant(id='m-1', name='Shop'),
        ),
        issuer_key=bank_key,
        sd=DisclosureMetadata(sd_keys=['amount', 'payee']),
    ).sd_jwt_issuance
    assert bank_segment.endswith('~'), "Bank SD-JWT must end with '~'"

    # Step 2 — SA delegates to CP. CP-challenge provides (aud_cp, nonce_cp).
    sa_segment = kb_sd_jwt.create(
        prev_token=_parse(bank_segment),
        holder_key=sa_key,
        payload=OpenPaymentMandate(constraints=[], cnf=make_cnf(cp_pub)),
        aud='cp-agent',
        nonce='cp-nonce-123',
    ).sd_jwt_issuance

    chain_step2 = f'{bank_segment[:-1]}~~{sa_segment}'
    assert chain_step2.count('~~') == 1

    # Step 3 — CP closes for the Merchant.
    closed_payload = PaymentMandate(
        transaction_id='tx_abc',
        payee=Merchant(id='m-1', name='Shop'),
        payment_amount=Amount(amount=2500, currency='USD'),
        payment_instrument=PaymentInstrument(id='pi-1', type='credit'),
    )
    cp_segment = kb_sd_jwt.create(
        prev_token=_parse(sa_segment),
        holder_key=cp_key,
        payload=closed_payload,
        aud='merchant',
        nonce='merchant-nonce-456',
    ).sd_jwt_issuance

    sa_segment_stripped = (
        sa_segment[:-1] if sa_segment.endswith('~') else sa_segment
    )
    chain_step3 = f'{bank_segment[:-1]}~~{sa_segment_stripped}~~{cp_segment}'
    assert chain_step3.count('~~') == 2

    # Step 4 — Merchant verifies the full chain.
    payloads = MandateClient().verify(
        token=chain_step3,
        key_or_provider=lambda _token: bank_pub,
        expected_aud='merchant',
        expected_nonce='merchant-nonce-456',
    )
    assert len(payloads) == 3
    assert payloads[0]['vct'] == 'mandate.payment.open.1'  # Bank's open mandate
    assert 'cnf' in payloads[1]  # SA delegated to CP
    assert payloads[2]['transaction_id'] == 'tx_abc'  # CP's closed mandate
    leaf_jwt = MandateClient().get_closed_mandate_jwt(chain_step3)
    assert leaf_jwt == cp_segment.split('~', 1)[0]
