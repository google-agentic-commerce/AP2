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

"""Tools used by the shopper subagent.

Each agent uses individual tools to handle distinct tasks throughout the
shopping and purchasing process.
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from a2a.types import Artifact
from google.adk.tools.tool_context import ToolContext

from ap2.types.mandate import CART_MANDATE_DATA_KEY
from ap2.types.mandate import CartMandate
from ap2.types.mandate import INTENT_MANDATE_DATA_KEY
from ap2.types.mandate import IntentMandate
from common.a2a_message_builder import A2aMessageBuilder
from common.artifact_utils import find_canonical_objects
from roles.shopping_agent.remote_agents import merchant_agent_client


def create_intent_mandate(
    natural_language_description: str,
    user_cart_confirmation_required: bool,
    merchants: list[str],
    skus: list[str],
    requires_refundability: bool,
    tool_context: ToolContext,
) -> IntentMandate:
  """Creates an IntentMandate object.

  Args:
    natural_language_description: The description of the user's intent.
    user_cart_confirmation_required: If the user must confirm the cart.
    merchants: A list of allowed merchants.
    skus: A list of allowed SKUs.
    requires_refundability: If the items must be refundable.
    tool_context: The ADK supplied tool context.

  Returns:
    An IntentMandate object valid for 1 day.
  """
  intent_mandate = IntentMandate(
      natural_language_description=natural_language_description,
      user_cart_confirmation_required=user_cart_confirmation_required,
      merchants=merchants,
      skus=skus,
      requires_refundability=requires_refundability,
      intent_expiry=(
          datetime.now(timezone.utc) + timedelta(days=1)
      ).isoformat(),
  )
  tool_context.state["intent_mandate"] = intent_mandate
  return intent_mandate


async def find_products(
    tool_context: ToolContext, debug_mode: bool = False
) -> list[CartMandate]:
  """Calls the merchant agent to find products matching the user's intent.

  Args:
    tool_context: The ADK supplied tool context.
    debug_mode: Whether the agent is in debug mode.

  Returns:
    A list of CartMandate objects.

  Raises:
    RuntimeError: If the merchant agent fails to provide products.
  """
  intent_mandate = tool_context.state["intent_mandate"]
  if not intent_mandate:
    raise RuntimeError("No IntentMandate found in tool context state.")
  risk_data = _collect_risk_data(tool_context)
  if not risk_data:
    raise RuntimeError("No risk data found in tool context state.")
  message = (
      A2aMessageBuilder()
      .add_text("Find products that match the user's IntentMandate.")
      .add_data(INTENT_MANDATE_DATA_KEY, intent_mandate.model_dump())
      .add_data("risk_data", risk_data)
      .add_data("debug_mode", debug_mode)
      .add_data("shopping_agent_id", "trusted_shopping_agent")
      .build()
  )
  task = await merchant_agent_client.send_a2a_message(message)

  if task.status.state != "completed":
    raise RuntimeError(f"Failed to find products: {task.status}")

  tool_context.state["shopping_context_id"] = task.context_id
  cart_mandates = _parse_cart_mandates(task.artifacts)
  tool_context.state["cart_mandates"] = cart_mandates
  return cart_mandates


def update_chosen_cart_mandate(cart_id: str, tool_context: ToolContext) -> str:
  """Updates the chosen CartMandate in the tool context state.

  Args:
    cart_id: The ID of the chosen cart.
    tool_context: The ADK supplied tool context.
  """
  cart_mandates: list[CartMandate] = tool_context.state.get("cart_mandates", [])
  for cart in cart_mandates:
    print(
        f"Checking cart with ID: {cart.contents.id} with chosen ID: {cart_id}"
    )
    if cart.contents.id == cart_id:
      tool_context.state["chosen_cart_id"] = cart_id
      return f"CartMandate with ID {cart_id} selected."
  return f"CartMandate with ID {cart_id} not found."


def _parse_cart_mandates(artifacts: list[Artifact]) -> list[CartMandate]:
  """Parses a list of artifacts into a list of CartMandate objects."""
  return find_canonical_objects(artifacts, CART_MANDATE_DATA_KEY, CartMandate)


def _collect_risk_data(tool_context: ToolContext) -> dict:
  """Creates a risk_data in the tool_context."""
  # This is a fake risk data for demonstration purposes.
  risk_data = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...fake_risk_data"
  tool_context.state["risk_data"] = risk_data
  return risk_data
