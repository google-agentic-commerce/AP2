/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Credential Provider MCP Server.
 *
 * Exposes three MCP tools consumed by the shopping agent v2 over stdio:
 *   issue_payment_credential, revoke_payment_credential, verify_payment_receipt
 *
 * NOTE: Minimum viable port. SD-JWT mandate-chain verification is STUBBED.
 * Tool names/args/response shapes mirror the v0.2 Python server.
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { randomUUID } from 'node:crypto';
import { z } from 'zod';

const TOKEN_STORE = new Map<string, { issued_at: number; expires_at: number }>();

const server = new McpServer({
  name: 'credentials-provider-mcp',
  version: '0.2.0',
});

server.tool(
  'issue_payment_credential',
  {
    payment_mandate_chain_id: z.string(),
    open_checkout_hash: z.string(),
    checkout_jwt_hash: z.string(),
    payment_nonce: z.string(),
  },
  async ({ payment_mandate_chain_id, open_checkout_hash, checkout_jwt_hash, payment_nonce }) => {
    if (!payment_mandate_chain_id || !open_checkout_hash || !checkout_jwt_hash || !payment_nonce) {
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              error: 'missing_fields',
              message: 'payment_mandate_chain_id, open_checkout_hash, checkout_jwt_hash, payment_nonce are required',
            }),
          },
        ],
      };
    }
    // STUB: real impl loads the sdjwt chain, verifies signatures and chain integrity,
    // then issues a scoped single-use token.
    const token = `pay_token_${randomUUID()}`;
    const issuedAt = Math.floor(Date.now() / 1000);
    const expiresAt = issuedAt + 600;
    TOKEN_STORE.set(token, { issued_at: issuedAt, expires_at: expiresAt });
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({ payment_token: token, expires_at: expiresAt }),
        },
      ],
    };
  },
);

server.tool(
  'revoke_payment_credential',
  { payment_token: z.string() },
  async ({ payment_token }) => {
    const existed = TOKEN_STORE.delete(payment_token);
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({ revoked: existed, payment_token }),
        },
      ],
    };
  },
);

server.tool(
  'verify_payment_receipt',
  { payment_receipt: z.string() },
  async ({ payment_receipt }) => {
    // STUB: real impl verifies the receipt's signature against the PSP key
    // and that it matches a prior issued payment_token.
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            verified: true,
            receipt_prefix: payment_receipt.slice(0, 20),
          }),
        },
      ],
    };
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
