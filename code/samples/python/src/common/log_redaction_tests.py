"""Sample logging must not copy payment artifacts into plaintext logs."""

import importlib
import logging

from io import StringIO
from types import SimpleNamespace

import httpx
import pytest

from fastmcp.server.middleware.logging import LoggingMiddleware

from common import server


@pytest.mark.parametrize('module_name', [
    'roles.credentials_provider_mcp.server',
    'roles.merchant_agent_mcp.server',
    'roles.merchant_payment_processor_mcp.server',
    'roles.x402_credentials_provider_mcp.server',
    'roles.x402_psp_mcp.server',
])
def test_mcp_logging_middleware_does_not_serialize_payloads(module_name):
  module = importlib.import_module(module_name)
  middleware = next(item for item in module.mcp.middleware if isinstance(item, LoggingMiddleware))
  assert not middleware.include_payloads
  assert not middleware.include_payload_length
  assert not middleware.estimate_payload_tokens


@pytest.mark.asyncio
async def test_a2a_http_middleware_does_not_log_body_or_change_response():
  secret = 'SENSITIVE_PAYMENT_TOKEN_123'
  output = StringIO()
  logger = logging.getLogger('ap2-test-http-redaction')
  logger.setLevel(logging.INFO)
  handler = logging.StreamHandler(output)
  logger.addHandler(handler)
  try:
    middleware = server._LoggingMiddleware(app=lambda *_: None, logger=logger)
    request = SimpleNamespace(
        method='POST',
        url=SimpleNamespace(path='/rpc', query=f'payment_token={secret}'),
        headers={'content-length': '42', server.A2A_EXTENSIONS_HEADER: secret},
        json=lambda: (_ for _ in ()).throw(AssertionError('must not read body')),
    )
    response = SimpleNamespace(status_code=200, body_iterator=iter([secret.encode()]))

    async def next_handler(_request):
      return response

    assert await middleware.dispatch(request, next_handler) is response
  finally:
    logger.removeHandler(handler)
  assert secret not in output.getvalue()
  assert 'Response status: 200' in output.getvalue()


@pytest.mark.asyncio
async def test_merchant_payment_post_does_not_log_token(monkeypatch):
  merchant = importlib.import_module('roles.merchant_agent_mcp.server')
  secret = 'SENSITIVE_PAYMENT_TOKEN_123'
  output = StringIO()
  handler = logging.StreamHandler(output)
  merchant._logger.addHandler(handler)

  class FakeClient:
    async def __aenter__(self): return self
    async def __aexit__(self, *_): pass
    async def post(self, url, *, headers, json):
      assert json['payment_token'] == secret
      return httpx.Response(200, json={'status': 'ok'}, request=httpx.Request('POST', url))

  monkeypatch.setattr(merchant.httpx, 'AsyncClient', lambda **_: FakeClient())
  try:
    result = await merchant._initiate_payment_with_payment_processor(secret, 'hash-a', 'hash-b')
  finally:
    merchant._logger.removeHandler(handler)
  assert result == {'status': 'ok'}
  assert secret not in output.getvalue()
  assert 'has_payment_token=True' in output.getvalue()


@pytest.mark.asyncio
async def test_merchant_payment_error_does_not_log_response_body(monkeypatch):
  merchant = importlib.import_module('roles.merchant_agent_mcp.server')
  secret = 'SENSITIVE_PAYMENT_TOKEN_123'
  output = StringIO()
  handler = logging.StreamHandler(output)
  merchant._logger.addHandler(handler)

  class FakeClient:
    async def __aenter__(self): return self
    async def __aexit__(self, *_): pass
    async def post(self, url, *, headers, json):
      return httpx.Response(
          403, text=secret, request=httpx.Request('POST', url)
      )

  monkeypatch.setattr(merchant.httpx, 'AsyncClient', lambda **_: FakeClient())
  try:
    result = await merchant._initiate_payment_with_payment_processor(secret, 'hash-a', 'hash-b')
  finally:
    merchant._logger.removeHandler(handler)
  assert result['error'].endswith('403')
  assert secret not in output.getvalue()
  assert secret not in str(result)
