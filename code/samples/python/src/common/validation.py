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

"""Validation logic for the PaymentMandate cart-to-payment binding.

See the "Cart-to-Payment Mandate Binding" section of
docs/ap2/specification.md for the normative requirements implemented here.
"""

import hashlib
import logging

from typing import Any

import rfc8785

from ap2.models.mandate import PaymentMandate


def validate_payment_mandate_signature(payment_mandate: PaymentMandate) -> None:
  """Validates that a PaymentMandate carries a user_authorization field.

  Note: This is a placeholder - a production implementation must verify the
  cryptographic signature (e.g., sd-jwt-vc key-binding) embedded in
  user_authorization.  Use validate_cart_mandate_hash() to enforce the
  cart-to-payment binding before releasing credentials or initiating payment.

  Args:
    payment_mandate: The PaymentMandate to be validated.

  Raises:
    ValueError: If the PaymentMandate has no user_authorization.
  """
  # In a real implementation, full validation logic would reside here. For
  # demonstration purposes, we simply log that the authorization field is
  # populated.
  if payment_mandate.user_authorization is None:
    raise ValueError("User authorization not found in PaymentMandate.")

  logging.info("Valid PaymentMandate found.")


def compute_cart_mandate_hash(cart_mandate_data: dict[str, Any]) -> str:
  """Computes the binding hash of a CartMandate JSON object.

  The hash is hex(sha256(JCS(cart_mandate_data))), where JCS is the JSON
  Canonicalization Scheme defined in RFC 8785.

  The input MUST be the CartMandate JSON object exactly as transmitted on
  the wire, not a re-serialized data model. Parsing into a schema model
  silently drops unknown or extension fields and can collapse an explicit
  null with an absent field, so a hash over a re-serialized model would not
  cover the full received object. JCS removes whitespace, key-order, and
  number-formatting variation, so hashing the raw object is stable across
  language implementations.

  Args:
    cart_mandate_data: The CartMandate as a raw JSON object (parsed dict),
      exactly as sent or received.

  Returns:
    The lowercase hex SHA-256 digest of the JCS canonical form.
  """
  canonical_bytes = rfc8785.dumps(cart_mandate_data)
  return hashlib.sha256(canonical_bytes).hexdigest()


def validate_cart_mandate_hash(
    payment_mandate: PaymentMandate,
    cart_mandate_data: dict[str, Any],
    *,
    allow_unbound_cart: bool = False,
) -> None:
  """Verifies the cart-to-payment binding by recomputing the JCS hash.

  Recomputes hex(sha256(JCS(cart_mandate_data))) over the raw received
  CartMandate JSON object and compares it against
  PaymentMandateContents.cart_mandate_hash per the "Cart-to-Payment Mandate
  Binding" section of the AP2 specification.

  Verifiers MUST call this gate before releasing credentials or initiating
  payment; a mismatch MUST cause the transaction to be rejected.

  The binding is enforced by default. A PaymentMandate without
  cart_mandate_hash is rejected unless allow_unbound_cart is explicitly set
  to True, which restricts the exemption to a controlled legacy rollout of
  mandates created before the binding requirement existed.

  Args:
    payment_mandate: The PaymentMandate whose contents hold the expected
      hash.
    cart_mandate_data: The merchant-signed CartMandate as the raw JSON
      object received on the wire (for example the value returned by
      message_utils.find_data_part for CART_MANDATE_DATA_KEY), before any
      model parsing.
    allow_unbound_cart: If True, a missing cart_mandate_hash logs a warning
      and skips the check instead of rejecting. Defaults to False.

  Raises:
    ValueError: If cart_mandate_hash is absent while allow_unbound_cart is
      False, or if it does not match the recomputed digest.
  """
  expected = payment_mandate.payment_mandate_contents.cart_mandate_hash
  if expected is None:
    if allow_unbound_cart:
      logging.warning(
          "cart_mandate_hash absent from PaymentMandateContents and "
          "allow_unbound_cart is True - skipping binding check for a legacy "
          "mandate. Populate cart_mandate_hash to enforce strong binding."
      )
      return
    raise ValueError(
        "cart_mandate_hash absent from PaymentMandateContents. The "
        "cart-to-payment binding is mandatory: reject this mandate, or opt "
        "out explicitly with allow_unbound_cart=True for legacy mandates "
        "only."
    )

  actual = compute_cart_mandate_hash(cart_mandate_data)
  if expected != actual:
    raise ValueError(
        f"CartMandate hash mismatch: mandate carries {expected!r} but "
        f"recomputed {actual!r}. PaymentMandate does not match the "
        "merchant-authorized CartMandate."
    )

  logging.info(
      "CartMandate hash verified: PaymentMandate is bound to cart %s.",
      payment_mandate.payment_mandate_contents.cart_mandate_id,
  )
