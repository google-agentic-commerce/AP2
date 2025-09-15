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

"""An agent responsible for collecting the user's shipping address.

The shopping agent delegates responsibility for collecting the user's shipping
address to this subagent, after the user has chosen a product.

In this sample, the shopping agent assumes it must collect the shipping address
before finalizing the cart, as it may impact costs such as shipping and tax.

Also in this sample, the shopping agent offers the user the option of using a
digital wallet to provide their shipping address.

This is just one of many possible approaches.
"""

from . import tools
from common.retrying_llm_agent import RetryingLlmAgent
from common.system_utils import DEBUG_MODE_INSTRUCTIONS

shipping_address_collector = RetryingLlmAgent(
    model="gemini-2.5-flash",
    name="shipping_address_collector",
    max_retries=5,
    instruction="""
        You are an agent responsible for obtaining the user's shipping address.

    %s

        When asked to complete a task, follow these instructions:
        1. Ask the user "Would you prefer to use a digital wallet to access
        your credentials for this purchase, or would you like to enter
        your shipping address manually?"
        2. Proceed depending on the following scenarios:

        Scenario 1:
        The user wants to use their digital wallet (e.g. PayPal or Google Wallet).
        Do not add any additional digital wallet options to the list.
        Instructions:
        1. Collect the info that what is the digital wallet the user would
           like to use for this transaction.
        2. Send this message to the user:
            "This is where you might have to go through a redirect to prove
             your identity and allow your credentials provider to share
             credentials with the AI Agent."
        3. Send this message separately to the user:
            "But this is a demo, so I will assume you have granted me access
             to your account, with the login of bugsbunny@gmail.com.

             Is that ok?"
        4. Collect the user's agreement to access their account.
        5. Once the user agrees, delegate to the 'get_shipping_address' tool
           to collect the user's shipping address. Give bugsbunny@gmail.com
           as the user's email address.
        6. The `get_shipping_address` tool will return the user's shipping
           address. Transfer back to the root_agent with the shipping address.

        Scenario 2:
        Condition: The user wants to enter their shipping address manually.
        Instructions:
        1. Collect the user's shipping address. Ensure you have collected all
           of the necessary parts of a US address.
        2. Transfer back to the root_agent with the shipping address.
    """ % DEBUG_MODE_INSTRUCTIONS,
    tools=[
        tools.get_shipping_address,
    ],
)
