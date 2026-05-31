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
 * Settles the payment and signs a real ES256 payment receipt with the PSP key
 * (the same receipt the PSP trigger server produces). Token-store lookup is
 * still simplified. Tool contract mirrors the v0.2 Python server.
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { randomUUID } from 'node:crypto';
import { z } from 'zod';
import { signJwtEs256, loadOrCreateKeyPair } from '../../common/sdjwt/index.js';

const TEMP_DB = process.env.TEMP_DB_DIR ?? '.temp-db';

const server = new McpServer({
  name: 'merchant-payment-processor-mcp',
  version: '0.2.0',
});

server.registerTool(
  'initiate_payment',
  {
    description:
      'Initiate and settle a payment for a previously issued payment token, bound to ' +
      'the checkout-JWT and open-checkout hashes, returning a (stubbed) signed PSP receipt.',
    inputSchema: {
      payment_token: z.string(),
      checkout_jwt_hash: z.string(),
      open_checkout_hash: z.string(),
    },
  },
  async ({ payment_token, checkout_jwt_hash, open_checkout_hash }) => {
    if (!payment_token || !checkout_jwt_hash || !open_checkout_hash) {
      const error = {
        error: 'missing_fields',
        message:
          'payment_token, checkout_jwt_hash, and open_checkout_hash are required',
      };
      return {
        content: [{ type: 'text', text: JSON.stringify(error) }],
        structuredContent: error,
        isError: true,
      };
    }
    // Settle and sign a real ES256 payment receipt with the PSP key.
    const psp = await loadOrCreateKeyPair(TEMP_DB, 'psp');
    const receipt = await signJwtEs256(
      {
        iss: 'merchant-payment-processor',
        receipt_id: randomUUID(),
        iat: Math.floor(Date.now() / 1000),
        checkout_jwt_hash,
        open_checkout_hash,
        payment_token,
        status: 'settled',
      },
      psp.privateKey,
    );
    const result = {
      status: 'settled',
      payment_receipt: receipt,
      checkout_jwt_hash,
      open_checkout_hash,
      amount: 1500,
      currency: 'USD',
      timestamp: Math.floor(Date.now() / 1000),
    };
    return {
      content: [{ type: 'text', text: JSON.stringify(result) }],
      structuredContent: result,
    };
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
