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

"""An agent responsible for helping the user shop for products.

The agent gathers the user's purchase intent, sends it to the merchant
to find products, and lets the user select one.
"""

from common.retrying_llm_agent import RetryingLlmAgent
from common.system_utils import DEBUG_MODE_INSTRUCTIONS

from . import tools


shopper = RetryingLlmAgent(
    model="gemini-3.1-flash-lite-preview",
    name="shopper",
    max_retries=5,
    instruction="""
    You are an agent responsible for helping the user shop for products.

    %s

    When asked to complete a task, follow these instructions:
    1. Find out what the user is interested in purchasing. Ask clarifying
      questions one at a time (item description, preferences, budget).
    2. Once you have enough information, call 'find_products' with a
      natural language description of what the user wants. The merchant
      will return product options as cart entries.
    3. Present the options to the user. For each option show:
        - Item name (bold)
        - Price with currency symbol
        - Cart ID
      Recommend the best match and explain why.
    4. Ask the user which item they'd like to purchase.
    5. Once they choose, call 'select_cart' with the cart_id.
    6. If successful, hand off to the root_agent for checkout.
    """ % DEBUG_MODE_INSTRUCTIONS,
    tools=[
        tools.find_products,
        tools.select_cart,
    ],
)
