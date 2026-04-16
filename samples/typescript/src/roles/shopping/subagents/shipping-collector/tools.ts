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
  MessageSendParams,
  SendMessageSuccessResponse,
  Task,
} from '@a2a-js/sdk';
import { AGENT_URLS } from '../../../index.js';

// Helper function
function parseShippingAddress(artifacts: Artifact[]): unknown[] {
  return artifacts.map((artifact) => {
    const dataPart = artifact.parts.find((part) => part.kind === 'data');
    return dataPart ? (dataPart as { kind: 'data'; data: unknown }).data : undefined;
  });
}

/**
 * Tool: Get Shipping Address
 *
 * Gets the user's shipping address from the credentials provider.
 */
export const getShippingAddress = new FunctionTool({
  name: 'get_shipping_address',
  description: 'Gets the user\'s shipping address from the credentials provider.',
  parameters: z.object({
    userEmail: z.string().describe('The user\'s email address'),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error('Missing execution context');
    const shoppingContextId = context.state.get('shoppingContextId') as string | undefined;

    const sendParams: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: 'user',
        contextId: shoppingContextId || uuidv4(),
        parts: [
          {
            kind: 'text',
            text: 'Get the user\'s shipping address.',
          },
          {
            kind: 'data',
            data: {
              user_email: input.userEmail,
            },
          },
        ],
        kind: 'message',
      },
    };

    const client = await A2AClient.fromCardUrl(AGENT_URLS.CREDENTIALS_PROVIDER);
    const response = await client.sendMessage(sendParams);

    if ('error' in response) {
      throw new Error(response.error.message);
    }

    const result = (response as SendMessageSuccessResponse).result;
    if (result.kind === 'task') {
      const task = result as Task;
      if (task.status.state !== 'completed') {
        throw new Error(
          `Failed to get shipping address: ${task.status.state}`
        );
      }

      const shippingAddress = parseShippingAddress(task.artifacts ?? [])?.[0];

      // Store in session state
      context.state.set('shippingAddress', shippingAddress);
      context.state.set('userEmail', input.userEmail);

      return shippingAddress;
    }

    throw new Error('Unexpected response type from credentials provider');
  },
});

/**
 * Tool: Save Manual Shipping Address
 *
 * Saves a manually entered shipping address to session state so that
 * postprocessResult can publish it as an artifact.
 */
export const saveManualShippingAddress = new FunctionTool({
  name: 'save_manual_shipping_address',
  description: 'Saves a manually entered shipping address. Call this after the user provides their full address.',
  parameters: z.object({
    recipient: z.string().describe('Full name of the recipient'),
    address_line: z.array(z.string()).describe('Street address lines'),
    city: z.string().describe('City'),
    region: z.string().describe('State or region'),
    postal_code: z.string().describe('Zip or postal code'),
    country: z.string().describe('Country code (e.g. US)'),
    phone_number: z.string().optional().describe('Phone number'),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error('Missing execution context');
    const shippingAddress = {
      recipient: input.recipient,
      address_line: input.address_line,
      city: input.city,
      region: input.region,
      postal_code: input.postal_code,
      country: input.country,
      phone_number: input.phone_number || '',
    };
    context.state.set('shippingAddress', shippingAddress);
    return shippingAddress;
  },
});
