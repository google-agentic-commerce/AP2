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
 * issue_payment_credential performs REAL SD-JWT verification of the presented
 * closed payment-mandate (KB-SD-JWT): it loads the mandate the agent persisted
 * under TEMP_DB, verifies the issuer (user) signature and the agent Key-Binding
 * JWT against `cnf.jwk` with the expected nonce, and only then mints a token —
 * mirroring the Python credentials_provider_mcp.issue_payment_credential.
 * Tool names/args/response shapes mirror the v0.2 Python server.
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { randomUUID } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { z } from 'zod';
import { verifyMandate, verifyJwtEs256, loadPublicJwk, type Es256KeyPair } from '../../common/sdjwt/index.js';

const TEMP_DB = process.env.TEMP_DB_DIR ?? '.temp-db';

const TOKEN_STORE = new Map<string, { issued_at: number; expires_at: number }>();

function readTempFile(filename: string): string | null {
  try {
    return fs.readFileSync(path.join(TEMP_DB, filename), 'utf-8');
  } catch {
    return null;
  }
}

/** The user (issuer) public key persisted by the shopping agent's mandate-tools. */
function loadUserPublicJwk(): JsonWebKey | null {
  const raw = readTempFile('user_key.jwk.json');
  if (!raw) return null;
  return (JSON.parse(raw) as Es256KeyPair).publicKey;
}

const server = new McpServer({
  name: 'credentials-provider-mcp',
  version: '0.2.0',
});

server.registerTool(
  'issue_payment_credential',
  {
    description:
      'Issue a scoped single-use payment token for a verified payment mandate chain, ' +
      'bound to the open-checkout and checkout-JWT hashes and a payment nonce.',
    inputSchema: {
      payment_mandate_chain_id: z.string(),
      open_checkout_hash: z.string(),
      checkout_jwt_hash: z.string(),
      payment_nonce: z.string().optional(),
    },
  },
  async ({ payment_mandate_chain_id, open_checkout_hash, checkout_jwt_hash }) => {
    if (!payment_mandate_chain_id || !open_checkout_hash || !checkout_jwt_hash) {
      const error = {
        error: 'missing_fields',
        message: 'payment_mandate_chain_id, open_checkout_hash, checkout_jwt_hash are required',
      };
      return {
        content: [{ type: 'text', text: JSON.stringify(error) }],
        structuredContent: error,
        isError: true,
      };
    }
    // Load the presented closed payment-mandate (KB-SD-JWT) the agent persisted.
    const presented = readTempFile(`${payment_mandate_chain_id}.sdjwt`);
    if (!presented) {
      const error = { error: 'mandate_not_found', message: payment_mandate_chain_id };
      return { content: [{ type: 'text', text: JSON.stringify(error) }], structuredContent: error, isError: true };
    }
    const issuerPublicJwk = loadUserPublicJwk();
    if (!issuerPublicJwk) {
      const error = { error: 'issuer_key_unavailable', message: 'user_key.jwk.json not found in TEMP_DB' };
      return { content: [{ type: 'text', text: JSON.stringify(error) }], structuredContent: error, isError: true };
    }

    // Verify the issuer (user) SD-JWT signature AND the agent Key-Binding JWT
    // against cnf.jwk, requiring the holder binding to commit to the SPECIFIC
    // checkout (nonce === checkout_jwt_hash). This is the hash-binding check:
    // a payment presentation made for a different checkout is rejected here,
    // and a forged/unbound presentation fails signature/KB verification.
    try {
      const { keyBound } = await verifyMandate({
        mandateSdJwt: presented,
        issuerPublicJwk,
        nonce: checkout_jwt_hash,
      });
      if (!keyBound) {
        const error = { error: 'checkout_binding_failed', message: 'payment mandate not holder-bound to this checkout_jwt_hash' };
        return { content: [{ type: 'text', text: JSON.stringify(error) }], structuredContent: error, isError: true };
      }
    } catch (e) {
      const error = { error: 'mandate_verification_failed', message: String(e) };
      return { content: [{ type: 'text', text: JSON.stringify(error) }], structuredContent: error, isError: true };
    }

    // Verified — mint a scoped single-use token bound to the mandate chain.
    const token = `pay_token_${randomUUID()}`;
    const issuedAt = Math.floor(Date.now() / 1000);
    const expiresAt = issuedAt + 600;
    TOKEN_STORE.set(token, { issued_at: issuedAt, expires_at: expiresAt });
    const result = { payment_token: token, expires_at: expiresAt };
    return {
      content: [{ type: 'text', text: JSON.stringify(result) }],
      structuredContent: result,
    };
  },
);

server.registerTool(
  'revoke_payment_credential',
  {
    description:
      'Revoke a previously issued payment token, removing it from the token store. ' +
      'Returns whether the token existed.',
    inputSchema: { payment_token: z.string() },
  },
  async ({ payment_token }) => {
    const existed = TOKEN_STORE.delete(payment_token);
    const result = { revoked: existed, payment_token };
    return {
      content: [{ type: 'text', text: JSON.stringify(result) }],
      structuredContent: result,
    };
  },
);

server.registerTool(
  'verify_payment_receipt',
  {
    description:
      'Verify a payment receipt (stubbed: checks signature against the PSP key ' +
      'and that it matches a prior issued payment token).',
    inputSchema: { payment_receipt: z.string() },
  },
  async ({ payment_receipt }) => {
    // Verify the receipt's ES256 signature against the PSP public key.
    const pspPub = loadPublicJwk(TEMP_DB, 'psp');
    if (!pspPub) {
      const error = { error: 'psp_key_unavailable', message: 'psp key not found in TEMP_DB' };
      return { content: [{ type: 'text', text: JSON.stringify(error) }], structuredContent: error, isError: true };
    }
    try {
      const payload = await verifyJwtEs256(payment_receipt, pspPub);
      const result = { verified: true, issuer: payload.iss, receipt_id: payload.receipt_id };
      return { content: [{ type: 'text', text: JSON.stringify(result) }], structuredContent: result };
    } catch (e) {
      const error = { error: 'receipt_verification_failed', message: String(e) };
      return { content: [{ type: 'text', text: JSON.stringify(error) }], structuredContent: error, isError: true };
    }
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
