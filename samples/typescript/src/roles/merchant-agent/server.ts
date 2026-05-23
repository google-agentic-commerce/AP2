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

import { v4 as uuidv4 } from 'uuid';
import { Runner } from '@google/adk';
import type {
  AgentCard,
  Message,
  TaskStatusUpdateEvent,
} from '@a2a-js/sdk';

import { merchantAgent } from './agent.js';
import { sessionService } from '../../common/config/session.js';
import { BaseAgentExecutor } from '../../common/server/base-executor.js';
import { bootstrapServer } from '../../common/server/bootstrap.js';
import { DATA_KEYS } from '../../common/constants/index.js';

const runner = new Runner({
  appName: 'ap2-merchant',
  agent: merchantAgent,
  sessionService,
});

const agentExecutor = new BaseAgentExecutor({
  agentName: 'merchant_agent',
  appName: 'ap2-merchant',
  runner,
  maxLlmCalls: 5,
  workingMessage: 'The merchant is processing your request...',
  preprocessMessage({ userText, dataParts }) {
    // If PaymentMandate is present, instruct agent to call initiatePayment immediately
    const hasPaymentMandate = dataParts.some(
      (dp) => DATA_KEYS.PAYMENT_MANDATE in dp
    );
    if (hasPaymentMandate) {
      return 'A PaymentMandate is present in the data. Call the initiatePayment tool immediately.';
    }
    // If IntentMandate is present, instruct agent to call findItemsWorkflow immediately
    const hasIntentMandate = dataParts.some(
      (dp) => DATA_KEYS.INTENT_MANDATE in dp
    );
    if (hasIntentMandate) {
      return 'An IntentMandate is present in the data. Call the findItemsWorkflow tool immediately to find matching products.';
    }
    return userText;
  },
  postprocessResult({
    responseText,
    toolWasCalled,
    lastToolResult,
    eventBus,
    taskId,
    contextId,
  }) {
    // Handle payment input-required status (OTP challenge)
    if (lastToolResult?.status === 'input-required') {
      const inputRequiredMessage: Message = {
        kind: 'message',
        role: 'agent',
        messageId: uuidv4(),
        parts: [
          {
            kind: 'text',
            text: 'A payment challenge has been raised. Please provide the OTP to complete the transaction. (Hint: the code is 123)',
          },
        ],
        taskId,
        contextId,
      };

      eventBus.publish({
        kind: 'status-update',
        taskId,
        contextId,
        status: {
          state: 'input-required',
          message: inputRequiredMessage,
          timestamp: new Date().toISOString(),
        },
        final: true,
      } satisfies TaskStatusUpdateEvent);

      return null; // Signal: already handled
    }

    // If the initiatePayment tool already published a terminal status-update
    // (completed/failed) directly via eventBus, suppress the default to avoid
    // double-publishing.
    const terminalToolStates = ['completed', 'failed', 'canceled', 'rejected'];
    if (lastToolResult?.status && terminalToolStates.includes(lastToolResult.status as string)) {
      return null; // Signal: already handled by the tool
    }

    // Determine final response text
    let finalText = responseText || 'Completed.';
    if (toolWasCalled && !responseText) {
      finalText = 'Request processed successfully.';
    }

    const agentMessage: Message = {
      kind: 'message',
      role: 'agent',
      messageId: uuidv4(),
      parts: [{ kind: 'text', text: finalText }],
      taskId,
      contextId,
    };

    return {
      kind: 'status-update',
      taskId,
      contextId,
      status: {
        state: 'completed',
        message: agentMessage,
        timestamp: new Date().toISOString(),
      },
      final: true,
    } satisfies TaskStatusUpdateEvent;
  },
});

const agentCard: AgentCard = {
  name: 'MerchantAgent',
  description: 'A sales assistant agent for a merchant.',
  url: 'http://localhost:8004',
  provider: { organization: 'AP2 Demo', url: 'https://github.com/google-agentic-commerce/ap2' },
  skills: [
    {
      id: 'search_catalog',
      name: 'Search Catalog',
      description:
        "Searches the merchant's catalog based on a shopping intent & returns a cart containing the top results.",
      parameters: {
        type: 'object',
        properties: {
          shopping_intent: {
            type: 'string',
            description:
              "A JSON string representing the user's shopping intent.",
          },
        },
        required: ['shopping_intent'],
      },
      tags: ['merchant', 'search', 'catalog'],
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
  defaultInputModes: ['application/json'],
  defaultOutputModes: ['application/json'],
  protocolVersion: '0.3.0',
  version: '1.0.0',
};

bootstrapServer({
  agentCard,
  agentExecutor,
  port: 8004,
  label: 'Merchant',
});
