/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Mandate helper tools for shopping-agent-v2, backed by the Verifiable Intent
 * library (src/common/vi -> @verifiable-intent/core). This replicates the
 * official Python reference flow (verifiable_intent/python/examples) sliced
 * along the AP2 roles this agent owns: the User (Layer 2) and the Agent
 * (Layer 3 split fulfillment).
 *
 *   - assembleAndSignMandates: issues the Layer 1 issuer credential (binding the
 *     user key) and the Layer 2 autonomous user mandate (binding the agent key,
 *     carrying the amount-range / merchant / line-item constraints).
 *   - checkConstraintsAgainstMandate: reads the L2 constraints and checks an
 *     observed price/merchant against them.
 *   - createMandateFulfillment: the agent builds the split Layer 3 credentials
 *     (L3a payment for the network, L3b checkout for the merchant) plus the
 *     per-recipient L2 presentations, all bound to the checkout hash.
 *   - verifyCheckoutReceipt: verifies a merchant-signed checkout receipt (JWS).
 *   - resetTempDb: clears mandate files for a fresh run, preserving keys.
 *
 * Chain artifacts (serialized SD-JWTs) are persisted under TEMP_DB and referenced
 * by id so the merchant / credentials-provider MCP servers can verify them.
 */

import { FunctionTool } from '@google/adk';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { z } from 'zod';

import {
  ACCEPTABLE_ITEMS,
  MERCHANTS,
  PAYMENT_INSTRUMENT,
  type Dict,
  type ViKeyPair,
  b64urlDecode,
  checkConstraints,
  createAgentFulfillment,
  createUserMandateAutonomous,
  decodeSdJwt,
  es256Verify,
  hashAscii,
  hashDisclosure,
  issueIssuerCredential,
  jwtDecodeParts,
  loadOrCreateViKey,
  loadViPublicJwk,
  resolveDisclosures,
  StrictnessMode,
} from '../../common/vi/index.js';

const TEMP_DB = process.env.TEMP_DB_DIR ?? '.temp-db';

/** Singleton chain artifacts for the active run. */
const L1_FILE = 'l1.sdjwt';
const L2_FILE = 'l2.sdjwt';
/** Mandate file prefixes cleared by resetTempDb (never the *_key.jwk.json keys). */
const MANDATE_PREFIXES = ['l1', 'l2', 'chk_', 'pay_'];

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

/** Verify a plain ES256 compact JWS and return its payload. */
async function verifyJws(token: string, publicJwk: ViKeyPair['publicKey']): Promise<Dict> {
  const parts = token.split('.');
  if (parts.length !== 3) {
    throw new Error('malformed JWT: expected three dot-separated segments');
  }
  const ok = await es256Verify(`${parts[0]}.${parts[1]}`, b64urlDecode(parts[2]), publicJwk);
  if (!ok) {
    throw new Error('invalid JWT signature');
  }
  return jwtDecodeParts(token).payload as Dict;
}

/** Build the merchant allowlist (Dict[]) the L2 mandate carries. */
function resolveMerchants(allowedNames?: string[]): Dict[] {
  if (!allowedNames || allowedNames.length === 0) {
    return MERCHANTS;
  }
  return allowedNames.map((name) => {
    const known = MERCHANTS.find((m) => String(m.name).toLowerCase() === name.toLowerCase());
    return known ?? { name, website: `https://${name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}.example` };
  });
}

