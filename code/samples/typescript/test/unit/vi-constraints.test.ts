/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Boundary tests for the payment amount/currency constraint — the core VI
 * guarantee that an autonomous agent cannot spend beyond the user's mandate.
 * Exercises the exact cap boundary and a currency mismatch through the network
 * verification path. Runs in-process (no servers / no Gemini).
 */

import { describe, it, expect } from 'vitest';
import {
  ACCEPTABLE_ITEMS,
  MERCHANTS,
  NETWORK_AUD,
  PAYMENT_INSTRUMENT,
  ROLE_KIDS,
  type ViKeyPair,
  createAgentFulfillment,
  createCheckoutJwt,
  checkoutHashFromJwt,
  createUserMandateAutonomous,
  findProduct,
  generateEs256Key,
  issueIssuerCredential,
  verifyPaymentChainAndConstraints,
} from '../../src/common/vi/index.js';

const NOW = 1_900_000_000;

async function makeKey(name: string): Promise<ViKeyPair> {
  const { publicKey, privateKey } = await generateEs256Key();
  return { publicKey, privateKey, kid: ROLE_KIDS[name] ?? `${name}-key-1` };
}

/** Build + verify a payment chain with a given mandate cap and fulfilled amount/currency. */
async function settle(opts: { amountMax: number; amount: number; currency?: string }) {
  const issuer = await makeKey('issuer');
  const user = await makeKey('user');
  const agent = await makeKey('agent');
  const merchant = await makeKey('merchant');

  const l1 = await issueIssuerCredential({ userPublicJwk: user.publicKey, issuer, sub: 'u', iat: NOW });
  const l2 = await createUserMandateAutonomous({
    l1Serialized: l1,
    user,
    agentPublicJwk: agent.publicKey,
    agentKid: agent.kid,
    promptSummary: 'racket',
    iat: NOW,
    merchants: MERCHANTS,
    acceptableItems: ACCEPTABLE_ITEMS,
    paymentInstrument: PAYMENT_INSTRUMENT,
    amountMin: 0,
    amountMax: opts.amountMax,
    currency: 'USD',
  });
  const racket = findProduct('BAB86345')!;
  const checkoutJwt = await createCheckoutJwt([{ sku: racket.sku }], merchant);
  const checkoutHash = await checkoutHashFromJwt(checkoutJwt);
  const f = await createAgentFulfillment({
    l2Serialized: l2,
    agent,
    checkoutJwt,
    checkoutHash,
    payee: MERCHANTS[0],
    itemId: racket.sku,
    amount: opts.amount,
    currency: opts.currency ?? 'USD',
    paymentInstrument: PAYMENT_INSTRUMENT,
    iat: NOW,
  });
  return verifyPaymentChainAndConstraints({
    l1Serialized: l1,
    l2PaymentSerialized: f.l2PaymentSerialized,
    l3PaymentSerialized: f.l3PaymentSerialized,
    issuerPublicJwk: issuer.publicKey,
    currentTime: NOW,
    expectedL3PaymentAud: NETWORK_AUD,
  });
}

describe('VI payment amount/currency constraint boundaries', () => {
  it('allows an amount exactly at the cap', async () => {
    const outcome = await settle({ amountMax: 27999, amount: 27999 });
    expect(outcome.constraints?.satisfied).toBe(true);
    expect(outcome.valid).toBe(true);
  });

  it('rejects an amount one minor unit over the cap', async () => {
    const outcome = await settle({ amountMax: 27998, amount: 27999 });
    expect(outcome.result.valid).toBe(true); // chain is cryptographically valid
    expect(outcome.constraints?.satisfied).toBe(false); // amount violates the cap
    expect(outcome.valid).toBe(false);
  });

  it('rejects a currency that differs from the mandate', async () => {
    const outcome = await settle({ amountMax: 40000, amount: 27999, currency: 'EUR' });
    expect(outcome.result.valid).toBe(true);
    expect(outcome.constraints?.satisfied).toBe(false);
    expect(outcome.valid).toBe(false);
  });
});
