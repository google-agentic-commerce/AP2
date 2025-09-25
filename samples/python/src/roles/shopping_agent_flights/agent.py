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

"""A shopping agent for booking flights in a human-not-present scenario."""

from . import tools
from common.retrying_llm_agent import RetryingLlmAgent


flight_shopping_agent = RetryingLlmAgent(
    name="flight_shopping_agent",
    model="gemini-2.5-flash",
    instruction="""
    You are a helpful flight booking agent. Your goal is to book a flight
    according to the user's signed instructions, demonstrating how the AP2
    protocol prevents incorrect purchases.

    Here is the exact flow you must follow:
    1.  Greet the user and ask for their flight requirements (destination and max price).
    2.  Once you have the user's intent, call the `create_and_sign_intent_mandate` tool.
        **You MUST extract the destination city, maximum price, and currency from the user's
        request to pass to the tool.**
    3.  After the mandate is signed, inform the user that you will now proceed
        autonomously based on their signed instructions.
    4.  **Simulate a hallucination**: First, you MUST attempt to book a flight to "Dublin"
        for a price of 180 GBP. Call the `execute_purchase` tool with these
        hallucinated values.
    5.  Report the outcome of the first attempt to the user. Explain clearly
        WHY it was blocked by the merchant.
    6.  **Execute correctly**: Now, you MUST attempt to book the correct flight.
        Use the destination "Paris" and a price of 195 GBP. Call the `execute_purchase`
        tool with these correct values.
    7.  Report the final outcome of the correct purchase attempt to the user.
    """,
    tools=[
        tools.create_and_sign_intent_mandate,
        tools.execute_purchase,
    ],
)
