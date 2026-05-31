/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Mandate helper tools used by shopping-agent-v2, backed by real SD-JWT
 * (src/common/sdjwt, @sd-jwt/core + ES256):
 *   - assembleAndSignMandates: issues open-checkout + open-payment SD-JWTs with
 *     a cnf.jwk agent key (RFC 7800). Constraints (price cap, merchant
 *     allowlist) are carried as claims so they can be verified later.
 *   - checkConstraintsAgainstMandate: verifies the open mandate and checks the
 *     observed price/merchant against its constraints (real, not a stub).
 *   - createCheckout/PaymentPresentation: KB-SD-JWT presentations whose holder
 *     binding commits to the checkout_jwt_hash (so a presentation cannot be
 *     replayed against a different checkout).
 *   - verifyCheckoutReceipt: verifies a presented mandate's signature + KB.
 *   - resetTempDb: clears mandate files for a fresh run, preserving keys.
 *
 * Names mirror Python `shopping_agent.mandate_tools`.
 */

import { FunctionTool } from '@google/adk';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID, createHash } from 'node:crypto';
import { z } from 'zod';

import {
  issueOpenMandate,
  presentClosedMandate,
  verifyMandate,
  loadOrCreateKeyPair,
  checkConstraints,
} from '../../common/sdjwt/index.js';

const TEMP_DB = process.env.TEMP_DB_DIR ?? '.temp-db';
const CREDENTIAL_PROVIDER_AUD = 'credentials-provider';

/** Mandate file prefixes — cleared by resetTempDb, never the *_key.jwk.json keys. */
const MANDATE_PREFIXES = ['open_chk_', 'open_pay_', 'chk_', 'pay_'];

function tempPath(filename: string): string {
  return path.join(TEMP_DB, filename);
}

function persist(filename: string, content: string): void {
  fs.mkdirSync(TEMP_DB, { recursive: true });
  fs.writeFileSync(tempPath(filename), content);
}

function readIfExists(filename: string): string | null {
  try {
    return fs.readFileSync(tempPath(filename), 'utf-8');
  } catch {
    return null;
  }
}

function sha256Base64Url(input: string): string {
  return createHash('sha256').update(input).digest('base64url');
}

export const assembleAndSignMandatesTool = new FunctionTool({
  name: 'assembleAndSignMandates',
  description:
    'Builds and signs the open-checkout and open-payment mandates as real SD-JWTs (ES256) with a cnf.jwk agent key for key binding. The price cap and optional merchant allowlist are carried as mandate constraints. Persists them under TEMP_DB and returns their IDs and sd-hashes.',
  parameters: z.object({
    natural_language_description: z.string(),
    constraint_price_cap: z.number(),
    expires_at_iso: z.string(),
    allowed_merchants: z.array(z.string()).optional(),
    user_cart_confirmation_required: z.boolean().optional(),
  }),
  execute: async (args) => {
    const user = await loadOrCreateKeyPair(TEMP_DB, 'user');
    const agent = await loadOrCreateKeyPair(TEMP_DB, 'agent');

    // Constraints are always-present claims (not selectively disclosed) so the
    // monitoring agent can read them back when checking the open mandate.
    const baseClaims = {
      natural_language_description: args.natural_language_description,
      constraint_price_cap: args.constraint_price_cap,
      allowed_merchants: args.allowed_merchants ?? [],
      currency: 'USD',
      expires_at_iso: args.expires_at_iso,
      user_cart_confirmation_required: args.user_cart_confirmation_required ?? true,
    };

    const openCheckoutId = `open_chk_${randomUUID()}`;
    const openPaymentId = `open_pay_${randomUUID()}`;

    const openCheckout = await issueOpenMandate({
      claims: { ...baseClaims, kind: 'open_checkout' },
      disclosable: ['natural_language_description'],
      issuerPrivateJwk: user.privateKey,
      holderPublicJwk: agent.publicKey,
    });
    const openPayment = await issueOpenMandate({
      claims: { ...baseClaims, kind: 'open_payment' },
      disclosable: ['natural_language_description'],
      issuerPrivateJwk: user.privateKey,
      holderPublicJwk: agent.publicKey,
    });

    persist(`${openCheckoutId}.sdjwt`, openCheckout);
    persist(`${openPaymentId}.sdjwt`, openPayment);

    return {
      open_checkout_mandate_id: openCheckoutId,
      open_checkout_hash: sha256Base64Url(openCheckout),
      open_payment_mandate_id: openPaymentId,
      open_payment_hash: sha256Base64Url(openPayment),
    };
  },
});

