"""Public present() can extend and verify a two-hop delegation chain."""

import pytest

from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate
from ap2.sdk.mandate import MandateClient
from ap2.sdk.sdjwt import compute_sd_hash, parse_token
from ap2.tests.conftest import make_cnf, sample_payment_mandate
from jwcrypto.jwk import JWK


def _chain(issuer_key, first_key, second_key, *, redact=False):
    client = MandateClient()
    root = client.create(
        payloads=[OpenPaymentMandate(constraints=[], cnf=make_cnf(first_key))],
        issuer_key=issuer_key,
    )
    hop1 = client.present(
        holder_key=first_key,
        mandate_token=root,
        payloads=[OpenPaymentMandate(constraints=[], cnf=make_cnf(second_key))],
        aud='agent-two',
        nonce='hop-one',
    )
    hop2 = client.present(
        holder_key=second_key,
        mandate_token=hop1,
        payloads=[sample_payment_mandate()],
        aud='merchant',
        nonce='hop-two',
        claims_to_disclose={} if redact else None,
    )
    return client, root, hop1, hop2


@pytest.mark.parametrize('redact', [False, True])
def test_present_extends_two_hops_and_verifies(
    issuer_key, issuer_public_key, redact
):
    first_key = JWK.generate(kty='EC', crv='P-256')
    second_key = JWK.generate(kty='EC', crv='P-256')
    client, root, hop1, hop2 = _chain(
        issuer_key, first_key, second_key, redact=redact
    )
    segments = hop2.split('~~')
    assert len(segments) == 3
    assert segments[0] == root.removesuffix('~')
    assert segments[1].split('~', 1)[0] == hop1.split('~~')[1].split('~', 1)[0]
    assert segments[-1].endswith('~')
    payloads = client.verify(
        token=hop2,
        key_or_provider=lambda _token: issuer_public_key,
        expected_aud='merchant',
        expected_nonce='hop-two',
    )
    assert len(payloads) == 3
    assert payloads[-1]['transaction_id'] == 'tx_1'
    # Binding is to the preceding individual hop as sent, not the whole chain.
    assert parse_token(segments[-1]).payload['sd_hash'] == compute_sd_hash(
        parse_token(segments[1] + '~')
    )


@pytest.mark.parametrize('redact', [False, True])
def test_present_rejects_tampered_prior_hop(
    issuer_key, issuer_public_key, redact
):
    first_key = JWK.generate(kty='EC', crv='P-256')
    second_key = JWK.generate(kty='EC', crv='P-256')
    client, _root, _hop1, chain = _chain(
        issuer_key, first_key, second_key, redact=redact
    )
    root, prior, final = chain.split('~~')
    # Mutate an actual disclosed claim while leaving its signed digest intact.
    # Its signature cannot authenticate the substituted disclosure.
    parts = prior.split('~')
    assert len(parts) >= 2 and parts[1]
    disclosure = parts[1]
    parts[1] = ('x' if disclosure[0] != 'x' else 'y') + disclosure[1:]
    changed_jwt = '~'.join(parts)
    with pytest.raises(Exception):
        client.verify(
            token='~~'.join((root, changed_jwt, final)),
            key_or_provider=lambda _token: issuer_public_key,
            expected_aud='merchant',
            expected_nonce='hop-two',
        )
