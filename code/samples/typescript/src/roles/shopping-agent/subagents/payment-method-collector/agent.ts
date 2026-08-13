/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { LlmAgent } from "@google/adk";
import { DEBUG_MODE_INSTRUCTIONS, HUMAN_PRESENTATION_INSTRUCTIONS } from "../../../../common/constants/index.js";
import { getCartSummary, getPaymentMethods, getPaymentCredentialToken } from "./tools.js";

/**
 * Payment Method Collector Agent (ADK)
 *
 * Collects payment method information from users.
 */
export const paymentCollectorAgent = new LlmAgent({
  name: "payment_method_collector_agent",
  model: "gemini-3.1-flash-lite",
  description:
    "A subagent that collects payment method information from users.",
  instruction: `You are an agent responsible for obtaining the user's payment method for a purchase.

When asked to complete a task, follow these instructions:
1. Call the get_cart_summary tool to get the current cart's exact amounts
    and the shipping address on file.
2. Present a clear and organized summary of the cart to the user, using
    EXACTLY the amounts returned by get_cart_summary — never estimate,
    recompute, or reuse amounts from earlier in the conversation. The
    summary should be divided into two main sections:
    a. Order Summary:
        Merchant: The merchantName from the tool result.
        Price Breakdown: One line per entry in orderSummary.lineItems
        (item, shipping, tax), then the orderSummary.total.
        Format all amounts with commas and the currency symbol.
        Expires: Convert the cartExpiry into a human-readable format
        (e.g., "in 2 hours," "by tomorrow at 5 PM"). Convert the time to the
        user's timezone.
        Refund Period: Convert the refundPeriodDays into a human-readable
        format (e.g., "30 days," "14 days").
    b. Show the shipping address from the tool result in a well-formatted
        manner.
    Ensure the entire presentation is well-formatted and easy to read.
3. Call the get_payment_methods tool to get eligible
    payment_method_aliases with the method_data from the CartMandate's
    payment_request. Present the payment_method_aliases to the user in
    a numbered list.
4. Ask the user to choose which of their forms of payment they would
    like to use for the payment. Remember that payment_method_alias.
5. Call the get_payment_credential_token tool to get the payment
    credential token with the user_email and payment_method_alias.
6. Once you have the token, immediately transfer back to the root_agent
    with the payment_method_alias so checkout continues — do not stop to
    wait for further user input. Never say the payment was processed or
    completed — no payment has happened yet.

${HUMAN_PRESENTATION_INSTRUCTIONS}

${DEBUG_MODE_INSTRUCTIONS}`,
  tools: [getCartSummary, getPaymentMethods, getPaymentCredentialToken],
});
