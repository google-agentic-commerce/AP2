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

"""Agent executor for processing payments on behalf of a merchant.

This agent's role is to:
1. Complete payments, engaging with the credentials provider agent when needed.

In order to clearly demonstrate the use of the Agent Payments Protocol A2A
extension, this agent was built directly using the A2A framework.

The core logic of how an A2A agent processes requests and generates responses is
handled by an AgentExecutor. The BaseServerExecutor handles the common task of
interpreting the user's request, identifying the appropriate tool to use, and
invoking it to complete a task.
"""


from typing import Any

from . import tools
from common.base_server_executor import BaseServerExecutor
from common.system_utils import DEBUG_MODE_INSTRUCTIONS




class PaymentProcessorExecutor(BaseServerExecutor):
  """AgentExecutor for the merchant payment processor agent."""

  _system_prompt = """
    You are a payment processor agent. Your role is to process payments
    on behalf of a merchant.

    %s
  """ % DEBUG_MODE_INSTRUCTIONS

  def __init__(self, supported_extensions: list[dict[str, Any]] = None):
    """Initializes the PaymentProcessorExecutor."""
    agent_tools = [
        tools.initiate_payment,
    ]
    super().__init__(supported_extensions, agent_tools, self._system_prompt)
