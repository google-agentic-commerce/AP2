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

import logging
import os

import httpx
from ap2.types.mandate import PaymentMandate


async def create_mock_bank_transaction(
    payment_mandate: PaymentMandate,
) -> None:
  """Creates a transaction at the mock bank for UPI_COLLECT payments.

  Args:
    payment_mandate: The payment mandate containing transaction details.
  """
  try:
    payment_details_id = payment_mandate.payment_mandate_contents.payment_details_id
    amount = payment_mandate.payment_mandate_contents.payment_details_total.amount.value
    currency = payment_mandate.payment_mandate_contents.payment_details_total.amount.currency

    payer_name = payment_mandate.payment_mandate_contents.payment_response.payer_name or ""
    first_name, last_name = _split_name(payer_name)

    payload = {
        "transaction_data": {
            "txn_id": payment_details_id,
            "amount": amount,
            "currency": currency,
            "description": "UPI Collect Payment"
        },
        "payment_data": {
            "UPI_COLLECT": {}
        }
    }

    if first_name and last_name:
      payload["customer_data"] = {
          "first_name": first_name,
          "last_name": last_name
      }

    mock_bank_url = os.environ.get("MOCK_BANK_URL", "http://127.0.0.1:8004")
    async with httpx.AsyncClient() as client:
      response = await client.post(
          f"{mock_bank_url}/payments",
          json=payload,
          timeout=10.0
      )
      response.raise_for_status()
      result = response.json()

      if result.get("success"):
        logging.info(
            "Successfully created transaction at mock bank: %s",
            payment_details_id
        )
      else:
        logging.error(
            "Failed to create transaction at mock bank: %s",
            result.get("error", "Unknown error")
        )
  except Exception as e:
    logging.error(
        "Error creating transaction at mock bank: %s",
        str(e)
    )

def _split_name(full_name: str) -> tuple[str, str]:
  """Splits a full name into first and last name.

  Args:
    full_name: The full name to split.

  Returns:
    A tuple of (first_name, last_name).
  """
  if not full_name:
    return "", ""

  parts = full_name.strip().split(None, 1)
  if len(parts) == 1:
    return parts[0], ""
  else:
    return parts[0], parts[1]
