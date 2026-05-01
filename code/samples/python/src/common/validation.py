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

"""Validation logic for PaymentMandate cart-to-payment binding (AP2 section 4.1.3.1)."""

import hashlib
import logging

import rfc8785

from ap2.models.mandate import CartMandate
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


def validate_cart_mandate_hash(
    payment_mandate: PaymentMandate,
    cart_mandate: CartMandate,
) -> None:
  """Verifies the cart-to-payment binding by recomputing the JCS hash.

  Recomputes sha256(RFC_8785(CartMandate)) and compares it against
  PaymentMandateContents.cart_mandate_hash per AP2 section 4.1.3.1.

  None values are excluded from the serialized dict so that optional fields
  omitted by Python match the behavior of Go's ``omitempty`` tag, giving a
  consistent canonical form across language implementations.

  Verifiers MUST call this gate before releasing credentials or initiating
  payment; a mismatch MUST cause the transaction to be rejected.

  If cart_mandate_hash is absent (mandate predates this field) a warning is
  logged and the check is skipped so that older implementations remain
  compatible during rollout.

  Args:
    payment_mandate: The PaymentMandate whose contents hold the expected hash.
    cart_mandate: The merchant-signed CartMandate to verify against.

  Raises:
    ValueError: If cart_mandate_hash is present but does not match the
      recomputed digest.
  """
  expected = payment_mandate.payment_mandate_contents.cart_mandate_hash
  if expected is None:
    logging.warning(
        "cart_mandate_hash absent from PaymentMandateContents - "
        "skipping binding check (mandate predates AP2 section 4.1.3.1 JCS "
        "requirement). Populate cart_mandate_hash to enforce strong binding."
    )
    return

  cart_dict = cart_mandate.model_dump(mode="json", exclude_none=True)
  canonical_bytes = rfc8785.dumps(cart_dict)
  actual = hashlib.sha256(canonical_bytes).hexdigest()

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
