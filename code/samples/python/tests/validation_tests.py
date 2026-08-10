# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the cart-to-payment mandate binding validation helpers."""

import copy

import pytest


pytest.importorskip('rfc8785', reason='samples dependency rfc8785 not installed')

from ap2.models.mandate import (
  CartContents,
  CartMandate,
  PaymentMandate,
  PaymentMandateContents,
)
from ap2.models.payment_request import (
  PaymentCurrencyAmount,
  PaymentDetailsInit,
  PaymentItem,
  PaymentMethodData,
  PaymentRequest,
)
from common.validation import (
  compute_cart_mandate_hash,
  validate_cart_mandate_hash,
)


def _payment_item(label: str = 'Total', value: float = 120.0) -> PaymentItem:
  return PaymentItem(
      label=label,
      amount=PaymentCurrencyAmount(currency='USD', value=value),
  )


def _cart_mandate_data(include_authorization: bool = True) -> dict:
  """Builds a CartMandate wire object as a merchant would transmit it."""
  cart_mandate = CartMandate(
      contents=CartContents(
          id='cart_001',
          user_cart_confirmation_required=True,
          payment_request=PaymentRequest(
              method_data=[PaymentMethodData(supported_methods='CARD')],
              details=PaymentDetailsInit(
                  id='order_001',
                  display_items=[_payment_item('High top shoes')],
                  total=_payment_item(),
              ),
          ),
          cart_expiry='2027-01-01T00:00:00Z',
          merchant_name='Example Merchant',
      ),
      merchant_authorization='hdr.payload.sig' if include_authorization
      else None,
  )
  return cart_mandate.model_dump(mode='json', exclude_none=True)


def _payment_mandate(cart_mandate_hash: str | None) -> PaymentMandate:
  return PaymentMandate(
      payment_mandate_contents=PaymentMandateContents(
          payment_mandate_id='pm_001',
          payment_details_id='order_001',
          payment_details_total=_payment_item(),
          payment_response={
              'request_id': 'order_001',
              'method_name': 'CARD',
          },
          merchant_agent='merchant_agent_001',
          timestamp='2026-08-04T00:00:00+00:00',
          cart_mandate_id='cart_001',
          cart_mandate_hash=cart_mandate_hash,
      ),
  )


def test_valid_binding_passes():
  """A hash over the raw wire object verifies cleanly, extensions included."""
  cart_data = _cart_mandate_data()
  # Extension data outside the CartMandate model schema is part of the
  # transmitted object and must be covered by the hash.
  cart_data['x_merchant_extension'] = {'loyalty_tier': 'gold'}
  payment_mandate = _payment_mandate(compute_cart_mandate_hash(cart_data))

  validate_cart_mandate_hash(payment_mandate, cart_data)


def test_tampered_model_field_rejected():
  """Tampering with a schema field after hashing is detected."""
  cart_data = _cart_mandate_data()
  payment_mandate = _payment_mandate(compute_cart_mandate_hash(cart_data))

  tampered = copy.deepcopy(cart_data)
  tampered['contents']['payment_request']['details']['total']['amount'][
      'value'
  ] = 1.0

  with pytest.raises(ValueError, match='hash mismatch'):
    validate_cart_mandate_hash(payment_mandate, tampered)


def test_tampered_extension_field_rejected():
  """Tampering outside the model schema is detected by the raw-object hash.

  A hash over a re-parsed Pydantic model would miss this: unknown fields are
  silently dropped by model_validate, so the re-serialized form is identical
  before and after tampering.
  """
  cart_data = _cart_mandate_data()
  cart_data['x_merchant_extension'] = {'loyalty_tier': 'gold'}
  payment_mandate = _payment_mandate(compute_cart_mandate_hash(cart_data))

  tampered = copy.deepcopy(cart_data)
  tampered['x_merchant_extension'] = {'loyalty_tier': 'none'}

  with pytest.raises(ValueError, match='hash mismatch'):
    validate_cart_mandate_hash(payment_mandate, tampered)


def test_injected_unknown_field_rejected():
  """Injecting a brand new unknown field after hashing is detected."""
  cart_data = _cart_mandate_data()
  payment_mandate = _payment_mandate(compute_cart_mandate_hash(cart_data))

  tampered = copy.deepcopy(cart_data)
  tampered['x_injected'] = 'attacker-data'

  with pytest.raises(ValueError, match='hash mismatch'):
    validate_cart_mandate_hash(payment_mandate, tampered)


def test_absent_hash_rejected_by_default():
  """A PaymentMandate without cart_mandate_hash is rejected by default."""
  cart_data = _cart_mandate_data()
  payment_mandate = _payment_mandate(None)

  with pytest.raises(ValueError, match='cart_mandate_hash absent'):
    validate_cart_mandate_hash(payment_mandate, cart_data)


def test_absent_hash_skipped_with_explicit_opt_out():
  """The legacy opt-out must be explicit and skips only the absent case."""
  cart_data = _cart_mandate_data()
  payment_mandate = _payment_mandate(None)

  validate_cart_mandate_hash(
      payment_mandate, cart_data, allow_unbound_cart=True
  )


def test_opt_out_does_not_weaken_present_hash():
  """allow_unbound_cart never bypasses verification of a present hash."""
  cart_data = _cart_mandate_data()
  payment_mandate = _payment_mandate(compute_cart_mandate_hash(cart_data))

  tampered = copy.deepcopy(cart_data)
  tampered['contents']['merchant_name'] = 'Evil Merchant'

  with pytest.raises(ValueError, match='hash mismatch'):
    validate_cart_mandate_hash(
        payment_mandate, tampered, allow_unbound_cart=True
    )


def test_explicit_null_differs_from_absent_field():
  """An explicit null is not the same wire object as an absent field."""
  cart_data = _cart_mandate_data(include_authorization=False)
  assert 'merchant_authorization' not in cart_data
  payment_mandate = _payment_mandate(compute_cart_mandate_hash(cart_data))

  with_null = copy.deepcopy(cart_data)
  with_null['merchant_authorization'] = None

  assert compute_cart_mandate_hash(with_null) != compute_cart_mandate_hash(
      cart_data
  )
  with pytest.raises(ValueError, match='hash mismatch'):
    validate_cart_mandate_hash(payment_mandate, with_null)
