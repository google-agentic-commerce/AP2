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

Returns Cart objects for browsing. The checkout JWT is created later
when the user selects a cart (via the ``create_checkout`` tool).
"""

from typing import Any

from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import DataPart, Part, Task, TextPart
from ap2.models.cart import CART_DATA_KEY, Cart
from ap2.models.payment_request import PaymentItem
from common import message_utils
from common.system_utils import DEBUG_MODE_INSTRUCTIONS
from google import genai
from pydantic import ValidationError

from .. import storage


async def find_items_workflow(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Find products.

  Use this tool only when the request says 'find products' or contains
  'catalog_search'. Searches the catalog and returns Cart objects.

  Args:
    data_parts: The data parts from the message.
    updater: The task updater to report status.
    current_task: The current task object.
  """
  llm_client = genai.Client()

  catalog_search = message_utils.find_data_part("catalog_search", data_parts)
  if not catalog_search:
    error_message = updater.new_agent_message(
        parts=[Part(root=TextPart(text="Missing catalog_search."))]
    )
    await updater.failed(message=error_message)
    return

  prompt = f"""
        Based on the user's request for '{catalog_search}', your task is to
        generate 3 complete, unique and realistic PaymentItem JSON objects.

        You MUST exclude all branding from the PaymentItem `label` field.

    %s
        """ % DEBUG_MODE_INSTRUCTIONS

  llm_response = llm_client.models.generate_content(
      model="gemini-3.1-flash-lite-preview",
      contents=prompt,
      config={
          "response_mime_type": "application/json",
          "response_schema": list[PaymentItem],
      },
  )
  try:
    items: list[PaymentItem] = llm_response.parsed

    for i, item in enumerate(items):
      cart = Cart(
          cart_id=f"cart_{i + 1}",
          item_label=item.label,
          amount=item.amount.value,
          currency=item.amount.currency,
      )
      storage.set_cart_data(cart.cart_id, cart.model_dump())
      await updater.add_artifact(
          [Part(root=DataPart(data={CART_DATA_KEY: cart.model_dump()}))]
      )

    risk_data = _collect_risk_data(updater)
    await updater.add_artifact([
        Part(root=DataPart(data={"risk_data": risk_data})),
    ])
    await updater.complete()
  except ValidationError as e:
    error_message = updater.new_agent_message(
        parts=[Part(root=TextPart(text=f"Invalid product list: {e}"))]
    )
    await updater.failed(message=error_message)
    return


def _collect_risk_data(updater: TaskUpdater) -> str:
  risk_data = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...fake_risk_data"
  storage.set_risk_data(updater.context_id, risk_data)
  return risk_data
