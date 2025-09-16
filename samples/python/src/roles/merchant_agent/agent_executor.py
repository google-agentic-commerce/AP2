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

"""A merchant agent executor for handling user shopping requests.

This agent's role is to:
1. Route user intent to a catalog for product discovery.
2. Handle requests to update a shopping cart.
3. Forward payment requests to the appropriate payment processor.

In order to clearly demonstrate the use of the Agent Payments Protocol A2A
extension, this agent was built directly using the A2A framework.

The core logic of how an A2A agent processes requests and generates responses is
handled by an AgentExecutor. The BaseServerExecutor handles the common task of
interpreting the user's request, identifying the appropriate tool to use, and
invoking it to complete a task.
"""


import logging
from typing import Any

from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import Part
from a2a.types import Task
from a2a.types import TextPart

from . import tools
from .sub_agents import catalog_agent
from common import message_utils
from common.base_server_executor import BaseServerExecutor
from common.system_utils import DEBUG_MODE_INSTRUCTIONS


# A list of known Shopping Agent identifiers that this Merchant is willing to
# work with.
_KNOWN_SHOPPING_AGENTS = [
    "trusted_shopping_agent",
]

class MerchantAgentExecutor(BaseServerExecutor):
  """AgentExecutor for the merchant agent."""

  _system_prompt = """
    You are a merchant agent. Your role is to help users with their shopping
    requests.

    You can find items, update shopping carts, and initiate payments.

    %s
  """ % DEBUG_MODE_INSTRUCTIONS

  def __init__(self, supported_extensions: list[dict[str, Any]] = None):
    """Initializes the MerchantAgentExecutor.

    Args:
        supported_extensions: A list of extension objects supported by the
          agent.
    """
    agent_tools = [
        tools.update_cart,
        catalog_agent.find_items_workflow,
        tools.initiate_payment,
        tools.dpc_finish,
    ]
    super().__init__(supported_extensions, agent_tools, self._system_prompt)

  async def _handle_request(
      self,
      text_parts: list[str],
      data_parts: list[dict[str, Any]],
      updater: TaskUpdater,
      current_task: Task | None,
  ) -> None:
    """Overrides the base class method to validate the shopping agent first."""
    if not await self._validate_shopping_agent(data_parts, updater):
      error_message = updater.new_agent_message(
          parts=[
              Part(root=TextPart(text=f"Failed to validate shopping agent."))
          ]
      )
      await updater.failed(message=error_message)
      return
    await super()._handle_request(text_parts, data_parts, updater, current_task)

  async def _validate_shopping_agent(
      self, data_parts: list[dict[str, Any]], updater: TaskUpdater
  ) -> None:
    """Validates that the incoming request is from a trusted Shopping Agent.

    Args:
      data_parts: A list of data part contents from the request.

    Returns:
      True if the Shopping Agent is trusted, or False if not.
    """

    shopping_agent_id = message_utils.find_data_part(
        "shopping_agent_id", data_parts
    )
    logging.info(
        "Received request from shopping_agent_id: %s", shopping_agent_id
    )

    if not shopping_agent_id:
      logging.warning("Missing shopping_agent_id in request.")
      await _fail_task(
          updater, "Unauthorized Request: Missing shopping_agent_id."
      )
      return False

    if shopping_agent_id not in _KNOWN_SHOPPING_AGENTS:
      logging.warning("Unknown Shopping Agent: %s", shopping_agent_id)
      await _fail_task(
          updater, f"Unauthorized Request: Unknown agent '{shopping_agent_id}'."
      )
      return False

    logging.info(
        "Authorized request from shopping_agent_id: %s", shopping_agent_id
    )
    return True


async def _fail_task(updater: TaskUpdater, error_text: str) -> None:
  """A helper function to fail a task with a given error message."""
  error_message = updater.new_agent_message(
      parts=[Part(root=TextPart(text=error_text))]
  )
  await updater.failed(message=error_message)
