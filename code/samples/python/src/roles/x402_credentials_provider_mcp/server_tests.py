"""Regression tests for x402 credential provider amount handling (issue #299).

The credential provider must authorize the amount signed in the verified
payment mandate, never a hardcoded fallback. Before the fix, an AttributeError
on a missing instrument field caused the handler to silently authorize a fixed
1250 cents regardless of what the user actually mandated.
"""

import sys

from pathlib import Path

import pytest


# Make the samples 'src' root importable (roles.*, common.*).
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
  sys.path.insert(0, str(_SRC))

from roles.x402_credentials_provider_mcp import server  # noqa: E402


class _Amount:

  def __init__(self, amount):
    self.amount = amount


class _Mandate:

  def __init__(self, amount):
    self.payment_amount = _Amount(amount)


class _Chain:

  def __init__(self, amount):
    self.closed_mandate = _Mandate(amount)


def test_amount_uses_signed_value():
  assert server._verified_amount_cents(_Chain(4200)) == 4200


def test_amount_honors_any_signed_value():
  # The pre-fix code authorized a fixed 1250 regardless of the mandate.
  for value in (1, 999, 1249, 1251, 500000):
    assert server._verified_amount_cents(_Chain(value)) == value


def test_amount_missing_fails_closed():
  class _NoAmount:
    pass

  # A verified mandate without a payment amount must raise, so the caller can
  # fail closed rather than fabricate a value.
  with pytest.raises(AttributeError):
    server._verified_amount_cents(_NoAmount())


def test_amount_null_fails_closed():
  # payment_amount is present but its amount is null. The null slips past
  # attribute access, so without an explicit guard the function would return
  # None and later crash on None * 10000 instead of failing closed. It must
  # raise AttributeError so the caller returns verification_failed.
  with pytest.raises(AttributeError):
    server._verified_amount_cents(_Chain(None))


def test_handler_does_not_fabricate_amount():
  # Guard against reintroducing the hardcoded amount fallback in the handler.
  source = Path(server.__file__).read_text(encoding="utf-8")
  assert "amount_cents = 1250" not in source
