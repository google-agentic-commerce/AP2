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

"""Validation logic for PaymentMandate."""

import logging

from ap2.types.mandate import PaymentMandate


def validate_payment_mandate_signature(payment_mandate: PaymentMandate) -> None:
  """Validates the PaymentMandate signature.

  Args:
    payment_mandate: The PaymentMandate to be validated.

  Raises:
    ValueError: If the PaymentMandate signature is not valid.
  """
  # In a real implementation, full validation logic would reside here. For
  # demonstration purposes, we simply log that the authorization field is
  # populated.
  if payment_mandate.user_authorization is None:
    raise ValueError("User authorization not found in PaymentMandate.")

  logging.info("Valid PaymentMandate found.")
