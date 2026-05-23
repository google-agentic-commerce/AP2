/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Mandate helper tools used by shopping-agent-v2. STUBS — see header in
 * adjacent files. Names and arg shapes mirror Python `shopping_agent.mandate_tools`.
 */

import { FunctionTool } from '@google/adk';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID, createHash } from 'node:crypto';
import { z } from 'zod';

const TEMP_DB = process.env.TEMP_DB_DIR ?? '.temp-db';

function sha256Base64Url(input: string): string {
  return createHash('sha256').update(input).digest('base64url');
}

function persistMandate(filename: string, content: string): void {
  fs.mkdirSync(TEMP_DB, { recursive: true });
  fs.writeFileSync(path.join(TEMP_DB, filename), content);
}

export const assembleAndSignMandatesTool = new FunctionTool({
  name: 'assembleAndSignMandates',
  description:
    'STUB: Builds and signs the open-checkout and open-payment mandate SD-JWT chains based on the user\'s intent and constraints. Persists them under TEMP_DB and returns their IDs and hashes.',
  parameters: z.object({
    natural_language_description: z.string(),
    constraint_price_cap: z.number(),
    expires_at_iso: z.string(),
    user_cart_confirmation_required: z.boolean().optional(),
  }),
  execute: async (args) => {
    const openCheckoutId = `open_chk_${randomUUID()}`;
    const openPaymentId = `open_pay_${randomUUID()}`;
    const checkoutBody = JSON.stringify({ ...args, kind: 'open_checkout', id: openCheckoutId });
    const paymentBody = JSON.stringify({ ...args, kind: 'open_payment', id: openPaymentId });
    persistMandate(`${openCheckoutId}.sdjwt`, `stub.${Buffer.from(checkoutBody).toString('base64url')}.sig`);
    persistMandate(`${openPaymentId}.sdjwt`, `stub.${Buffer.from(paymentBody).toString('base64url')}.sig`);
    return {
      open_checkout_mandate_id: openCheckoutId,
      open_checkout_hash: sha256Base64Url(checkoutBody),
      open_payment_mandate_id: openPaymentId,
      open_payment_hash: sha256Base64Url(paymentBody),
    };
  },
});

export const checkConstraintsAgainstMandateTool = new FunctionTool({
  name: 'checkConstraintsAgainstMandate',
  description:
    'Check whether the current price + availability of an item satisfies the constraints in the open mandate.',
  parameters: z.object({
    open_checkout_mandate_id: z.string(),
    current_price: z.number(),
    available: z.boolean(),
  }),
  execute: async ({ available, current_price }) => {
    if (!available) return { satisfies: false, reason: 'item_not_available' };
    if (current_price <= 0) return { satisfies: false, reason: 'invalid_price' };
    return { satisfies: true };
  },
});

export const createCheckoutPresentationTool = new FunctionTool({
  name: 'createCheckoutPresentation',
  description: 'STUB: Build the closed-checkout mandate SD-JWT presentation from the open mandate and a concrete cart.',
  parameters: z.object({
    open_checkout_mandate_id: z.string(),
    checkout_jwt_hash: z.string(),
    cart_id: z.string(),
  }),
  execute: async (args) => {
    const id = `chk_${randomUUID()}`;
    persistMandate(`${id}.sdjwt`, `stub.${Buffer.from(JSON.stringify(args)).toString('base64url')}.sig`);
    return { checkout_mandate_chain_id: id };
  },
});

export const createPaymentPresentationTool = new FunctionTool({
  name: 'createPaymentPresentation',
  description: 'STUB: Build the closed-payment mandate SD-JWT presentation.',
  parameters: z.object({
    open_payment_mandate_id: z.string(),
    checkout_jwt_hash: z.string(),
    payment_nonce: z.string(),
  }),
  execute: async (args) => {
    const id = `pay_${randomUUID()}`;
    persistMandate(`${id}.sdjwt`, `stub.${Buffer.from(JSON.stringify(args)).toString('base64url')}.sig`);
    return { payment_mandate_chain_id: id };
  },
});

export const verifyCheckoutReceiptTool = new FunctionTool({
  name: 'verifyCheckoutReceipt',
  description: 'STUB: Verify the signed checkout receipt returned by complete_checkout.',
  parameters: z.object({
    receipt_signature: z.string().optional(),
  }),
  execute: async ({ receipt_signature }) => ({ verified: Boolean(receipt_signature) }),
});
