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

"""An A2A Agent Executor for the credentials provider agent.

A credentials provider has several roles:
1. Manage a user's payment credentials & shipping address.
2. Find available payment methods for a particular purchase.
3. Provide a payment credential token for a specific payment method.
4. Provide payment credentials to a processor for completion of a payment.

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



class CredentialsProviderExecutor(BaseServerExecutor):
  """AgentExecutor for the credentials provider agent."""

  _system_prompt = """
    You are a credentials provider agent acting as a secure digital wallet.
    Your job is to manage a user's payment methods and shipping addresses.

    Based on the user's request, identify their intent and select the
    single correct tool to use. Your only output should be a tool call.
    Do not engage in conversation.

    %s
  """ % DEBUG_MODE_INSTRUCTIONS

  def __init__(self, supported_extensions: list[dict[str, Any]] = None):
    """Initializes the CredentialsProviderExecutor.

    Args:
        supported_extensions: A list of extension objects supported by the
          agent.
    """

    agent_tools = [
        tools.handle_create_payment_credential_token,
        tools.handle_get_payment_method_raw_credentials,
        tools.handle_get_shipping_address,
        tools.handle_search_payment_methods,
        tools.handle_signed_payment_mandate,
    ]
    super().__init__(supported_extensions, agent_tools, self._system_prompt)
