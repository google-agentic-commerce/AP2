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

import { FunctionTool } from '@google/adk';
import { z } from 'zod';
import { v4 as uuidv4 } from 'uuid';
import { A2AClient } from '@a2a-js/sdk/client';
import type {
  MessageSendParams,
  SendMessageSuccessResponse,
  Task,
  TaskArtifactUpdateEvent,
  TaskStatusUpdateEvent,
} from '@a2a-js/sdk';
import { findDataPart, parseCanonicalObject } from '../../common/utils/message.js';
import { getA2AContextFromTool } from '../../common/server/a2a-context.js';
import type { PaymentItem } from '../../common/types/payment-item.js';
import type { CartMandate } from '../../common/types/cart-mandate.js';
import type { IntentMandate } from '../../common/types/intent-mandate.js';
import type { PaymentMandate } from '../../common/types/payment-mandate.js';
import { intentMandateSchema } from '../../common/schemas/intent-mandate.js';
import { paymentMandateSchema } from '../../common/schemas/payment-mandate.js';
import { getCartMandate, getRiskData, setCartMandate, setRiskData } from './storage.js';
import { GoogleGenAI } from '@google/genai';
import { AGENT_URLS } from '../index.js';
import { DATA_KEYS } from '../../common/constants/index.js';

/** Known shopping agent IDs allowed to interact with this merchant. */
const KNOWN_SHOPPING_AGENTS = new Set(['trusted_shopping_agent']);

const FAKE_JWT = 'eyJhbGciOiJSUzI1NiIsImtpZIwMjQwOTA...';
const INTENT_MANDATE_DATA_KEY = DATA_KEYS.INTENT_MANDATE;
const CART_MANDATE_DATA_KEY = DATA_KEYS.CART_MANDATE;
const PAYMENT_MANDATE_DATA_KEY = DATA_KEYS.PAYMENT_MANDATE;

const PAYMENT_PROCESSORS_BY_PAYMENT_METHOD_TYPE: Record<string, string> = {
  CARD: AGENT_URLS.PAYMENT_PROCESSOR,
  'https://www.x402.org/': AGENT_URLS.PAYMENT_PROCESSOR,
};

// Lazy initialization of Gemini for product generation
function getGenAI() {
  const apiKey = process.env.GOOGLE_GENAI_API_KEY || process.env.GEMINI_API_KEY;
  if (!apiKey) {
    throw new Error('GOOGLE_GENAI_API_KEY or GEMINI_API_KEY environment variable is required for product generation');
  }
  return new GoogleGenAI({ apiKey });
}

