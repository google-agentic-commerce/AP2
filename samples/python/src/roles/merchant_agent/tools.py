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

"""Tools used by the merchant agent.

Each agent uses individual tools to handle distinct tasks throughout the
shopping and purchasing process.
"""

import base64
import json
import logging

from pydantic import ValidationError
from typing import Any

from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import DataPart
from a2a.types import Part
from a2a.types import Task
from a2a.types import TextPart

from . import storage
from ap2.types.contact_picker import ContactAddress
from ap2.types.mandate import CART_MANDATE_DATA_KEY
from ap2.types.mandate import PAYMENT_MANDATE_DATA_KEY
from ap2.types.mandate import PaymentMandate
from ap2.types.payment_request import PaymentCurrencyAmount
from ap2.types.payment_request import PaymentItem
from common import message_utils
from common.a2a_extension_utils import EXTENSION_URI
from common.a2a_message_builder import A2aMessageBuilder
from common.payment_remote_a2a_client import PaymentRemoteA2aClient

# A map of payment method types to their corresponding processor agent URLs.
# This is the set of linked Merchant Payment Processor Agents this Merchant
# is integrated with.
_PAYMENT_PROCESSORS_BY_PAYMENT_METHOD_TYPE = {
    "CARD": "http://localhost:8003/a2a/merchant_payment_processor_agent",
}

# A placeholder for a JSON Web Token (JWT) used for merchant authorization.
_FAKE_JWT = "eyJhbGciOiJSUzI1NiIsImtpZIwMjQwOTA..."


async def update_cart(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
    debug_mode: bool = False,
) -> None:
  """Updates an existing cart after a shipping address is provided.

  Args:
    data_parts: A list of data part contents from the request.
    updater: The TaskUpdater instance to add artifacts and complete the task.
    current_task: The current task -- not used in this function.
    debug_mode: Whether the agent is in debug mode.
  """
  cart_id = message_utils.find_data_part("cart_id", data_parts)
  if not cart_id:
    await _fail_task(updater, "Missing cart_id.")
    return

  shipping_address = message_utils.find_data_part(
      "shipping_address", data_parts
  )
  if not shipping_address:
    await _fail_task(updater, "Missing shipping_address.")
    return

  cart_mandate = storage.get_cart_mandate(cart_id)
  if not cart_mandate:
    await _fail_task(updater, f"CartMandate not found for cart_id: {cart_id}")
    return

  risk_data = storage.get_risk_data(updater.context_id)
  if not risk_data:
    await _fail_task(
        updater, f"Missing risk_data for context_id: {updater.context_id}"
    )
    return

  # Update the CartMandate with new shipping and tax cost.
  try:
    # Add the shipping address to the CartMandate:
    cart_mandate.contents.payment_request.shipping_address = (
        ContactAddress.model_validate(shipping_address)
    )

    # Add new shipping and tax costs to the PaymentRequest:
    tax_and_shipping_costs = [
        PaymentItem(
            label="Shipping",
            amount=PaymentCurrencyAmount(currency="USD", value=2.00),
        ),
        PaymentItem(
            label="Tax",
            amount=PaymentCurrencyAmount(currency="USD", value=1.50),
        ),
    ]

    payment_request = cart_mandate.contents.payment_request

    if payment_request.details.display_items is None:
      payment_request.details.display_items = tax_and_shipping_costs
    else:
      payment_request.details.display_items.extend(tax_and_shipping_costs)

    # Recompute the total amount of the PaymentRequest:
    payment_request.details.total.amount.value = sum(
        item.amount.value for item in payment_request.details.display_items
    )

    # A base64url-encoded JSON Web Token (JWT) that digitally signs the cart
    # contents by the merchant's private key.
    cart_mandate.merchant_authorization = _FAKE_JWT

    await updater.add_artifact([
        Part(
            root=DataPart(
                data={CART_MANDATE_DATA_KEY: cart_mandate.model_dump()}
            )
        ),
        Part(root=DataPart(data={"risk_data": risk_data})),
    ])
    await updater.complete()

  except ValidationError as e:
    await _fail_task(updater, f"Invalid CartMandate after update: {e}")


