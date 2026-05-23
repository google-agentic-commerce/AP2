/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Shopping Agent v2 — Human-Not-Present.
 *
 * Single LlmAgent (MVP — Python has a consent/monitoring/purchase hierarchy)
 * that owns three MCP toolsets (merchant, credentials-provider, payment-processor)
 * plus the mandate helper tools. Each MCP toolset is a long-lived stdio Client
 * connected to the corresponding `*-mcp/server.ts` subprocess.
 */

import { FunctionTool, LlmAgent } from '@google/adk';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { z, type ZodTypeAny } from 'zod';

import {
  assembleAndSignMandatesTool,
  checkConstraintsAgainstMandateTool,
  createCheckoutPresentationTool,
  createPaymentPresentationTool,
  verifyCheckoutReceiptTool,
} from './mandate-tools.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROLES_DIR = path.resolve(__dirname, '..');

async function makeMcpClient(serverEntry: string): Promise<Client> {
  const transport = new StdioClientTransport({
    command: 'npx',
    args: ['tsx', serverEntry],
    env: {
      ...process.env,
      LOGS_DIR: process.env.LOGS_DIR ?? path.resolve(ROLES_DIR, '../../.logs'),
      TEMP_DB_DIR: process.env.TEMP_DB_DIR ?? path.resolve(ROLES_DIR, '../../.temp-db'),
    } as Record<string, string>,
  });
  const client = new Client({ name: 'shopping-agent-v2', version: '0.2.0' });
  await client.connect(transport);
  return client;
}

function mcpTool<S extends ZodTypeAny>(
  client: Client,
  toolName: string,
  description: string,
  parameters: S,
): FunctionTool {
  return new FunctionTool({
    name: toolName,
    description,
    parameters,
    execute: async (args: unknown) => {
      const result = (await client.callTool({
        name: toolName,
        arguments: args as Record<string, unknown>,
      })) as { content?: Array<{ type: string; text?: string }> };
      const first = result.content?.[0];
      if (first?.type === 'text' && first.text) {
        try { return JSON.parse(first.text); } catch { return first.text; }
      }
      return result;
    },
  });
}

const merchantClient = await makeMcpClient(path.join(ROLES_DIR, 'merchant-agent-mcp/server.ts'));
const credentialsClient = await makeMcpClient(path.join(ROLES_DIR, 'credentials-provider-mcp/server.ts'));
const pspClient = await makeMcpClient(path.join(ROLES_DIR, 'merchant-payment-processor-mcp/server.ts'));

const merchantTools = [
  mcpTool(
    merchantClient,
    'search_inventory',
    'Search the merchant inventory by natural-language description. Returns at most one matching product. Stock is 0 until a price-drop trigger fires.',
    z.object({
      product_description: z.string(),
      constraint_price_cap: z.number().nullable().optional(),
    }),
  ),
  mcpTool(
    merchantClient,
    'check_product',
    'Return the current price and availability of a known item_id (e.g. supershoe_size_9_0). Stock becomes >0 only after the trigger fires.',
    z.object({
      item_id: z.string(),
      constraint_price_cap: z.number().nullable().optional(),
    }),
  ),
  mcpTool(
    merchantClient,
    'assemble_cart',
    'Build a cart for the given item_id and qty after check_product reports available=true.',
    z.object({ item_id: z.string(), qty: z.number().int().positive() }),
  ),
  mcpTool(
    merchantClient,
    'create_checkout',
    'Issue an ES256-signed checkout JWT for the cart and the open checkout mandate.',
    z.object({ cart_id: z.string(), open_checkout_mandate_id: z.string() }),
  ),
  mcpTool(
    merchantClient,
    'complete_checkout',
    'Hand the issued payment credential back to the merchant to finalize the order and emit a checkout receipt.',
    z.object({ checkout_jwt: z.string(), payment_credential: z.unknown().optional() }),
  ),
];

const credentialsTools = [
  mcpTool(
    credentialsClient,
    'issue_payment_credential',
    'Verify the closed payment mandate chain and issue a scoped, single-use payment token.',
    z.object({
      payment_mandate_chain_id: z.string(),
      open_checkout_hash: z.string(),
      checkout_jwt_hash: z.string(),
      payment_nonce: z.string(),
    }),
  ),
  mcpTool(
    credentialsClient,
    'revoke_payment_credential',
    'Revoke a previously issued payment token.',
    z.object({ payment_token: z.string() }),
  ),
  mcpTool(
    credentialsClient,
    'verify_payment_receipt',
    'Verify a PSP-signed payment receipt against the issued payment token.',
    z.object({ payment_receipt: z.string() }),
  ),
];

const pspTools = [
  mcpTool(
    pspClient,
    'initiate_payment',
    'Submit a settlement request to the PSP using the issued payment token. Returns a signed payment receipt.',
    z.object({
      payment_token: z.string(),
      checkout_jwt_hash: z.string(),
      open_checkout_hash: z.string(),
    }),
  ),
];

export const shoppingAgentV2 = new LlmAgent({
  name: 'root_agent',
  model: process.env.AGENT_MODEL ?? 'gemini-2.5-flash',
  description:
    'Human-Not-Present shopping agent. Captures user intent, signs an open mandate, ' +
    'monitors merchant for price/availability, and autonomously executes the purchase ' +
    'when the constraint is satisfied.',
  instruction: `You are a Human-Not-Present shopping agent.

Flow:
1. Capture the user's intent (item, price cap, expiry). Call search_inventory once to register the item and get its item_id.
2. Call assembleAndSignMandates with the natural_language_description, constraint_price_cap, and an expires_at_iso string (1 hour from now). This produces open_checkout_mandate_id, open_payment_mandate_id, and their hashes.
3. To check current state, call check_product with the item_id from step 1.
4. Call checkConstraintsAgainstMandate with the open_checkout_mandate_id, current_price, and available. If satisfies = false, tell the user you'll keep watching and stop.
5. When satisfies = true, execute the autonomous purchase:
   a. assemble_cart(item_id, qty=1)
   b. create_checkout(cart_id, open_checkout_mandate_id)
   c. createCheckoutPresentation, createPaymentPresentation
   d. issue_payment_credential(payment_mandate_chain_id, open_checkout_hash, checkout_jwt_hash, payment_nonce — generate a random nonce)
   e. initiate_payment(payment_token, checkout_jwt_hash, open_checkout_hash)
   f. complete_checkout(checkout_jwt, payment_credential)
   g. verify_payment_receipt, verifyCheckoutReceipt
6. Surface a brief receipt summary to the user.

If a tool returns an object with an "error" key, STOP and return the error verbatim.`,
  tools: [
    assembleAndSignMandatesTool,
    checkConstraintsAgainstMandateTool,
    createCheckoutPresentationTool,
    createPaymentPresentationTool,
    verifyCheckoutReceiptTool,
    ...merchantTools,
    ...credentialsTools,
    ...pspTools,
  ],
});

export { shoppingAgentV2 as rootAgent };
