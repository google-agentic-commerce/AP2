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

import { Runner } from '@google/adk';
import type { AgentCard } from '@a2a-js/sdk';

import { credentialsProviderAgent } from './agent.js';
import { sessionService } from '../../common/config/session.js';
import { BaseAgentExecutor } from '../../common/server/base-executor.js';
import { bootstrapServer } from '../../common/server/bootstrap.js';
import { DATA_KEYS, A2A_DATA_KEYS } from '../../common/constants/index.js';
import { initKeyManager } from '../../common/vc/index.js';

const runner = new Runner({
  appName: 'ap2-credentials-provider',
  agent: credentialsProviderAgent,
  sessionService,
});

const agentExecutor = new BaseAgentExecutor({
  agentName: 'credentials_provider_agent',
  appName: 'ap2-credentials-provider',
  runner,
  maxLlmCalls: 3,
  workingMessage: 'Processing request...',
  preprocessMessage({ userText, dataParts }) {
    // Build a hint about available data so the LLM knows which tool to call
    const dataKeys = dataParts.flatMap((dp) => Object.keys(dp));
    const hasUserEmail = dataKeys.includes(A2A_DATA_KEYS.USER_EMAIL);
    const hasPaymentMandate = dataKeys.includes(DATA_KEYS.PAYMENT_MANDATE);
    const hasPaymentMethodData = dataKeys.includes(A2A_DATA_KEYS.PAYMENT_METHOD_DATA);
    const hasPaymentMethodAlias = dataKeys.includes(A2A_DATA_KEYS.PAYMENT_METHOD_ALIAS);

    if (hasPaymentMandate && hasUserEmail) {
      return `${userText}\n\nThe request data contains a PaymentMandate. Call the appropriate tool to handle it.`;
    }
    if (hasPaymentMethodData && hasUserEmail) {
      return `${userText}\n\nThe request data contains user_email and payment method criteria. Call handleSearchPaymentMethods.`;
    }
    if (hasPaymentMethodAlias && hasUserEmail) {
      return `${userText}\n\nThe request data contains user_email and payment_method_alias. Call handleCreatePaymentCredentialToken.`;
    }
    if (hasUserEmail) {
      return `${userText}\n\nThe request data contains user_email. Call handleGetShippingAddress now.`;
    }
    return userText;
  },
});

const agentCard: AgentCard = {
  name: 'CredentialsProvider',
  description: "An agent that holds a user's payment credentials.",
  url: 'http://localhost:8002',
  provider: { organization: 'AP2 Demo', url: 'https://github.com/google-agentic-commerce/ap2' },
  skills: [
    {
      id: 'initiate_payment',
      name: 'Initiate Payment',
      description: 'Initiates a payment with the correct payment processor.',
      tags: ['payments'],
    },
    {
      id: 'get_eligible_payment_methods',
      name: 'Get Eligible Payment Methods',
      description:
        'Provides a list of eligible payment methods for a particular purchase.',
      parameters: {
        type: 'object',
        properties: {
          email_address: {
            type: 'string',
            description:
              "The email address associated with the user's account.",
          },
        },
        required: ['email_address'],
      },
      tags: ['eligible', 'payment', 'methods'],
    } as AgentCard['skills'][number],
    {
      id: 'get_account_shipping_address',
      name: 'Get Shipping Address',
      description: "Fetches the shipping address from a user's wallet.",
      parameters: {
        type: 'object',
        properties: {
          email_address: {
            type: 'string',
            description:
              "The email address associated with the user's account.",
          },
        },
        required: ['email_address'],
      },
      tags: ['account', 'shipping'],
    } as AgentCard['skills'][number],
  ],
  capabilities: {
    streaming: true,
    pushNotifications: false,
    stateTransitionHistory: true,
    extensions: [
      {
        uri: 'https://github.com/google-agentic-commerce/ap2/v1',
        description: 'Supports the Agent Payments Protocol.',
        required: true,
      },
      {
        uri: 'https://sample-card-network.github.io/paymentmethod/common/types/v1',
        description:
          'Supports the Sample Card Network payment method extension',
        required: true,
      },
    ],
  },
  defaultInputModes: ['text/plain'],
  defaultOutputModes: ['application/json'],
  protocolVersion: '0.3.0',
  version: '1.0.0',
};

// Initialize the VC key manager before starting the server so
// the credentials-provider can issue and verify Verifiable Credentials.
initKeyManager().then(() => {
  bootstrapServer({
    agentCard,
    agentExecutor,
    port: 8002,
    label: 'CredentialsProvider',
  });
});