export const assembleAndSignMandatesTool = new FunctionTool({
  name: 'assembleAndSignMandates',
  description:
    'Issues the Layer 1 issuer credential (binding the user key) and signs the Layer 2 autonomous ' +
    'user mandate as a real SD-JWT delegation chain (ES256). The mandate delegates to the agent key ' +
    '(cnf.jwk) and carries the amount-range, allowed-merchant and acceptable-item constraints. ' +
    'Persists L1 + L2 under TEMP_DB and returns their ids and hashes.',
  parameters: z.object({
    natural_language_description: z.string(),
    constraint_price_cap: z.number(),
    expires_at_iso: z.string(),
    allowed_merchants: z.array(z.string()).optional(),
    item_id: z.string().optional(),
    item_title: z.string().optional(),
  }),
  execute: async (args) => {
    const issuer = await loadOrCreateViKey(TEMP_DB, 'issuer');
    const user = await loadOrCreateViKey(TEMP_DB, 'user');
    const agent = await loadOrCreateViKey(TEMP_DB, 'agent');

    const now = Math.floor(Date.now() / 1000);
    const expiresAt = Math.floor(new Date(args.expires_at_iso).getTime() / 1000);
    const ttlSeconds = Number.isFinite(expiresAt) && expiresAt > now ? expiresAt - now : 3600;
    const amountMaxCents = Math.round(args.constraint_price_cap * 100);

    const merchants = resolveMerchants(args.allowed_merchants);
    const acceptableItems: Dict[] = args.item_id
      ? [{ id: args.item_id, title: args.item_title ?? args.natural_language_description }]
      : ACCEPTABLE_ITEMS;

    // L1 — the Issuer (credentials provider) binds the user's key.
    const l1 = await issueIssuerCredential({
      userPublicJwk: user.publicKey,
      issuer,
      sub: 'shopping-agent-user',
      iat: now,
      panLastFour: '1234',
    });

    // L2 — the User delegates to the agent with constraints (autonomous mode).
    const l2 = await createUserMandateAutonomous({
      l1Serialized: l1,
      user,
      agentPublicJwk: agent.publicKey,
      agentKid: agent.kid,
      promptSummary: args.natural_language_description,
      iat: now,
      ttlSeconds,
      merchants,
      acceptableItems,
      paymentInstrument: PAYMENT_INSTRUMENT,
      amountMin: 0,
      amountMax: amountMaxCents,
    });

    persist(L1_FILE, l1);
    persist(L2_FILE, l2);

    return {
      credential_id: 'l1',
      mandate_id: 'l2',
      l1_hash: await hashAscii(l1),
      l2_hash: await hashAscii(l2),
      amount_cap_cents: amountMaxCents,
      currency: 'USD',
    };
  },
});

export const checkConstraintsAgainstMandateTool = new FunctionTool({
  name: 'checkConstraintsAgainstMandate',
  description:
    "Reads the signed Layer 2 user mandate and checks an observed price (and optional merchant) " +
    "against its amount-range and allowed-payee constraints. Returns meets_constraints + violations.",
  parameters: z.object({
    current_price: z.number(),
    available: z.boolean(),
    merchant: z.string().optional(),
    currency: z.string().optional(),
  }),
  execute: async ({ current_price, available, merchant, currency }) => {
    if (!available) {
      return { meets_constraints: false, satisfies: false, violations: ['item_not_available'] };
    }
    const l2Serialized = readIfExists(L2_FILE);
    if (!l2Serialized) {
      return { error: 'mandate_not_found', message: 'l2 mandate not signed yet' };
    }

    let l2;
    try {
      l2 = decodeSdJwt(l2Serialized);
    } catch (e) {
      return { error: 'mandate_decode_failed', message: String(e) };
    }
    const claims = await resolveDisclosures(l2);
    const delegates = (claims.delegate_payload as Dict[] | undefined) ?? [];
    let paymentConstraints: Dict[] = [];
    for (const d of delegates) {
      if (d && typeof d === 'object' && d.vct === 'mandate.payment.open.1') {
        paymentConstraints = (d.constraints as Dict[] | undefined) ?? [];
        break;
      }
    }

    // Build a candidate fulfillment from the observed offer and resolve allowed_payees.
    const fulfillment: Dict = {
      payment_amount: { currency: currency ?? 'USD', amount: Math.round(current_price * 100) },
    };
    const discByHash = new Map<string, unknown[]>();
    for (let i = 0; i < l2.disclosures.length; i++) {
      discByHash.set(await hashDisclosure(l2.disclosures[i]), l2.disclosureValues[i]);
    }
    for (const c of paymentConstraints) {
      if (c.type === 'mandate.payment.allowed_payees') {
        const resolved: unknown[] = [];
        for (const ref of (c.allowed as unknown[] | undefined) ?? []) {
          const refHash = ref && typeof ref === 'object' ? ((ref as Dict)['...'] as string) : '';
          if (refHash && discByHash.has(refHash)) {
            const dv = discByHash.get(refHash)!;
            resolved.push(dv[dv.length - 1]);
          }
        }
        fulfillment.allowed_merchants = merchant ? [{ name: merchant }] : resolved;
      }
    }

    const result = checkConstraints(paymentConstraints, fulfillment, { mode: StrictnessMode.PERMISSIVE });
    return {
      meets_constraints: result.satisfied,
      satisfies: result.satisfied, // alias for older prompt wording
      violations: result.violations,
      price: current_price,
      available,
    };
  },
});

