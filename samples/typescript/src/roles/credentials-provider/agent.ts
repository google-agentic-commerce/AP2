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
import {
  handleCreatePaymentCredentialToken,
  handleGetPaymentMethodRawCredentials,
  handleGetShippingAddress,
  handleSearchPaymentMethods,
  handleSignedPaymentMandate,
  handlePaymentReceipt,
} from './tools.js';

/**
 * Credentials Provider Agent (ADK)
 *
 * This agent acts as a secure digital wallet managing user payment credentials.
 */
export const credentialsProviderAgent = new LlmAgent({
  name: 'credentials_provider_agent',
  model: 'gemini-2.5-flash',
  description: 'An agent that holds a user\'s payment credentials.',
  instruction: `You are a credentials provider agent acting as a secure digital wallet.
Your job is to manage a user's payment methods and shipping addresses.

IMPORTANT RULES:
1. Read the user request carefully and call EXACTLY ONE tool.
2. After the tool returns its result, respond with a single short
   sentence confirming what was done. Example: "Shipping address retrieved."
3. NEVER call a tool more than once per request.
4. NEVER ask follow-up questions or continue the conversation.
5. Your entire response after the tool result must be one sentence.

${DEBUG_MODE_INSTRUCTIONS}`,
  tools: [
    handleCreatePaymentCredentialToken,
    handleGetPaymentMethodRawCredentials,
    handleGetShippingAddress,
    handleSearchPaymentMethods,
    handleSignedPaymentMandate,
    handlePaymentReceipt,
  ],
});
