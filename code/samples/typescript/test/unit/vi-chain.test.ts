/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * End-to-end Verifiable Intent chain tests — the TypeScript replication of the
 * official Python reference flows (verifiable_intent/python/examples):
 *   - autonomous_flow.py: L1 issuer -> L2 user (open, agent delegation)
 *     -> L3a/L3b agent fulfillment -> merchant + network verification + constraints
 *   - immediate_flow.py: L1 issuer -> L2 user (final values, no L3) -> verification
 *
 * Runs entirely in-process (no servers / no Gemini), using @verifiable-intent/core
 * via src/common/vi. A fixed `currentTime` keeps verification deterministic.
 */

import { describe, it, expect } from 'vitest';
import {
  ACCEPTABLE_ITEMS,
  MERCHANTS,
  PAYMENT_INSTRUMENT,
  ROLE_KIDS,
  type ViKeyPair,
  createAgentFulfillment,
  createCheckoutJwt,
  checkoutHashFromJwt,
  createUserMandateAutonomous,
  createUserMandateImmediate,
  decodeSdJwt,
  findProduct,
  generateEs256Key,
  issueIssuerCredential,
  verifyChain,
  verifyCheckoutChain,
  verifyPaymentChainAndConstraints,
} from '../../src/common/vi/index.js';

async function makeKey(name: string): Promise<ViKeyPair> {
  const { publicKey, privateKey } = await generateEs256Key();
  return { publicKey, privateKey, kid: ROLE_KIDS[name] ?? `${name}-key-1` };
}

const NOW = 1_900_000_000; // fixed, deterministic timestamp

describe('Verifiable Intent — autonomous (3-layer) flow', () => {
  it('issues L1->L2->L3a/L3b and verifies merchant + network chains with constraints', async () => {
    const issuer = await makeKey('issuer');
    const user = await makeKey('user');
    const agent = await makeKey('agent');
    const merchant = await makeKey('merchant');

    // L1 — Credentials Provider issues the issuer credential, binding the user key.
    const l1 = await issueIssuerCredential({
      userPublicJwk: user.publicKey,
      issuer,
      sub: 'user-alice-001',
      iat: NOW,
      email: 'alice@example.com',
      panLastFour: '1234',
    });

    // L2 — User signs the autonomous mandate, delegating to the agent.
    const l2 = await createUserMandateAutonomous({
      l1Serialized: l1,
      user,
      agentPublicJwk: agent.publicKey,
      agentKid: agent.kid,
      promptSummary: 'Buy a Babolat tennis racket under $400',
      iat: NOW,
      merchants: MERCHANTS,
      acceptableItems: ACCEPTABLE_ITEMS,
      paymentInstrument: PAYMENT_INSTRUMENT,
      amountMin: 10000,
      amountMax: 40000,
      recurrence: { frequency: 'YEAR', startDate: '2026-01-01', endDate: '2028-01-01', number: 3 },
    });

    // Merchant produces a checkout JWT for the agent-selected racket.
    const racket = findProduct('BAB86345')!;
    const checkoutJwt = await createCheckoutJwt([{ sku: racket.sku, quantity: 1 }], merchant);
    const checkoutHash = checkoutHashFromJwt(checkoutJwt);

    // L3 — Agent builds split fulfillment + per-recipient L2 presentations.
    const fulfillment = await createAgentFulfillment({
      l2Serialized: l2,
      agent,
      checkoutJwt,
      checkoutHash,
      payee: MERCHANTS[0],
      itemId: racket.sku,
      amount: racket.price,
      paymentInstrument: PAYMENT_INSTRUMENT,
      iat: NOW,
    });

    // Merchant verifies the checkout-side chain (full L2 for pairing, as the example does).
    const merchantResult = await verifyCheckoutChain({
      l1Serialized: l1,
      l2CheckoutSerialized: fulfillment.l2CheckoutSerialized,
      l3CheckoutSerialized: fulfillment.l3CheckoutSerialized,
      issuerPublicJwk: issuer.publicKey,
      l2Serialized: l2,
      currentTime: NOW,
    });
    expect(merchantResult.valid).toBe(true);
    expect(merchantResult.errors).toEqual([]);
    expect(merchantResult.l2CheckoutDisclosed).toBe(true);

    // Network verifies the payment-side chain and enforces constraints (STRICT).
    const networkOutcome = await verifyPaymentChainAndConstraints({
      l1Serialized: l1,
      l2PaymentSerialized: fulfillment.l2PaymentSerialized,
      l3PaymentSerialized: fulfillment.l3PaymentSerialized,
      issuerPublicJwk: issuer.publicKey,
      l2Serialized: l2,
      currentTime: NOW,
    });
    expect(networkOutcome.result.valid).toBe(true);
    expect(networkOutcome.constraints).not.toBeNull();
    expect(networkOutcome.constraints!.satisfied).toBe(true);
    expect(networkOutcome.valid).toBe(true);
  });

  it('verifies the merchant chain without the full L2 (privacy-strict: checkout presentation only)', async () => {
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
      amountMin: 10000,
      amountMax: 40000,
    });
    const racket = findProduct('BAB86345')!;
    const checkoutJwt = await createCheckoutJwt([{ sku: racket.sku }], merchant);
    const checkoutHash = checkoutHashFromJwt(checkoutJwt);
    const fulfillment = await createAgentFulfillment({
      l2Serialized: l2,
      agent,
      checkoutJwt,
      checkoutHash,
      payee: MERCHANTS[0],
      itemId: racket.sku,
      amount: racket.price,
      paymentInstrument: PAYMENT_INSTRUMENT,
      iat: NOW,
    });

    // No l2Serialized → defaults to the checkout presentation the merchant actually receives.
    const merchantResult = await verifyCheckoutChain({
      l1Serialized: l1,
      l2CheckoutSerialized: fulfillment.l2CheckoutSerialized,
      l3CheckoutSerialized: fulfillment.l3CheckoutSerialized,
      issuerPublicJwk: issuer.publicKey,
      currentTime: NOW,
    });
    expect(merchantResult.valid).toBe(true);
  });

  it('rejects an over-budget payment via STRICT constraint enforcement', async () => {
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
      promptSummary: 'cheap racket only',
      iat: NOW,
      merchants: MERCHANTS,
      acceptableItems: ACCEPTABLE_ITEMS,
      paymentInstrument: PAYMENT_INSTRUMENT,
      amountMin: 1000,
      amountMax: 20000, // cap BELOW the racket price (27999)
    });
    const racket = findProduct('BAB86345')!;
    const checkoutJwt = await createCheckoutJwt([{ sku: racket.sku }], merchant);
    const checkoutHash = checkoutHashFromJwt(checkoutJwt);
    const fulfillment = await createAgentFulfillment({
      l2Serialized: l2,
      agent,
      checkoutJwt,
      checkoutHash,
      payee: MERCHANTS[0],
      itemId: racket.sku,
      amount: racket.price, // 27999 > 20000 cap
      paymentInstrument: PAYMENT_INSTRUMENT,
      iat: NOW,
    });

    const networkOutcome = await verifyPaymentChainAndConstraints({
      l1Serialized: l1,
      l2PaymentSerialized: fulfillment.l2PaymentSerialized,
      l3PaymentSerialized: fulfillment.l3PaymentSerialized,
      issuerPublicJwk: issuer.publicKey,
      l2Serialized: l2,
      currentTime: NOW,
    });
    // Chain is cryptographically valid, but the amount violates the mandate.
    expect(networkOutcome.result.valid).toBe(true);
    expect(networkOutcome.constraints!.satisfied).toBe(false);
    expect(networkOutcome.valid).toBe(false);
    expect(networkOutcome.errors.length).toBeGreaterThan(0);
  });
});

