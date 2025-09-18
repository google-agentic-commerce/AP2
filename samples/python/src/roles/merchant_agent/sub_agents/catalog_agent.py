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

"""A sub-agent that offers items from its 'catalog'.

This agent fabricates catalog content based on the user's request.
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any

from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import DataPart
from a2a.types import Part
from a2a.types import Task
from a2a.types import TextPart
from google import genai
from pydantic import ValidationError

from .. import storage
from ap2.types.mandate import CART_MANDATE_DATA_KEY
from ap2.types.mandate import CartContents
from ap2.types.mandate import CartMandate
from ap2.types.mandate import INTENT_MANDATE_DATA_KEY
from ap2.types.mandate import IntentMandate
from ap2.types.payment_request import PaymentDetailsInit
from ap2.types.payment_request import PaymentItem
from ap2.types.payment_request import PaymentMethodData
from ap2.types.payment_request import PaymentOptions
from ap2.types.payment_request import PaymentRequest
from common import message_utils
from common.system_utils import DEBUG_MODE_INSTRUCTIONS


async def find_items_workflow(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Finds products that match the user's IntentMandate."""
  llm_client = genai.Client()

  intent_mandate = message_utils.parse_canonical_object(
      INTENT_MANDATE_DATA_KEY, data_parts, IntentMandate
  )
  intent = intent_mandate.natural_language_description
  prompt = f"""
        Based on the user's request for '{intent}', your task is to generate 3
        complete, unique and realistic PaymentItem JSON objects.

        You MUST exclude all branding from the PaymentItem `label` field.

    %s
        """ % DEBUG_MODE_INSTRUCTIONS

  llm_response = llm_client.models.generate_content(
      model="gemini-2.5-flash",
      contents=prompt,
      config={
          "response_mime_type": "application/json",
          "response_schema": list[PaymentItem],
      }
  )
  try:
    items: list[PaymentItem] = llm_response.parsed

    current_time = datetime.now(timezone.utc)
    item_count = 0
    for item in items:
      item_count += 1
      await _create_and_add_cart_mandate_artifact(
          item, item_count, current_time, updater
      )
    risk_data = _collect_risk_data(updater)
    updater.add_artifact([
        Part(root=DataPart(data={"risk_data": risk_data})),
    ])
    await updater.complete()
  except ValidationError as e:
    error_message = updater.new_agent_message(
        parts=[Part(root=TextPart(text=f"Invalid CartMandate list: {e}"))]
    )
    await updater.failed(message=error_message)
    return


async def _create_and_add_cart_mandate_artifact(
    item: PaymentItem,
    item_count: int,
    current_time: datetime,
    updater: TaskUpdater,
) -> None:
  """Creates a CartMandate and adds it as an artifact."""
  payment_request = PaymentRequest(
      method_data=[
          PaymentMethodData(
              supported_methods="CARD",
              data={
                  "network": ["mastercard", "paypal", "amex"],
              },
          )
      ],
      details=PaymentDetailsInit(
          id=f"order_{item_count}",
          display_items=[item],
          total=PaymentItem(
              label="Total",
              amount=item.amount,
          ),
      ),
      options=PaymentOptions(request_shipping=True),
  )

  cart_contents = CartContents(
      id=f"cart_{item_count}",
      user_cart_confirmation_required=True,
      payment_request=payment_request,
      cart_expiry=(current_time + timedelta(minutes=30)).isoformat(),
      merchant_name="Generic Merchant",
  )

  cart_mandate = CartMandate(contents=cart_contents)

  storage.set_cart_mandate(cart_mandate.contents.id, cart_mandate)
  await updater.add_artifact([
      Part(
          root=DataPart(data={CART_MANDATE_DATA_KEY: cart_mandate.model_dump()})
      )
  ])


def _collect_risk_data(updater: TaskUpdater) -> dict:
  """Creates a risk_data in the tool_context."""
  # This is a fake risk data for demonstration purposes.
  risk_data = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...fake_risk_data"
  storage.set_risk_data(updater.context_id, risk_data)
  return risk_data
