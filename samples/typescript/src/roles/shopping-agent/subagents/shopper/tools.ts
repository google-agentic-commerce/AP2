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
  Artifact,
  DataPart,
  MessageSendParams,
  SendMessageSuccessResponse,
  Task,
} from '@a2a-js/sdk';
import { AGENT_URLS } from '../../../index.js';
import { DATA_KEYS } from '../../../../common/constants/index.js';

const INTENT_MANDATE_DATA_KEY = DATA_KEYS.INTENT_MANDATE;
const CART_MANDATE_DATA_KEY = DATA_KEYS.CART_MANDATE;

// Helper functions
function parseCartMandates(artifacts: Artifact[]): Record<string, unknown>[] {
  const cartMandates: Record<string, unknown>[] = [];

  for (const artifact of artifacts) {
    for (const part of artifact.parts) {
      if (part.kind === 'data') {
        const dataPart = part as DataPart;
        const data = dataPart.data as Record<string, unknown>;
        if (CART_MANDATE_DATA_KEY in data) {
          cartMandates.push(
            data[CART_MANDATE_DATA_KEY] as Record<string, unknown>
          );
        }
      }
    }
  }

  return cartMandates;
}

function collectRiskData(): { riskData: string } {
  return {
    riskData: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...fake_risk_data',
  };
}

/**
 * Tool 1: Create Intent Mandate
 *
 * Creates an IntentMandate with the user's shopping intent.
 */
export const createIntentMandate = new FunctionTool({
  name: 'create_intent_mandate',
  description: 'Create an IntentMandate with the user\'s shopping intent and preferences.',
  parameters: z.object({
    naturalLanguageDescription: z
      .string()
      .describe('The description of the user\'s intent.'),
    userCartConfirmationRequired: z
      .boolean()
      .describe('If the user must confirm the cart.'),
    merchants: z.array(z.string()).describe('A list of allowed merchants.'),
    skus: z.array(z.string()).describe('A list of allowed SKUs.'),
    requiresRefundability: z
      .boolean()
      .describe('If the items must be refundable.'),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error('Missing execution context');
    const {
      naturalLanguageDescription,
      userCartConfirmationRequired,
      merchants,
      skus,
      requiresRefundability,
    } = input;

    const intentMandate = {
      naturalLanguageDescription,
      userCartConfirmationRequired,
      merchants,
      skus,
      requiresRefundability,
      intentExpiry: new Date(Date.now() + 1000 * 60 * 60 * 24).toISOString(),
    };

    // Store in session state
    context.state.set('intentMandate', intentMandate);

    return intentMandate;
  },
});

/**
 * Tool 2: Find Products
 *
 * Calls the merchant agent to find products matching the user's intent.
 */
export const findProducts = new FunctionTool({
  name: 'find_products',
  description: 'Calls the merchant agent to find products matching the user\'s intent.',
  parameters: z.object({
    debugMode: z
      .boolean()
      .optional()
      .default(false)
      .describe('If the agent is in debug mode.'),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error('Missing execution context');
    const intentMandate = context.state.get('intentMandate');
    if (!intentMandate) {
      throw new Error('No IntentMandate found in session state.');
    }

    const riskData = collectRiskData();
    if (!riskData) {
      throw new Error('No risk data available.');
    }

    const client = await A2AClient.fromCardUrl(AGENT_URLS.MERCHANT);
    const sendParams: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: 'user',
        parts: [
          {
            kind: 'text',
            text: 'Find products that match the user\'s IntentMandate.',
          },
          {
            kind: 'data',
            data: {
              [INTENT_MANDATE_DATA_KEY]: intentMandate,
            },
          },
          {
            kind: 'data',
            data: {
              risk_data: riskData.riskData,
            },
          },
          {
            kind: 'data',
            data: {
              debug_mode: input.debugMode,
            },
          },
          {
            kind: 'data',
            data: {
              shopping_agent_id: 'trusted_shopping_agent',
            },
          },
        ],
        kind: 'message',
      },
    };

    const response = await client.sendMessage(sendParams);

    if ('error' in response) {
      console.error('Error:', response.error.message);
      throw new Error(response.error.message);
    }

    const result = (response as SendMessageSuccessResponse).result;
    if (result.kind === 'task') {
      const task = result as Task;
      if (task.status.state !== 'completed') {
        throw new Error(`Failed to find products: ${JSON.stringify(task.status)}`);
      }

      const cartMandates = parseCartMandates(task.artifacts ?? []);

      // Store in session state
      context.state.set('shoppingContextId', task.contextId);
      context.state.set('cartMandates', cartMandates);
      context.state.set('riskData', riskData.riskData);

      return { cartMandates };
    }

    throw new Error('Unexpected response type from merchant agent');
  },
});

/**
 * Tool 3: Update Chosen Cart Mandate
 *
 * Updates the chosen CartMandate in the session state.
 */
export const updateChosenCartMandate = new FunctionTool({
  name: 'update_chosen_cart_mandate',
  description: 'Updates the chosen CartMandate in the session state. Use the cart ID (contents.id) from the CartMandate the user selected.',
  parameters: z.object({
    cartId: z
      .string()
      .describe('The cart ID (contents.id) of the CartMandate the user selected.'),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error('Missing execution context');
    const { cartId } = input;
    const cartMandates = context.state.get('cartMandates') as Record<string, unknown>[] || [];

    if (cartMandates.length === 0) {
      return 'No products available. Please search for products first.';
    }

    const selectedCart = cartMandates.find((cm) => {
      const contents = cm.contents as Record<string, unknown> | undefined;
      return contents?.id === cartId;
    });

    if (!selectedCart) {
      return `Cart with ID "${cartId}" not found. Please choose a valid cart ID.`;
    }

    // Store in session state
    context.state.set('chosenCartId', cartId);
    context.state.set('cartMandate', selectedCart);

    return `Cart ${cartId} selected successfully.`;
  },
});
