"""Regression tests for the x402 PSP fail-closed fix (AP2 #309).

When the agent-provider public key cannot be loaded, ``settle_payment``
must fail closed and return ``agent_provider_key_missing`` instead of
silently skipping SD-JWT mandate verification. A second test proves that
verification still runs (and can fail) when the key IS present, so the
fix did not disable the check. A third test covers key files that parse as
JSON but are not a usable key (an invalid JWK object, which raises
``jwcrypto`` ``JWException``, and a non-object JSON value, which raises
``TypeError``) -- neither is a ``ValueError``/``JSONDecodeError``, and both
must fail closed rather than propagate.
"""

import json

import pytest

from jwcrypto.jwk import JWK
from roles.x402_psp_mcp import server
from roles.x402_psp_mcp.server import settle_payment


def _minimal_bundle():
    """Return the smallest bundle that reaches the key-loading guard."""
    return {
        'payment_mandate_chain': 'not-a-valid-sd-jwt',
        'eip_3009_payload': {'authorization': {'nonce': '0x00'}},
        'payment_nonce': 'nonce-abc',
    }


def test_settle_payment_fails_closed_when_key_missing(monkeypatch, tmp_path):
    """Missing agent-provider key must fail closed, not skip verification."""
    missing = tmp_path / 'missing.pub'
    monkeypatch.setattr(server, 'AGENT_PROVIDER_PUB_PATH', missing)

    result = settle_payment(payment_token=json.dumps(_minimal_bundle()))

    assert result['error'] == 'agent_provider_key_missing'


def test_settle_payment_still_verifies_when_key_present(monkeypatch, tmp_path):
    """With the key present, verification still runs and rejects bad input."""
    pub_path = tmp_path / 'present.pub'
    public_jwk = JWK.generate(kty='EC', crv='P-256').export_public()
    pub_path.write_text(public_jwk, encoding='utf-8')
    monkeypatch.setattr(server, 'AGENT_PROVIDER_PUB_PATH', pub_path)

    result = settle_payment(payment_token=json.dumps(_minimal_bundle()))

    assert result['error'] == 'mandate_verification_failed'


@pytest.mark.parametrize(
    'key_content',
    [
        '{}',  # valid JSON object, invalid JWK -> jwcrypto JWException
        '[]',  # non-object JSON -> TypeError
        'null',  # non-object JSON -> TypeError
        '123',  # non-object JSON -> TypeError
        '',  # empty file -> JSONDecodeError
    ],
)
def test_settle_payment_fails_closed_when_key_is_unusable(
    monkeypatch, tmp_path, key_content
):
    """A file that is not a usable key must fail closed, not raise.

    ``JWK.from_json`` raises different exception types for these inputs
    (``JWException`` for an invalid JWK object, ``TypeError`` for a
    non-object JSON value, ``JSONDecodeError`` for empty/garbage text).
    None is a ``ValueError``, so the key-load guard must catch broadly
    and return ``agent_provider_key_missing`` for every one of them.
    """
    bad_path = tmp_path / 'unusable.pub'
    bad_path.write_text(key_content, encoding='utf-8')
    monkeypatch.setattr(server, 'AGENT_PROVIDER_PUB_PATH', bad_path)

    result = settle_payment(payment_token=json.dumps(_minimal_bundle()))

    assert result['error'] == 'agent_provider_key_missing'
