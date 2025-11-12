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

"""Objects for the Agent Payments Protocol Payment Receipt."""

from datetime import datetime
from datetime import timezone
from typing import Any, Dict, Optional

from ap2.types.payment_request import PaymentCurrencyAmount
from pydantic import BaseModel
from pydantic import Field


PAYMENT_RECEIPT_DATA_KEY = "ap2.PaymentReceipt"


class Success(BaseModel):
  """Details about a successful payment."""

  merchant_confirmation_id: str = Field(
      ...,
      description=(
          "A unique identifier for the transaction confirmation at the"
          " merchant."
      ),
  )
  psp_confirmation_id: Optional[str] = Field(
      None,
      description=(
          "A unique identifier for the transaction confirmation at the PSP."
      ),
  )
  network_confirmation_id: Optional[str] = Field(
      None,
      description=(
          "A unique identifier for the transaction confirmation at the network."
      ),
  )


class Error(BaseModel):
  """Details about an errored payment."""

  error_message: str = Field(
      ...,
      description=(
          "A human-readable message explaining the error and how to proceed."
      ),
  )


class Failure(BaseModel):
  """Details about a failed payment."""

  failure_message: str = Field(
      ...,
      description=(
          "A human-readable message explaining the failure and how to proceed."
      ),
  )


class PaymentReceipt(BaseModel):
  """Supplies information about the final state of a payment."""

  payment_mandate_id: str = Field(
      ..., description="A unique identifier for the processed payment mandate."
  )
  timestamp: str = Field(
      description=(
          "The date and time the payment receipt was created, in ISO 8601"
          "format."
      ),
      default_factory=lambda: datetime.now(timezone.utc).isoformat(),
  )
  payment_id: str = Field(
      ..., description="A unique identifier for the payment."
  )
  amount: PaymentCurrencyAmount = Field(
      ..., description="The monetary amount of the payment."
  )
  payment_status: Success | Error | Failure = Field(
      ..., description="The status of the payment."
  )
  payment_method_details: Optional[Dict[str, Any]] = Field(
      None,
      description="The payment method used for the transaction.",
  )
