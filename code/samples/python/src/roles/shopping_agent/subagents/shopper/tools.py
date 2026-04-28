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

Finds products (as Cart objects) and lets the user select one.
"""

from ap2.models.cart import CART_DATA_KEY, Cart
from common.a2a_message_builder import A2aMessageBuilder
from common.artifact_utils import find_canonical_objects
from google.adk.tools.tool_context import ToolContext
from roles.shopping_agent.remote_agents import merchant_agent_client


async def find_products(
    catalog_search: str,
    tool_context: ToolContext,
    debug_mode: bool = False,
) -> list[Cart]:
  """Calls the merchant agent to find products matching the user's search.

  Args:
    catalog_search: The user's catalog search query.
    tool_context: The context object for the tool.
    debug_mode: Whether to run in debug mode.

  Returns:
    A list of Cart objects (cart_id, item_label, amount, currency).

  Raises:
    RuntimeError: If the merchant agent fails to find products.
  """
  risk_data = _collect_risk_data(tool_context)
  message = (
      A2aMessageBuilder()
      .add_text("Find products that match the user's request.")
      .add_data("catalog_search", catalog_search)
      .add_data("risk_data", risk_data)
      .add_data("debug_mode", debug_mode)
      .add_data("shopping_agent_id", "trusted_shopping_agent")
      .build()
  )
  task = await merchant_agent_client.send_a2a_message(message)

  if task.status.state != "completed":
    raise RuntimeError(f"Failed to find products: {task.status}")

  tool_context.state["shopping_context_id"] = task.context_id
  carts = find_canonical_objects(task.artifacts, CART_DATA_KEY, Cart)
  tool_context.state["available_carts"] = [
      c.model_dump(mode="json") for c in carts
  ]
  return carts


def select_cart(cart_id: str, tool_context: ToolContext) -> str:
  """Selects a cart by ID from the available carts."""
  available_carts = tool_context.state.get("available_carts", [])
  for cart in available_carts:
    if cart.get("cart_id") == cart_id:
      tool_context.state["chosen_cart_id"] = cart_id
      return f"Cart {cart_id} selected."
  return f"Cart {cart_id} not found."


def _collect_risk_data(tool_context: ToolContext) -> str:
  risk_data = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...fake_risk_data"
  tool_context.state["risk_data"] = risk_data
  return risk_data
