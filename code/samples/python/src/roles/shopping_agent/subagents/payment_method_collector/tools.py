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

"""Tools used by the payment method collector subagent.

Each agent uses individual tools to handle distinct tasks throughout the
shopping and purchasing process.
"""

import os

from ap2.models.payment_request import PAYMENT_METHOD_DATA_DATA_KEY
from common import artifact_utils
from common.a2a_message_builder import A2aMessageBuilder
from google.adk.tools.tool_context import ToolContext
from roles.shopping_agent.remote_agents import credentials_provider_client


def _merchant_accepted_payment_method() -> dict:
  """Returns the merchant's accepted PaymentMethodData for the current flow.

  The scenario run scripts set ``PAYMENT_METHOD`` to either ``CARD`` (default)
  or ``x402``. Matches the branching already used by the credentials provider
  in ``_get_eligible_payment_method_aliases`` / ``_payment_method_is_eligible``.
  """
  if os.environ.get("PAYMENT_METHOD") == "x402":
    return {
        "supported_methods": "https://www.x402.org/",
        "data": {},
    }
  return {
      "supported_methods": "CARD",
      "data": {"network": ["mastercard", "amex"]},
  }


async def get_payment_methods(
    user_email: str,
    tool_context: ToolContext,
) -> list[str]:
  """Gets the user's payment methods from the credentials provider.

  Args:
    user_email: Identifies the user's account.
    tool_context: The ADK supplied tool context.

  Returns:
    A dictionary of the user's applicable payment methods.
  """
  message_builder = (
      A2aMessageBuilder()
      .set_context_id(tool_context.state["shopping_context_id"])
      .add_text("Get a filtered list of the user's payment methods.")
      .add_data("user_email", user_email)
      .add_data(
          PAYMENT_METHOD_DATA_DATA_KEY,
          _merchant_accepted_payment_method(),
      )
  )
  task = await credentials_provider_client.send_a2a_message(
      message_builder.build()
  )
  payment_methods = artifact_utils.get_first_data_part(task.artifacts)
  return payment_methods


async def get_payment_credential_token(
    user_email: str,
    payment_method_alias: str,
    tool_context: ToolContext,
) -> str:
  """Gets a payment credential token from the credentials provider.

  Args:
    user_email: The user's email address.
    payment_method_alias: The payment method alias.
    tool_context: The ADK supplied tool context.

  Returns:
    Status of the call and the payment credential token.
  """
  message = (
      A2aMessageBuilder()
      .set_context_id(tool_context.state["shopping_context_id"])
      .add_text("Get a payment credential token for the user's payment method.")
      .add_data("payment_method_alias", payment_method_alias)
      .add_data("user_email", user_email)
      .build()
  )
  task = await credentials_provider_client.send_a2a_message(message)
  data = artifact_utils.get_first_data_part(task.artifacts)
  token = data.get("token")
  credentials_provider_agent_card = (
      await credentials_provider_client.get_agent_card()
  )

  tool_context.state["payment_credential_token"] = {
      "value": token,
      "url": credentials_provider_agent_card.url,
  }
  return {"status": "success", "token": token}