describe('Verifiable Intent — immediate (2-layer) flow', () => {
  it('issues L1->L2 with final values and verifies the 2-layer chain', async () => {
    const issuer = await makeKey('issuer');
    const user = await makeKey('user');
    const merchant = await makeKey('merchant');

    const l1 = await issueIssuerCredential({
      userPublicJwk: user.publicKey,
      issuer,
      sub: 'user-bob-001',
      iat: NOW,
      email: 'bob@example.com',
      panLastFour: '5678',
    });

    const checkoutJwt = await createCheckoutJwt([{ sku: 'BAB86345', quantity: 1 }], merchant);
    const l2 = await createUserMandateImmediate({
      l1Serialized: l1,
      user,
      checkoutJwt,
      paymentInstrument: PAYMENT_INSTRUMENT,
      payee: MERCHANTS[0],
      amount: 27999,
      iat: NOW,
      promptSummary: 'Purchase Babolat Pure Aero racket',
    });

    // Merchant: structural check (issuer signature verified out of band).
    const merchantResult = await verifyChain(decodeSdJwt(l1), decodeSdJwt(l2), {
      skipIssuerVerification: true,
      currentTime: NOW,
    });
    expect(merchantResult.valid).toBe(true);

    // Network: full verification with the issuer key.
    const networkResult = await verifyChain(decodeSdJwt(l1), decodeSdJwt(l2), {
      issuerPublicJwk: issuer.publicKey,
      l1Serialized: l1,
      currentTime: NOW,
    });
    expect(networkResult.valid).toBe(true);
    expect(networkResult.errors).toEqual([]);
  });
});
