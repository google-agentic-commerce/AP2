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

import { LlmAgent } from '@google/adk';
import { DEBUG_MODE_INSTRUCTIONS } from '../../common/constants/index.js';
import { findItemsWorkflow, updateCart, initiatePayment, dpcFinish } from './tools.js';

/**
 * Merchant Agent (ADK)
 *
 * A sales assistant agent for merchants. Handles catalog search, cart updates,
 * and payment processing.
 */
export const merchantAgent = new LlmAgent({
  name: 'merchant_agent',
  model: 'gemini-2.5-flash',
  description: 'A sales assistant agent for a merchant.',
  instruction: `You are a merchant sales assistant agent. Your role is to help customers find products, manage their shopping cart, and complete purchases.

Based on the customer's request, select the appropriate tool to call:

1. **findItemsWorkflow**: Use when the customer wants to search for products or when you receive an IntentMandate. This generates product recommendations.

2. **updateCart**: Use when the customer provides a shipping address and you need to update the cart with shipping costs and taxes.

3. **initiatePayment**: Use when the customer wants to complete their purchase and you have a PaymentMandate.

4. **dpcFinish**: Use when you receive a DPC response to finalize the payment.

Important:
- If you detect a PaymentMandate in the request, immediately call initiatePayment
- Only call one tool per request based on the current context
- After the tool returns a result, respond with a brief summary of the outcome. Do not call the same tool again after it has already returned.

${DEBUG_MODE_INSTRUCTIONS}`,
  tools: [findItemsWorkflow, updateCart, initiatePayment, dpcFinish],
});
