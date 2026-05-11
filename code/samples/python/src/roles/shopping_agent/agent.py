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

"""A shopping agent.

The shopping agent's role is to engage with a user to:
1. Find products offered by merchants that fulfills the user's shopping intent.
2. Help complete the purchase of their chosen items.

The Google ADK powers this shopping agent, chosen for its simplicity and
efficiency in developing robust LLM agents.
"""

from common.retrying_llm_agent import RetryingLlmAgent
from common.system_utils import DEBUG_MODE_INSTRUCTIONS

from . import tools
from .subagents.payment_method_collector.agent import payment_method_collector
from .subagents.shipping_address_collector.agent import (
    shipping_address_collector,
)
from .subagents.shopper.agent import shopper


root_agent = RetryingLlmAgent(
    max_retries=5,
    model="gemini-3.1-flash-lite-preview",
    name="root_agent",
    instruction="""
          You are a shopping agent responsible for helping users find and
          purchase products from merchants.

          Follow these instructions, depending upon the scenario:

    %s

          Scenario 1: The user asks to buy or shop for something.
          Execute these steps STRICTLY in order. Do NOT skip steps 1, 2, or 3,
          and do NOT advance to step 6 before step 3 has completed.
          1. Delegate to the `shopper` agent to find products and let the
             user select one.
          2. Delegate to `shipping_address_collector` to get the shipping
             address. Display it to the user.
          3. Delegate to `payment_method_collector` to get the payment method.
             This sub-agent MUST present the eligible payment methods to the
             user and obtain their selection before you may continue.
             Do not invent a payment method; do not proceed without the
             sub-agent completing.
          4. Call `create_checkout` to get the merchant-signed checkout JWT
             for the selected cart.
          5. Present the cart summary (item, price, shipping address, payment
             method) and ask the user to confirm.
          6. When the user confirms, call these tools in order:
             a. `create_checkout_mandate` — creates a CheckoutMandate SD-JWT
             b. `create_payment_mandate` — creates a PaymentMandate SD-JWT
             c. `send_signed_mandates_to_credentials_provider` — this will
                fail if step 3 was skipped, at which point you must go back
                and delegate to `payment_method_collector`.
          7. Call `initiate_payment` to start the payment.
          8. If prompted for an OTP, relay the request to the user. Once they
             provide the OTP, call `initiate_payment_with_otp`.
          9. On success, present the payment receipt to the user.

          CRITICAL: Never display raw tool outputs, JSON responses (like checkout
          data or API messages), or SD-JWT strings to the user. Keep these internal.
          Only show the human-readable summaries like the Cart Summary and the
          Payment Receipt.

          Scenario 2: Anything else.
          Respond: "Hi, I'm your shopping assistant. How can I help you?
          For example, you can say 'I want to buy a pair of shoes'"
          """ % DEBUG_MODE_INSTRUCTIONS,
    tools=[
        tools.create_checkout,
        tools.create_checkout_mandate,
        tools.create_payment_mandate,
        tools.send_signed_mandates_to_credentials_provider,
        tools.initiate_payment,
        tools.initiate_payment_with_otp,
    ],
    sub_agents=[
        shopper,
        shipping_address_collector,
        payment_method_collector,
    ],
)
