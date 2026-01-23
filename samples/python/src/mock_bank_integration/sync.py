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

async def get_payment_status_from_mock_bank(payment_details_id: str) -> str:
  """Gets the payment status from the mock bank.

  Args:
    payment_details_id: The payment mandate ID (used as transaction ID).

  Returns:
    The status string: "PENDING", "SUCCESS", "FAILURE", or "UNKNOWN" on error.
  """
  try:
    mock_bank_url = os.environ.get("MOCK_BANK_URL", "http://127.0.0.1:8004")
    async with httpx.AsyncClient() as client:
      response = await client.get(
          f"{mock_bank_url}/payments",
          params={"id": payment_details_id},
          timeout=10.0
      )
      response.raise_for_status()
      result = response.json()

      if result.get("success"):
        status = result.get("status", "UNKNOWN")
        logging.info(
            "Retrieved status for transaction %s: %s",
            payment_details_id,
            status
        )
        return status
      else:
        logging.error(
            "Failed to get status from mock bank: %s",
            result.get("error", "Unknown error")
        )
        return "UNKNOWN"
  except Exception as e:
    logging.error(
        "Error getting status from mock bank for %s: %s",
        payment_details_id,
        str(e)
    )
    return "UNKNOWN"
