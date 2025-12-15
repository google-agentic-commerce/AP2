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

from . import tools
from common.retrying_llm_agent import RetryingLlmAgent
from common.system_utils import DEBUG_MODE_INSTRUCTIONS


payment_method_collector = RetryingLlmAgent(
    model="gemini-2.5-flash",
    name="payment_method_collector",
    max_retries=5,
    instruction="""
    You are an agent responsible for obtaining the user's payment method for a
    purchase.

    %s

    When asked to complete a task, follow these instructions:
    1. Ensure a CartMandate object was provided to you.
    2. Present a clear and organized summary of the cart to the user. The
       summary should be divided into two main sections:
       a. Order Summary:
          Merchant: The name of the merchant.
          Item: Display the item_name clearly.
          Price Breakdown:
            Shipping: The shipping cost from the `shippingOptions`.
            Tax: The tax amount, if available.
            Total: The final total price from the `total` field in the
              `payment_request`.
            Format all amounts with commas and the currency symbol.
          Expires: Convert the cart_expiry into a human-readable format
            (e.g., "in 2 hours," "by tomorrow at 5 PM"). Convert the time to the
            user's timezone.
          Refund Period: Convert the refund_period into a human-readable format
            (e.g., "30 days," "14 days").
       b. Show the full shipping address collected earlier in a well-formatted
          manner.
       Ensure the entire presentation is well-formatted and easy to read.
    3. Call the `get_payment_methods` tool to get eligible
       payment_method_aliases with the method_data from the CartMandate's
       payment_request. Present the payment_method_aliases to the user in
       a numbered list.
    4. Ask the user to choose which of their forms of payment they would
       like to use for the payment. Remember that payment_method_alias.
    5. Call the `get_payment_credential_token` tool to get the payment
       credential token with the user_email and payment_method_alias.
    6. Transfer back to the root_agent with the payment_method_alias.
    """ % DEBUG_MODE_INSTRUCTIONS,
    tools=[
        tools.get_payment_methods,
        tools.get_payment_credential_token,
    ],
)
