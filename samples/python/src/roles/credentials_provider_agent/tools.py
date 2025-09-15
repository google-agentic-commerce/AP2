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

"""Tools for the credentials provider agent.

Each agent uses individual tools to handle distinct tasks throughout the
shopping and purchasing process.
"""

from typing import Any

from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import DataPart
from a2a.types import Part
from a2a.types import Task

from . import account_manager
from ap2.types.contact_picker import CONTACT_ADDRESS_DATA_KEY
from ap2.types.mandate import PAYMENT_MANDATE_DATA_KEY
from ap2.types.mandate import PaymentMandate
from ap2.types.payment_request import PAYMENT_METHOD_DATA_DATA_KEY
from ap2.types.payment_request import PaymentMethodData
from common import message_utils


async def handle_get_shipping_address(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Handles a request to get the user's shipping address.

  Updates a task with the user's shipping address if found.

  Args:
    data_parts: DataPart contents. Should contain a single user_email.
    updater: The TaskUpdater instance for updating the task state.
    current_task: The current task if there is one.
  """
  user_email = message_utils.find_data_part("user_email", data_parts)
  if not user_email:
    raise ValueError("user_email is required for get_shipping_address")
  shipping_address = account_manager.get_account_shipping_address(user_email)
  await updater.add_artifact(
      [Part(root=DataPart(data={CONTACT_ADDRESS_DATA_KEY: shipping_address}))]
  )
  await updater.complete()


async def handle_search_payment_methods(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Returns the user's payment methods that match what the merchant accepts.

  The merchant's accepted payment methods are provided in the data_parts as a
  list of PaymentMethodData objects.  The user's account is identified by the
  user_email provided in the data_parts.

  This tool finds and returns all the payment methods associated with the user's
  account that match the merchant's accepted payment methods.

  Args:
    data_parts: DataPart contents. Should contain a single user_email and a
      list of PaymentMethodData objects.
    updater: The TaskUpdater instance for updating the task state.
    current_task: The current task if there is one.
  """
  user_email = message_utils.find_data_part("user_email", data_parts)
  method_data = message_utils.find_data_parts(
      PAYMENT_METHOD_DATA_DATA_KEY, data_parts
  )
  if not user_email:
    raise ValueError(
        "user_email is required for search_payment_methods"
    )
  if not method_data:
    raise ValueError("method_data is required for search_payment_methods")

  merchant_method_data_list = [
      PaymentMethodData.model_validate(data) for data in method_data
  ]
  eligible_aliases = _get_eligible_payment_method_aliases(
      user_email, merchant_method_data_list
  )
  await updater.add_artifact([Part(root=DataPart(data=eligible_aliases))])
  await updater.complete()


async def handle_get_payment_method_raw_credentials(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Exchanges a payment token for the payment method's raw credentials.

  Updates a task with the payment credentials.

  Args:
    data_parts: DataPart contents. Should contain a single PaymentMandate.
    updater: The TaskUpdater instance for updating the task state.
    current_task: The current task if there is one.
  """

  payment_mandate_contents = message_utils.parse_canonical_object(
      PAYMENT_MANDATE_DATA_KEY, data_parts, PaymentMandate
  ).payment_mandate_contents

  token = payment_mandate_contents.payment_response.details.get(
      "token", {}
  ).get("value", "")
  payment_mandate_id = payment_mandate_contents.payment_mandate_id

  payment_method = account_manager.verify_token(token, payment_mandate_id)
  if not payment_method:
    raise ValueError(f"Payment method not found for token: {token}")
  await updater.add_artifact([Part(root=DataPart(data=payment_method))])
  await updater.complete()


async def handle_create_payment_credential_token(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Handles a request to get a payment credential token.

  Updates a task with the payment credential token.

  Args:
    data_parts: DataPart contents. Should contain the user_email and
      payment_method_alias.
    updater: The TaskUpdater instance for updating the task state.
    current_task: The current task if there is one.
  """
  user_email = message_utils.find_data_part("user_email", data_parts)
  payment_method_alias = message_utils.find_data_part(
      "payment_method_alias", data_parts
  )
  if not user_email or not payment_method_alias:
    raise ValueError(
        "user_email and payment_method_alias are required for"
        " create_payment_credential_token"
    )

  tokenized_payment_method = account_manager.create_token(
      user_email, payment_method_alias
  )

  await updater.add_artifact(
      [Part(root=DataPart(data={"token": tokenized_payment_method}))]
  )
  await updater.complete()


async def handle_signed_payment_mandate(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Handles a signed payment mandate.

  Adds the payment mandate id to the token in storage and then completes the
  task.

  Args:
    data_parts: DataPart contents. Should contain a single PaymentMandate.
    updater: The TaskUpdater instance for updating the task state.
    current_task: The current task if there is one.
  """
  payment_mandate = message_utils.parse_canonical_object(
      PAYMENT_MANDATE_DATA_KEY, data_parts, PaymentMandate
  )
  token = payment_mandate.payment_mandate_contents.payment_response.details.get(
      "token", {}
  ).get("value", "")
  payment_mandate_id = (
      payment_mandate.payment_mandate_contents.payment_mandate_id
  )
  account_manager.update_token(token, payment_mandate_id)
  await updater.complete()


def _get_payment_method_aliases(
    payment_methods: list[dict[str, Any]],
) -> list[str | None]:
  """Gets the payment method aliases from a list of payment methods."""
  return [payment_method.get("alias") for payment_method in payment_methods]


def _get_eligible_payment_method_aliases(
    user_email: str, merchant_accepted_payment_methods: list[PaymentMethodData]
) -> dict[str, list[str | None]]:
  """Gets the payment_methods eligible according to given PaymentMethodData.

  Args:
    user_email: The email address of the user's account.
    merchant_accepted_payment_methods: A list of eligible payment method
      criteria.

  Returns:
    A list of the user's eligible payment_methods.
  """
  payment_methods = account_manager.get_account_payment_methods(user_email)
  eligible_payment_methods = []

  for payment_method in payment_methods:
    for criteria in merchant_accepted_payment_methods:
      if _payment_method_is_eligible(payment_method, criteria):
        eligible_payment_methods.append(payment_method)
        break
  return {
      "payment_method_aliases": _get_payment_method_aliases(
          eligible_payment_methods
      )
  }


def _payment_method_is_eligible(
    payment_method: dict[str, Any], merchant_criteria: PaymentMethodData
) -> bool:
  """Checks if a payment method is eligible based on a PaymentMethodData.

  Args:
    payment_method: A dictionary representing the payment method.
    merchant_criteria: A PaymentMethodData object containing the eligibility
      criteria.

  Returns:
    True if the payment_method is eligible according to the payment method,
    False otherwise.
  """
  if payment_method.get("type", "") != merchant_criteria.supported_methods:
    return False

  merchant_supported_networks = [
      network.casefold()
      for network in merchant_criteria.data.get("network", [])
  ]
  if not merchant_supported_networks:
    return False

  payment_card_networks = payment_method.get("network", [])
  for network_info in payment_card_networks:
    for supported_network in merchant_supported_networks:
      if network_info.get("name", "").casefold() == supported_network:
        return True
  return False
