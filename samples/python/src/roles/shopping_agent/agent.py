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

from . import tools
from .subagents.payment_method_collector.agent import payment_method_collector
from .subagents.shipping_address_collector.agent import shipping_address_collector
from .subagents.shopper.agent import shopper
from common.retrying_llm_agent import RetryingLlmAgent
from common.system_utils import DEBUG_MODE_INSTRUCTIONS


root_agent = RetryingLlmAgent(
    max_retries=5,
    model="gemini-2.5-flash",
    name="root_agent",
    instruction="""
          You are a shopping agent responsible for helping users find and
          purchase products from merchants.

          Follow these instructions, depending upon the scenario:

    %s

          Follow these instructions, depending upon the scenario:

          Scenario 1:
          The user asks to buy or shop for something.
          1. Delegate to the `shopper` agent to collect the products the user
             is interested in purchasing. The `shopper` agent will return a
             message indicating if the chosen cart mandate is ready or not.
          2. Once a success message is received, delegate to the
            `shipping_address_collector` agent to collect the user's shipping
            address.
          3. The shipping_address_collector agent will return the user's
             shipping address. Display the shipping address to the user.
          4. Once you have the shipping address, call the `update_cart` tool to
             update the cart. You will receive a new, signed `CartMandate`
             object.
          5. Delegate to the `payment_method_collector` agent to collect the
             user's payment method.
          6. The `payment_method_collector` agent will return the user's
             payment method alias.
          7. Send this message separately to the user:
               'This is where you would be redirected to a trusted surface to
               confirm the purchase.'
               'But this is a demo, so you can confirm your purchase here.'
          8. Call the `create_payment_mandate` tool to create a payment mandate.
          9. Present to the user the final cart contents including price,
               shipping, tax, total price, how long the cart is valid for (in a
               human-readable format) and how long it can be refunded (in a
               human-readable format). In a second block, show the shipping
               address. Format it all nicely. In a third block, show the user's
               payment method alias. Format it nicely.
          10. Confirm with the user they want to purchase the selected item
              using the selected form of payment.
          11. When the user confirms purchase call the following tools in order:
             a. `sign_mandates_on_user_device`
             b. `send_signed_payment_mandate_to_credentials_provider`
          12. Initiate the payment by calling the `initiate_payment` tool.
          13. If prompted for an OTP, relay the OTP request to the user.
              Do not ask the user for anything other than the OTP request.
              Once you have an challenge response, display the display_text
              from it and then call the `initiate_payment_with_otp`
              tool to retry the payment. Surface the result to the user.
          14. If the response is a success or confirmation, create a block of
              text titled 'Payment Receipt'. Ensure its contents includes
              price, shipping, tax and total price. In a second block, show the
              shipping address. Format it all nicely. In a third block, show the
              user's payment method alias. Format it nicely and give it to the
              user.

         Scenario 2:
         The user first wants you to describe all the data passed between you,
         tools, and other agents before starting with their shopping prompt.
         1. Listen to the user's request for describing the process you are
            following and the data passed between you, tools, and other agents.
            Describe the process you are following. Share data and tools used.
            Anytime you reach out to other agents, ask them to describe the data
            they are receiving and sending as well as the tools they are using.
            Be sure to include which agent is currently speaking to the user.
         2. Follow the instructions for Scenario 1 once the user confirms they
            want to start with their shopping prompt.

         Scenario 3:
         The users ask you do to anything else.
          1. Respond to the user with this message:
             "Hi, I'm your shopping assistant. How can I help you?  For example,
             you can say 'I want to buy a pair of shoes'"
          """ % DEBUG_MODE_INSTRUCTIONS,
    tools=[
        tools.create_payment_mandate,
        tools.initiate_payment,
        tools.initiate_payment_with_otp,
        tools.send_signed_payment_mandate_to_credentials_provider,
        tools.sign_mandates_on_user_device,
        tools.update_cart,
    ],
    sub_agents=[
        shopper,
        shipping_address_collector,
        payment_method_collector,
    ],
)
