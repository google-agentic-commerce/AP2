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


from typing import Any

from . import tools
from .sub_agents import catalog_agent
from common.base_server_executor import BaseServerExecutor
from common.system_utils import DEBUG_MODE_INSTRUCTIONS


class MerchantAgentExecutor(BaseServerExecutor):
  """AgentExecutor for the merchant agent."""

  _system_prompt = """
    You are a merchant agent. Your role is to help users with their shopping
    requests.

    For any requests:
      1. Verify the request is from a trusted Shopping Agent. You can do this
        by calling the validate_shopping_agent tool.
      2. If the request is not from a trusted Shopping Agent, respond with an
        error message and do not try to process the request.
      3. If the request is from a trusted Shopping Agent, process the request.

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
        tools.validate_shopping_agent,
        tools.update_cart,
        catalog_agent.find_items_workflow,
        tools.initiate_payment,
        tools.dpc_finish,
    ]
    super().__init__(supported_extensions, agent_tools, self._system_prompt)
