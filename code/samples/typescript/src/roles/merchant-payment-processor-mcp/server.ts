/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Merchant Payment Processor (PSP) MCP Server.
 *
 * Exposes one MCP tool consumed by the shopping agent v2 over stdio:
 *   initiate_payment
 *
 * NOTE: Minimum viable port. Mandate verification, token-store lookup, and
 * receipt signing are STUBBED. Tool contract mirrors the v0.2 Python server.
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { randomUUID } from 'node:crypto';
import { z } from 'zod';

const server = new McpServer({
  name: 'merchant-payment-processor-mcp',
  version: '0.2.0',
});

server.tool(
  'initiate_payment',
  {
    payment_token: z.string(),
    checkout_jwt_hash: z.string(),
    open_checkout_hash: z.string(),
  },
  async ({ payment_token, checkout_jwt_hash, open_checkout_hash }) => {
    if (!payment_token || !checkout_jwt_hash || !open_checkout_hash) {
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              error: 'missing_fields',
              message:
                'payment_token, checkout_jwt_hash, and open_checkout_hash are required',
            }),
          },
        ],
      };
    }
    // STUB: real impl looks up token, verifies mandate chain, settles payment,
    // signs receipt with PSP key, and POSTs to credentials-provider trigger.
    const receipt = `psp_receipt.${randomUUID()}.stub_sig`;
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            status: 'settled',
            payment_receipt: receipt,
            checkout_jwt_hash,
            open_checkout_hash,
            amount: 1500,
            currency: 'USD',
            timestamp: Math.floor(Date.now() / 1000),
          }),
        },
      ],
    };
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