// Helper functions
function getPaymentProcessorTaskId(task: Task | undefined): string | null {
  if (!task || !task.history) {
    return null;
  }

  for (const message of task.history) {
    if (message.taskId && message.taskId !== task.id) {
      return message.taskId;
    }
  }

  return null;
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Tool 1: Find Items Workflow
 *
 * Generates products matching the user's IntentMandate using Gemini.
 */
export const findItemsWorkflow = new FunctionTool({
  name: 'findItemsWorkflow',
  description: "Finds products that match the user's IntentMandate by generating realistic product recommendations. Pass the user's shopping intent description.",
  parameters: z.object({
    _trigger: z.boolean().optional().describe('Tool trigger'),
    intentDescription: z.string().optional().describe("The user's shopping intent description (used in ADK dev mode when no A2A data parts are available)."),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error('Missing execution context');
    const { dataParts, eventBus, currentTask } = getA2AContextFromTool(context);

    const taskId = currentTask?.id || uuidv4();
    const contextId = currentTask?.contextId || uuidv4();

    // Validate shopping agent ID
    const shoppingAgentId = findDataPart('shopping_agent_id', dataParts) as string | null;
    if (shoppingAgentId && !KNOWN_SHOPPING_AGENTS.has(shoppingAgentId)) {
      return { error: `Unknown shopping agent: ${shoppingAgentId}. Report this error to the caller.` };
    }

    // Parse IntentMandate from A2A data parts, or fall back to direct parameter
    let intent: string;
    try {
      const intentMandate = parseCanonicalObject<IntentMandate>(
        INTENT_MANDATE_DATA_KEY,
        dataParts,
        intentMandateSchema
      );
      intent = intentMandate.naturalLanguageDescription;
    } catch {
      // ADK dev mode fallback: use the intent description parameter directly
      if (input.intentDescription) {
        intent = input.intentDescription;
      } else {
        return { error: 'IntentMandate not found in request data and no intentDescription provided. Report this error to the caller.' };
      }
    }

    // Generate products using Gemini
    const genAI = getGenAI();

    const prompt = `Based on the user's request for '${intent}', generate 3 complete, unique and realistic PaymentItem JSON objects.

You MUST exclude all branding from the PaymentItem label field.

Generate realistic, diverse product data with reasonable prices and details.

Return a JSON array where each object has: label (string), amount (object with currency string and value number), and refundPeriod (number in days).`;

    // Retry mechanism
    const maxRetries = 3;
    const retryDelay = 1000;
    let items: PaymentItem[] = [];

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        const result = await genAI.models.generateContent({
          model: 'gemini-2.5-flash',
          contents: prompt,
          config: {
            responseMimeType: 'application/json',
          },
        });
        const text = result.text ?? '';
        items = JSON.parse(text) as PaymentItem[];
        break;
      } catch (error) {
        if (attempt === maxRetries - 1) {
          return { error: `Unable to generate products after ${maxRetries} attempts: ${error instanceof Error ? error.message : String(error)}. Report this error to the caller.` };
        }
        await sleep(retryDelay * (attempt + 1));
      }
    }

    if (!items || items.length === 0) {
      return { error: 'No products were generated. Report this error to the caller.' };
    }

    // Create cart mandates for each item
    const currentTime = new Date();
    let itemCount = 0;

    for (const item of items) {
      itemCount++;
      const cartExpiryTime = new Date(currentTime.getTime() + 30 * 60 * 1000);

      const cartMandate: CartMandate = {
        contents: {
          id: `cart_${itemCount}`,
          userCartConfirmationRequired: true,
          paymentRequest: {
            methodData: [
              {
                supportedMethods: 'CARD',
                data: {
                  network: ['mastercard', 'paypal', 'amex'],
                },
              },
            ],
            details: {
              id: `order_${itemCount}`,
              displayItems: [item],
              shippingOptions: [],
              modifiers: [],
              total: {
                label: 'Total',
                amount: item.amount,
                pending: false,
                refundPeriod: item.refundPeriod,
              },
            },
            options: {
              requestShipping: true,
            },
          },
          cartExpiry: cartExpiryTime.toISOString(),
          merchantName: 'Generic Merchant',
        },
      };

      setCartMandate(cartMandate.contents.id, cartMandate);

      const artifactUpdate: TaskArtifactUpdateEvent = {
        kind: 'artifact-update',
        taskId,
        contextId,
        artifact: {
          artifactId: uuidv4(),
          parts: [
            {
              kind: 'data',
              data: {
                [CART_MANDATE_DATA_KEY]: cartMandate,
              },
            },
          ],
        },
      };

      eventBus.publish(artifactUpdate);
    }

    // Add risk data
    const riskData = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...fake_risk_data';
    setRiskData(contextId, riskData);

    const riskDataArtifact: TaskArtifactUpdateEvent = {
      kind: 'artifact-update',
      taskId,
      contextId,
      artifact: {
        artifactId: uuidv4(),
        parts: [
          {
            kind: 'data',
            data: { risk_data: riskData },
          },
        ],
      },
    };
    eventBus.publish(riskDataArtifact);

    return { status: 'success', itemCount };
  },
});

/**
 * Tool 2: Update Cart
 *
 * Updates cart with shipping address and adds tax/shipping costs.
 */