async def initiate_payment(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
    debug_mode: bool = False,
) -> None:
  """Initiates a payment for a given payment mandate. Use to make a payment.

  Args:
    data_parts: The data parts from the request, expected to contain a
      PaymentMandate and optionally an challenge response.
    updater: The TaskUpdater instance for updating the task state.
    current_task: The current task, used to find the processor's task ID.
    debug_mode: Whether the agent is in debug mode.
  """
  payment_mandate = message_utils.parse_canonical_object(
      PAYMENT_MANDATE_DATA_KEY, data_parts, PaymentMandate
  )
  if not payment_mandate:
    await _fail_task(updater, "Missing payment_mandate.")
    return

  risk_data = message_utils.find_data_part("risk_data", data_parts)
  if not risk_data:
    await _fail_task(updater, "Missing risk_data.")
    return

  payment_method_type = (
      payment_mandate.payment_mandate_contents.payment_response.method_name
  )
  processor_url = _PAYMENT_PROCESSORS_BY_PAYMENT_METHOD_TYPE.get(
      payment_method_type
  )

  if not processor_url:
    await _fail_task(
        updater, f"No payment processor found for method: {payment_method_type}"
    )
    return

  payment_processor_agent = PaymentRemoteA2aClient(
      name="payment_processor_agent",
      base_url=processor_url,
      required_extensions={
          EXTENSION_URI,
      },
  )

  message_builder = (
      A2aMessageBuilder()
      .set_context_id(updater.context_id)
      .add_text("initiate_payment")
      .add_data(PAYMENT_MANDATE_DATA_KEY, payment_mandate.model_dump())
      .add_data("risk_data", risk_data)
      .add_data("debug_mode", debug_mode)
  )

  challenge_response = (
      message_utils.find_data_part("challenge_response", data_parts) or ""
  )
  if challenge_response:
    message_builder.add_data("challenge_response", challenge_response)

  payment_processor_task_id = _get_payment_processor_task_id(current_task)
  if payment_processor_task_id:
    message_builder.set_task_id(payment_processor_task_id)

  task = await payment_processor_agent.send_a2a_message(message_builder.build())
  await updater.update_status(
      state=task.status.state,
      message=task.status.message,
  )


async def dpc_finish(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Receives and validates a DPC response to finalize payment.

  This tool receives the Digital Payment Credential (DPC) response, in the form
  of an OpenID4VP JSON, validates it, and simulates payment finalization.

  Args:
    data_parts: A list of data part contents from the request.
    updater: The TaskUpdater instance to add artifacts and complete the task.
    current_task: The current task, not used in this function.
  """
  dpc_response = message_utils.find_data_part("dpc_response", data_parts)
  if not dpc_response:
    await _fail_task(updater, "Missing dpc_response.")
    return

  logging.info("Received DPC response for finalization: %s", dpc_response)

  # --- Sample validation and payment finalization logic ---
  # TODO: Validate the nonce, and other merchant-specific attributes from the
  # DPC response.
  # TODO: Pass the DPC response to the payment processor agent for validation.

  # Simulate payment finalization.
  await updater.add_artifact([
      Part(root=DataPart(data={
          "payment_status": "SUCCESS",
          "transaction_id": "txn_1234567890",
      }))
  ])
  await updater.complete()


def _get_payment_processor_task_id(task: Task | None) -> str | None:
  """Returns the task ID of the payment processor task, if it exists.

  Identified by assuming the first message with a task ID that is not the
  merchant's task ID is a payment processor message.
  """
  if task is None:
    return None
  for message in task.history:
    if message.task_id != task.id:
      return message.task_id
  return None


async def _fail_task(updater: TaskUpdater, error_text: str) -> None:
  """A helper function to fail a task with a given error message."""
  error_message = updater.new_agent_message(
      parts=[Part(root=TextPart(text=error_text))]
  )
  await updater.failed(message=error_message)
