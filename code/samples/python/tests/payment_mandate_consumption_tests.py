"""Credential-provider integration tests for consume-once mandates."""

import json

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from roles.credentials_provider_mcp import server


class _VerifiedChain:
    @staticmethod
    def verify(**_expected_bindings):
        return []


class _PaymentMandateChain:
    @staticmethod
    def parse(_payloads):
        return _VerifiedChain()


class _MandateClient:
    @staticmethod
    def verify(**_verification_inputs):
        return ['verified-payload']

    @staticmethod
    def get_closed_mandate_jwt(_payment_mandate_chain):
        return 'closed-mandate-jwt'


def _agent_provider_public_key():
    return object()


def _configure_verified_mandate(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        server, '_load_persisted_mandate', lambda _filename: 'mandate-chain'
    )
    monkeypatch.setattr(
        server, '_get_agent_provider_public_key', _agent_provider_public_key
    )
    monkeypatch.setattr(server, 'MandateClient', _MandateClient)
    monkeypatch.setattr(server, 'PaymentMandateChain', _PaymentMandateChain)
    monkeypatch.setattr(
        server, 'compute_sha256_b64url', lambda _value: 'closed-mandate-hash'
    )
    monkeypatch.setattr(server, '_TOKEN_STORE_PATH', tmp_path / 'tokens.json')
    monkeypatch.setattr(
        server,
        '_CONSUMED_MANDATES_PATH',
        tmp_path / 'consumed-mandates.sqlite3',
    )


def _issue_payment_credential():
    return server.issue_payment_credential(
        payment_mandate_chain_id='pay_123',
        open_checkout_hash='open-checkout-hash',
        checkout_jwt_hash='checkout-jwt-hash',
        payment_nonce='payment-nonce',
    )


def _issue_payment_credential_for_worker(_worker_index):
    return _issue_payment_credential()


def test_credential_provider_refuses_sequential_replay(monkeypatch, tmp_path):
    _configure_verified_mandate(monkeypatch, tmp_path)

    first = _issue_payment_credential()
    replay = _issue_payment_credential()

    assert 'payment_token' in first
    assert replay['error'] == 'mandate_already_used'


def test_credential_provider_refuses_reference_from_legacy_store(
    monkeypatch, tmp_path
):
    _configure_verified_mandate(monkeypatch, tmp_path)
    server._TOKEN_STORE_PATH.write_text(
        json.dumps({'closed-mandate-hash': {'token': 'legacy-token'}}),
        encoding='utf-8',
    )

    replay = _issue_payment_credential()

    assert replay['error'] == 'mandate_already_used'
    assert not server._CONSUMED_MANDATES_PATH.exists()


def test_credential_provider_refuses_concurrent_replay(monkeypatch, tmp_path):
    _configure_verified_mandate(monkeypatch, tmp_path)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(_issue_payment_credential_for_worker, range(8))
        )

    assert sum('payment_token' in result for result in results) == 1
    assert (
        sum(result.get('error') == 'mandate_already_used' for result in results)
        == 7
    )


def test_credential_provider_fails_closed_on_corrupt_replay_state(
    monkeypatch, tmp_path
):
    _configure_verified_mandate(monkeypatch, tmp_path)
    server._CONSUMED_MANDATES_PATH.write_bytes(b'not a sqlite database')

    result = _issue_payment_credential()

    assert result['error'] == 'replay_state_unavailable'
    assert 'payment_token' not in result


def test_credential_provider_fails_closed_on_unreadable_replay_state(
    monkeypatch, tmp_path
):
    _configure_verified_mandate(monkeypatch, tmp_path)
    server._CONSUMED_MANDATES_PATH.mkdir()

    result = _issue_payment_credential()

    assert result['error'] == 'replay_state_unavailable'
    assert 'payment_token' not in result