export const updateCart = new FunctionTool({
  name: 'updateCart',
  description: 'Updates an existing cart after a shipping address is provided.',
  parameters: z.object({
    _trigger: z.boolean().optional().describe('Tool trigger'),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error('Missing execution context');
    const { dataParts, eventBus, currentTask } = getA2AContextFromTool(context);

    const cartId = findDataPart('cart_id', dataParts) as string | null;
    if (!cartId) {
      return { error: 'Missing cart_id in request data. Report this error to the caller.' };
    }

    const shippingAddress = findDataPart(
      'shipping_address',
      dataParts
    ) as Record<string, unknown> | null;
    if (!shippingAddress) {
      return { error: 'Missing shipping address in request data. Report this error to the caller.' };
    }

    const cartMandate = getCartMandate(cartId);
    if (!cartMandate) {
      return { error: `CartMandate not found for cart_id: ${cartId}. Report this error to the caller.` };
    }

    const riskData = getRiskData(currentTask.contextId);
    if (!riskData) {
      return { error: `Missing risk_data for context_id: ${currentTask.contextId}. Report this error to the caller.` };
    }

    // Cast shipping address from A2A data parts to the expected schema type
    cartMandate.contents.paymentRequest.shippingAddress = shippingAddress as typeof cartMandate.contents.paymentRequest.shippingAddress;

    const taxAndShippingCosts: PaymentItem[] = [
      {
        label: 'Shipping',
        amount: {
          currency: 'USD',
          value: 2.0,
        },
        refundPeriod: 30,
      },
      {
        label: 'Tax',
        amount: {
          currency: 'USD',
          value: 1.5,
        },
        refundPeriod: 30,
      },
    ];

    const paymentRequest = cartMandate.contents.paymentRequest;

    if (!paymentRequest.details.displayItems) {
      paymentRequest.details.displayItems = taxAndShippingCosts;
    } else {
      paymentRequest.details.displayItems.push(...taxAndShippingCosts);
    }

    paymentRequest.details.total.amount.value =
      paymentRequest.details.displayItems.reduce(
        (acc, curr) => acc + curr.amount.value,
        0
      );

    cartMandate.merchantAuthorization = FAKE_JWT;

    const artifactUpdate: TaskArtifactUpdateEvent = {
      kind: 'artifact-update',
      taskId: currentTask.id,
      contextId: currentTask.contextId,
      artifact: {
        artifactId: uuidv4(),
        parts: [
          {
            kind: 'data',
            data: {
              [CART_MANDATE_DATA_KEY]: cartMandate,
            },
          },
          {
            kind: 'data',
            data: {
              risk_data: riskData,
            },
          },
        ],
      },
    };

    eventBus.publish(artifactUpdate);

    return { status: 'success', cartMandate };
  },
});

/**
 * Tool 3: Initiate Payment
 *
 * Delegates payment processing to the payment processor agent.
 */
export const initiatePayment = new FunctionTool({
  name: 'initiatePayment',
  description: 'Initiates a payment for a given payment mandate by delegating to the payment processor.',
  parameters: z.object({
    _trigger: z.boolean().optional().describe('Tool trigger'),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error('Missing execution context');
    const { dataParts, eventBus, currentTask } = getA2AContextFromTool(context);

    let paymentMandate: PaymentMandate;
    try {
      paymentMandate = parseCanonicalObject<PaymentMandate>(
        PAYMENT_MANDATE_DATA_KEY,
        dataParts,
        paymentMandateSchema
      );
    } catch {
      return { error: 'PaymentMandate not found in request data. Report this error to the caller.' };
    }

    const riskData = findDataPart('risk_data', dataParts) as string | null;
    if (!riskData) {
      return { error: 'Missing risk_data in request data. Report this error to the caller.' };
    }

    const paymentMethodType =
      paymentMandate.paymentMandateContents.paymentResponse.methodName;

    const processorUrl =
      PAYMENT_PROCESSORS_BY_PAYMENT_METHOD_TYPE[paymentMethodType];

    if (!processorUrl) {
      return { error: `No payment processor found for method: ${paymentMethodType}. Report this error to the caller.` };
    }

    const client = await A2AClient.fromCardUrl(processorUrl);

    const message: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: 'user',
        contextId: currentTask.contextId,
        parts: [
          {
            kind: 'text',
            text: 'Call the initiatePayment tool to process this payment. The payment mandate and risk data are provided in the data parts of this message.',
          },
          {
            kind: 'data',
            data: {
              [PAYMENT_MANDATE_DATA_KEY]: paymentMandate,
            },
          },
          {
            kind: 'data',
            data: {
              risk_data: riskData,
            },
          },
        ],
        kind: 'message',
      },
    };

    const challengeResponse = findDataPart('challenge_response', dataParts) as
      | string
      | null;
    if (challengeResponse) {
      message.message.parts.push({
        kind: 'data',
        data: { challenge_response: challengeResponse },
      });
    }

    const paymentProcessorTaskId = getPaymentProcessorTaskId(currentTask);
    if (paymentProcessorTaskId) {
      message.message.taskId = paymentProcessorTaskId;
    }

    const response = await client.sendMessage(message);

    if ('error' in response) {
      return { error: `Payment processor error: ${response.error.message}. Report this error to the caller.` };
    }

    const result = (response as SendMessageSuccessResponse).result;
    if (result.kind === 'task') {
      const task = result as Task;

      // Forward PaymentReceipt artifacts from payment processor to shopping agent
      for (const artifact of task.artifacts ?? []) {
        for (const part of artifact.parts) {
          if (part.kind === 'data') {
            const data = (part as { kind: 'data'; data: Record<string, unknown> }).data;
            if (data[DATA_KEYS.PAYMENT_RECEIPT]) {
              const receiptArtifact: TaskArtifactUpdateEvent = {
                kind: 'artifact-update',
                taskId: currentTask.id,
                contextId: currentTask.contextId,
                artifact: {
                  artifactId: uuidv4(),
                  parts: [{ kind: 'data', data: { [DATA_KEYS.PAYMENT_RECEIPT]: data[DATA_KEYS.PAYMENT_RECEIPT] } }],
                },
              };
              eventBus.publish(receiptArtifact);
            }
          }
        }
      }

      const statusUpdate: TaskStatusUpdateEvent = {
        kind: 'status-update',
        taskId: currentTask.id,
        contextId: currentTask.contextId,
        status: {
          state: task.status.state,
          message: task.status.message,
          timestamp: new Date().toISOString(),
        },
        final: false,
      };

      const terminalStates = ['completed', 'failed', 'canceled', 'rejected'];
      if (terminalStates.includes(task.status.state)) {
        statusUpdate.final = true;
      }

      eventBus.publish(statusUpdate);

      return {
        status: task.status.state,
        taskId: task.id,
      };
    }

    return { error: 'Unexpected response type from payment processor. Report this error to the caller.' };
  },
});

/**
 * Tool 4: DPC Finish
 *
 * Receives and validates DPC response to finalize payment.
 */
export const dpcFinish = new FunctionTool({
  name: 'dpcFinish',
  description: 'Receives and validates a DPC response to finalize payment. This receives the Digital Payment Credential (DPC) response and simulates payment finalization.',
  parameters: z.object({
    _trigger: z.boolean().optional().describe('Tool trigger'),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error('Missing execution context');
    const { dataParts, eventBus, currentTask } = getA2AContextFromTool(context);

    const dpcResponse = findDataPart('dpc_response', dataParts) as Record<
      string,
      unknown
    > | null;
    if (!dpcResponse) {
      return { error: 'Missing dpc_response in request data. Report this error to the caller.' };
    }

    const artifactUpdate: TaskArtifactUpdateEvent = {
      kind: 'artifact-update',
      taskId: currentTask.id,
      contextId: currentTask.contextId,
      artifact: {
        artifactId: uuidv4(),
        parts: [
          {
            kind: 'data',
            data: { paymentStatus: 'SUCCESS', transactionId: 'txn_1234567890' },
          },
        ],
      },
    };
    eventBus.publish(artifactUpdate);

    return { status: 'success' };
  },
});