export const checkConstraintsAgainstMandateTool = new FunctionTool({
  name: 'checkConstraintsAgainstMandate',
  description:
    "Verifies the open checkout mandate and checks the observed price (and optional merchant) against the mandate's constraints (price cap, merchant allowlist). Returns meets_constraints + any violations.",
  parameters: z.object({
    open_checkout_mandate_id: z.string(),
    current_price: z.number(),
    available: z.boolean(),
    merchant: z.string().optional(),
    currency: z.string().optional(),
  }),
  execute: async ({ open_checkout_mandate_id, current_price, available, merchant, currency }) => {
    if (!available) {
      return { meets_constraints: false, satisfies: false, violations: ['item_not_available'] };
    }
    const open = readIfExists(`${open_checkout_mandate_id}.sdjwt`);
    if (!open) {
      return { error: 'open_mandate_not_found', message: open_checkout_mandate_id };
    }
    const user = await loadOrCreateKeyPair(TEMP_DB, 'user');
    let claims: Record<string, unknown>;
    try {
      claims = (await verifyMandate({ mandateSdJwt: open, issuerPublicJwk: user.publicKey })).payload;
    } catch (e) {
      return { error: 'mandate_verification_failed', message: String(e) };
    }

    const priceCap = typeof claims.constraint_price_cap === 'number' ? claims.constraint_price_cap : undefined;
    const allowedMerchants = Array.isArray(claims.allowed_merchants)
      ? (claims.allowed_merchants as string[])
      : undefined;

    const { meetsConstraints, violations } = checkConstraints(
      { price: current_price, currency, merchant },
      { priceCap, currency: typeof claims.currency === 'string' ? claims.currency : undefined, allowedMerchants },
    );

    return {
      meets_constraints: meetsConstraints,
      satisfies: meetsConstraints, // alias for older prompt wording
      violations,
      price_cap: priceCap,
      price: current_price,
      available,
    };
  },
});

export const createCheckoutPresentationTool = new FunctionTool({
  name: 'createCheckoutPresentation',
  description:
    'Builds the closed-checkout mandate as a KB-SD-JWT presentation whose holder binding commits to checkout_jwt_hash, from the persisted open-checkout mandate.',
  parameters: z.object({
    open_checkout_mandate_id: z.string(),
    checkout_jwt_hash: z.string(),
    cart_id: z.string(),
  }),
  execute: async ({ open_checkout_mandate_id, checkout_jwt_hash }) => {
    const open = readIfExists(`${open_checkout_mandate_id}.sdjwt`);
    if (!open) return { error: 'open_mandate_not_found', message: open_checkout_mandate_id };
    const agent = await loadOrCreateKeyPair(TEMP_DB, 'agent');
    const closed = await presentClosedMandate({
      openMandateSdJwt: open,
      disclose: ['natural_language_description'],
      holderPrivateJwk: agent.privateKey,
      nonce: checkout_jwt_hash, // bind the presentation to this checkout
      audience: CREDENTIAL_PROVIDER_AUD,
    });
    const id = `chk_${randomUUID()}`;
    persist(`${id}.sdjwt`, closed);
    return { checkout_mandate_chain_id: id };
  },
});

export const createPaymentPresentationTool = new FunctionTool({
  name: 'createPaymentPresentation',
  description:
    'Builds the closed-payment mandate as a KB-SD-JWT presentation whose holder binding commits to checkout_jwt_hash (the transaction binding), from the persisted open-payment mandate.',
  parameters: z.object({
    open_payment_mandate_id: z.string(),
    checkout_jwt_hash: z.string(),
    payment_nonce: z.string().optional(),
  }),
  execute: async ({ open_payment_mandate_id, checkout_jwt_hash }) => {
    const open = readIfExists(`${open_payment_mandate_id}.sdjwt`);
    if (!open) return { error: 'open_mandate_not_found', message: open_payment_mandate_id };
    const agent = await loadOrCreateKeyPair(TEMP_DB, 'agent');
    // Bind to checkout_jwt_hash (transaction id), NOT an arbitrary nonce, so
    // the payment proof cannot be replayed against a different checkout.
    const closed = await presentClosedMandate({
      openMandateSdJwt: open,
      disclose: ['natural_language_description'],
      holderPrivateJwk: agent.privateKey,
      nonce: checkout_jwt_hash,
      audience: CREDENTIAL_PROVIDER_AUD,
    });
    const id = `pay_${randomUUID()}`;
    persist(`${id}.sdjwt`, closed);
    return { payment_mandate_chain_id: id };
  },
});

export const verifyCheckoutReceiptTool = new FunctionTool({
  name: 'verifyCheckoutReceipt',
  description:
    'Verifies a persisted closed-mandate presentation: checks the user (issuer) SD-JWT signature and the agent Key-Binding JWT against cnf.jwk, using the expected nonce (checkout_jwt_hash).',
  parameters: z.object({
    mandate_chain_id: z.string(),
    nonce: z.string(),
  }),
  execute: async ({ mandate_chain_id, nonce }) => {
    const presented = readIfExists(`${mandate_chain_id}.sdjwt`);
    if (!presented) return { verified: false, error: 'mandate_not_found', message: mandate_chain_id };
    const user = await loadOrCreateKeyPair(TEMP_DB, 'user');
    try {
      const result = await verifyMandate({ mandateSdJwt: presented, issuerPublicJwk: user.publicKey, nonce });
      return { verified: result.keyBound, key_bound: result.keyBound };
    } catch (e) {
      return { verified: false, error: 'verification_failed', message: String(e) };
    }
  },
});

export const resetTempDbTool = new FunctionTool({
  name: 'resetTempDb',
  description:
    'Clears persisted mandate files (open/closed checkout and payment) for a fresh run. Preserves signing keys and merchant inventory.',
  parameters: z.object({
    confirm: z.boolean().optional(),
  }),
  execute: async () => {
    let removed = 0;
    try {
      for (const f of fs.readdirSync(TEMP_DB)) {
        if (MANDATE_PREFIXES.some((p) => f.startsWith(p))) {
          fs.rmSync(tempPath(f), { force: true });
          removed += 1;
        }
      }
    } catch {
      return { status: 'ok', removed: 0, message: 'no temp-db to clear' };
    }
    return { status: 'ok', removed, message: `removed ${removed} mandate files` };
  },
});
