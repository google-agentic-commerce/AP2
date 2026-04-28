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

"""An agent responsible for collecting the user's choice of payment method.

The shopping agent delegates responsibility for collecting the user's choice of
payment method to this subagent, after the user has finalized their cart.

Through the get_payment_methods tool, the agent retrieves a list of eligible
payment methods from the credentials provider agent. The agent then presents the
list to the user, allowing them to select their preferred payment method.

After selection, the agent gets a purchase token from the credentials
provider, which is then sent to the merchant agent for payment.
"""

from common.retrying_llm_agent import RetryingLlmAgent
from common.system_utils import DEBUG_MODE_INSTRUCTIONS

from . import tools


payment_method_collector = RetryingLlmAgent(
    model="gemini-3.1-flash-lite-preview",
    name="payment_method_collector",
    max_retries=5,
    instruction="""
    You are an agent responsible for obtaining the user's payment method for a
    purchase.

    %s

    When asked to complete a task, follow these instructions:
    1. Call the `get_payment_methods` tool to get eligible
       payment_method_aliases. Use bugsbunny@gmail.com as the user_email.
       Present the payment_method_aliases to the user in a numbered list.
    2. Ask the user to choose which of their forms of payment they would
       like to use for the payment. Remember that payment_method_alias.
    3. Call the `get_payment_credential_token` tool to get the payment
       credential token with the user_email and payment_method_alias.
    4. Transfer back to the root_agent with the payment_method_alias.
    """ % DEBUG_MODE_INSTRUCTIONS,
    tools=[
        tools.get_payment_methods,
        tools.get_payment_credential_token,
    ],
)
