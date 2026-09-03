"""Payment-processor integration tests for consume-once transactions."""

import asyncio
import json

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from roles.merchant_payment_processor_mcp import server


class _VerifiedChain:
    closed_mandate = object()

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


class _ReceiptContent:
    root = SimpleNamespace(payment_id='payment-123')

    @staticmethod
    def model_dump():
        return {}

    @staticmethod
    def model_dump_json():
        return '{}'


class _ReceiptClient:
    @staticmethod
    def create_payment_receipt(**_receipt_inputs):
        return _ReceiptContent()


def _agent_provider_public_key():
    return object()


def _configure_verified_payment(monkeypatch, tmp_path: Path):
    token_store_path = tmp_path / 'tokens.json'
    token_store_path.write_text(
        json.dumps(
            {
                'token-123': {
                    'used': True,
                    'payment_mandate_chain': 'mandate-chain',
                    'payment_nonce': 'payment-nonce',
                    'order_id': 'order-123',
                }
            }
        ),
        encoding='utf-8',
    )
    monkeypatch.setattr(server, '_TOKEN_STORE_PATH', token_store_path)
    monkeypatch.setattr(
        server,
        '_CONSUMED_TRANSACTIONS_PATH',
        tmp_path / 'consumed-transactions.sqlite3',
    )
    monkeypatch.setattr(
        server, '_get_agent_provider_public_key', _agent_provider_public_key
    )
    monkeypatch.setattr(server, 'MandateClient', _MandateClient)
    monkeypatch.setattr(server, 'PaymentMandateChain', _PaymentMandateChain)
    monkeypatch.setattr(server, 'ReceiptClient', _ReceiptClient)
    monkeypatch.setattr(server, 'create_jwt', lambda **_inputs: 'receipt-jwt')
    monkeypatch.setattr(
        server,
        '_get_merchant_payment_processor_signing_key',
        lambda **_inputs: SimpleNamespace(kid='payment-processor-key'),
    )

    async def _discard_receipt(_receipt):
        return None

    monkeypatch.setattr(
        server,
        '_send_payment_receipt_to_credentials_provider',
        _discard_receipt,
    )


def _initiate_payment():
    return asyncio.run(
        server.initiate_payment(
            payment_token='token-123',
            checkout_jwt_hash='checkout-jwt-hash',
            open_checkout_hash='open-checkout-hash',
        )
    )


def _initiate_payment_for_worker(_worker_index):
    return _initiate_payment()


def test_payment_processor_refuses_sequential_replay(monkeypatch, tmp_path):
    _configure_verified_payment(monkeypatch, tmp_path)

    first = _initiate_payment()
    replay = _initiate_payment()

    assert first['status'] == 'success'
    assert replay['error'] == 'mandate_already_used'


def test_payment_processor_refuses_concurrent_replay(monkeypatch, tmp_path):
    _configure_verified_payment(monkeypatch, tmp_path)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(_initiate_payment_for_worker, range(8)))

    assert sum(result.get('status') == 'success' for result in results) == 1
    assert (
        sum(result.get('error') == 'mandate_already_used' for result in results)
        == 7
    )


def test_payment_processor_fails_closed_on_corrupt_replay_state(
    monkeypatch, tmp_path
):
    _configure_verified_payment(monkeypatch, tmp_path)
    server._CONSUMED_TRANSACTIONS_PATH.write_bytes(b'not a sqlite database')

    result = _initiate_payment()

    assert result['error'] == 'replay_state_unavailable'
    assert 'payment_receipt' not in result


def test_payment_processor_fails_closed_on_unreadable_replay_state(
    monkeypatch, tmp_path
):
    _configure_verified_payment(monkeypatch, tmp_path)
    server._CONSUMED_TRANSACTIONS_PATH.mkdir()

    result = _initiate_payment()

    assert result['error'] == 'replay_state_unavailable'
    assert 'payment_receipt' not in result