export const createMandateFulfillmentTool = new FunctionTool({
  name: 'createMandateFulfillment',
  description:
    'Builds the split Layer 3 agent fulfillment from the signed L2 mandate: L3a (payment, for the ' +
    'network) and L3b (checkout, for the merchant), each bound to the checkout hash, plus the ' +
    'per-recipient L2 presentations (selective disclosure). Persists them and returns their chain ids.',
  parameters: z.object({
    checkout_jwt: z.string(),
    checkout_jwt_hash: z.string(),
    item_id: z.string(),
    amount_cents: z.number(),
    payee_name: z.string().optional(),
    currency: z.string().optional(),
  }),
  execute: async ({ checkout_jwt, checkout_jwt_hash, item_id, amount_cents, payee_name, currency }) => {
    const l2Serialized = readIfExists(L2_FILE);
    if (!l2Serialized) {
      return { error: 'mandate_not_found', message: 'l2 mandate not signed yet' };
    }
    const agent = await loadOrCreateViKey(TEMP_DB, 'agent');

    const payee =
      (payee_name && MERCHANTS.find((m) => String(m.name).toLowerCase() === payee_name.toLowerCase())) ||
      MERCHANTS[0];

    let fulfillment;
    try {
      fulfillment = await createAgentFulfillment({
        l2Serialized,
        agent,
        checkoutJwt: checkout_jwt,
        checkoutHash: checkout_jwt_hash,
        payee,
        itemId: item_id,
        amount: amount_cents,
        currency: currency ?? 'USD',
        paymentInstrument: PAYMENT_INSTRUMENT,
      });
    } catch (e) {
      return { error: 'fulfillment_failed', message: String(e) };
    }

    const checkoutId = `chk_${randomUUID()}`;
    const paymentId = `pay_${randomUUID()}`;
    persist(`${checkoutId}.sdjwt`, fulfillment.l3CheckoutSerialized);
    persist(`${checkoutId}.l2.sdjwt`, fulfillment.l2CheckoutSerialized);
    persist(`${paymentId}.sdjwt`, fulfillment.l3PaymentSerialized);
    persist(`${paymentId}.l2.sdjwt`, fulfillment.l2PaymentSerialized);

    return {
      checkout_mandate_chain_id: checkoutId,
      payment_mandate_chain_id: paymentId,
    };
  },
});

export const verifyCheckoutReceiptTool = new FunctionTool({
  name: 'verifyCheckoutReceipt',
  description:
    'Verifies a merchant-signed checkout receipt (compact ES256 JWS) against the merchant public key. ' +
    'Returns verified + the receipt id and issuer.',
  parameters: z.object({
    checkout_receipt: z.string(),
  }),
  execute: async ({ checkout_receipt }) => {
    const merchantPub = loadViPublicJwk(TEMP_DB, 'merchant');
    if (!merchantPub) {
      return { verified: false, error: 'merchant_key_unavailable', message: 'merchant key not found in TEMP_DB' };
    }
    try {
      const payload = await verifyJws(checkout_receipt, merchantPub);
      return { verified: true, receipt_id: payload.receipt_id, issuer: payload.iss };
    } catch (e) {
      return { verified: false, error: 'receipt_verification_failed', message: String(e) };
    }
  },
});

export const resetTempDbTool = new FunctionTool({
  name: 'resetTempDb',
  description:
    'Clears persisted mandate / chain files (L1, L2, and the L3 fulfillment chains) for a fresh run. ' +
    'Preserves signing keys and merchant inventory.',
  parameters: z.object({
    confirm: z.boolean().optional(),
  }),
  execute: async () => {
    let removed = 0;
    try {
      for (const f of fs.readdirSync(TEMP_DB)) {
        if (f.endsWith('_key.jwk.json')) continue;
        if (MANDATE_PREFIXES.some((p) => f.startsWith(p)) && (f.endsWith('.sdjwt') || f === L1_FILE || f === L2_FILE)) {
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
