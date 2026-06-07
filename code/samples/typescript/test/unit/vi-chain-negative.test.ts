/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Rejection-path tests for the Verifiable Intent chain — the security
 * properties that MUST hold: expired credentials, missing/wrong issuer key, and
 * delegation to an out-of-mandate payee are all refused. Seed batch for the
 * autonomous improvement loop (see BACKLOG.md). Runs in-process, no servers.
 */

import { describe, it, expect } from 'vitest';
import {
  ACCEPTABLE_ITEMS,
  MERCHANT_AUD,
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

const NOW = 1_900_000_000;

/** Build a full, valid autonomous fulfillment for the tennis-racket scenario. */
async function buildChain() {
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
  return { issuer, user, agent, merchant, l1, l2, checkoutJwt, checkoutHash, fulfillment, racket };
}

describe('Verifiable Intent — rejection paths', () => {
  it('rejects an expired L3 (verified well after its exp)', async () => {
    const { issuer, l1, fulfillment } = await buildChain();
    // L3 exp = iat + 300; verify ~1h later → expired.
    const outcome = await verifyPaymentChainAndConstraints({
      l1Serialized: l1,
      l2PaymentSerialized: fulfillment.l2PaymentSerialized,
      l3PaymentSerialized: fulfillment.l3PaymentSerialized,
      issuerPublicJwk: issuer.publicKey,
      currentTime: NOW + 3600,
    });
    expect(outcome.valid).toBe(false);
    expect(outcome.result.valid).toBe(false);
  });

  it('fails closed when no issuer key is provided and verification is not skipped', async () => {
    const { l1, fulfillment } = await buildChain();
    const result = await verifyChain(
      decodeSdJwt(l1),
      decodeSdJwt(fulfillment.l2PaymentSerialized),
      {
        l3Payment: decodeSdJwt(fulfillment.l3PaymentSerialized),
        l1Serialized: l1,
        l2PaymentSerialized: fulfillment.l2PaymentSerialized,
        currentTime: NOW,
        // intentionally: no issuerPublicJwk, no skipIssuerVerification
      },
    );
    expect(result.valid).toBe(false);
  });

  it('rejects a chain verified against the wrong issuer key', async () => {
    const { l1, fulfillment } = await buildChain();
    const wrongIssuer = await makeKey('issuer');
    const outcome = await verifyPaymentChainAndConstraints({
      l1Serialized: l1,
      l2PaymentSerialized: fulfillment.l2PaymentSerialized,
      l3PaymentSerialized: fulfillment.l3PaymentSerialized,
      issuerPublicJwk: wrongIssuer.publicKey,
      currentTime: NOW,
    });
    expect(outcome.valid).toBe(false);
  });

  it('rejects a checkout presentation addressed to a different audience', async () => {
    const { issuer, l1, fulfillment } = await buildChain(); // L3b aud defaults to MERCHANT_AUD
    const good = await verifyCheckoutChain({
      l1Serialized: l1,
      l2CheckoutSerialized: fulfillment.l2CheckoutSerialized,
      l3CheckoutSerialized: fulfillment.l3CheckoutSerialized,
      issuerPublicJwk: issuer.publicKey,
      currentTime: NOW,
      expectedL3CheckoutAud: MERCHANT_AUD,
    });
    expect(good.valid).toBe(true);

    const wrong = await verifyCheckoutChain({
      l1Serialized: l1,
      l2CheckoutSerialized: fulfillment.l2CheckoutSerialized,
      l3CheckoutSerialized: fulfillment.l3CheckoutSerialized,
      issuerPublicJwk: issuer.publicKey,
      currentTime: NOW,
      expectedL3CheckoutAud: 'https://evil.example',
    });
    expect(wrong.valid).toBe(false);
  });

  it('refuses to build a fulfillment for a payee outside the mandate', async () => {
    const { agent, l2, checkoutJwt, checkoutHash, racket } = await buildChain();
    await expect(
      createAgentFulfillment({
        l2Serialized: l2,
        agent,
        checkoutJwt,
        checkoutHash,
        payee: { id: 'merchant-unknown', name: 'Not Allowed', website: 'https://nope.example' },
        itemId: racket.sku,
        amount: racket.price,
        paymentInstrument: PAYMENT_INSTRUMENT,
        iat: NOW,
      }),
    ).rejects.toThrow();
  });
});

describe('Verifiable Intent — immediate (2-layer) rejection paths', () => {
  it('rejects an immediate L2 verified against a different L1 (sd_hash binding)', async () => {
    const issuer = await makeKey('issuer');
    const user = await makeKey('user');
    const merchant = await makeKey('merchant');
    // Two issuer credentials for the SAME user key but different content → different serialization.
    const l1a = await issueIssuerCredential({ userPublicJwk: user.publicKey, issuer, sub: 'alice', iat: NOW });
    const l1b = await issueIssuerCredential({ userPublicJwk: user.publicKey, issuer, sub: 'bob', iat: NOW });
    const checkoutJwt = await createCheckoutJwt([{ sku: 'BAB86345' }], merchant);
    const l2 = await createUserMandateImmediate({
      l1Serialized: l1a,
      user,
      checkoutJwt,
      paymentInstrument: PAYMENT_INSTRUMENT,
      payee: MERCHANTS[0],
      amount: 27999,
      iat: NOW,
    });
    // L2's sd_hash binds it to l1a; verifying it against l1b must fail.
    const result = await verifyChain(decodeSdJwt(l1b), decodeSdJwt(l2), {
      issuerPublicJwk: issuer.publicKey,
      l1Serialized: l1b,
      currentTime: NOW,
    });
    expect(result.valid).toBe(false);
  });

  it('rejects an immediate chain verified against the wrong issuer key', async () => {
    const issuer = await makeKey('issuer');
    const user = await makeKey('user');
    const merchant = await makeKey('merchant');
    const wrongIssuer = await makeKey('issuer');
    const l1 = await issueIssuerCredential({ userPublicJwk: user.publicKey, issuer, sub: 'u', iat: NOW });
    const checkoutJwt = await createCheckoutJwt([{ sku: 'BAB86345' }], merchant);
    const l2 = await createUserMandateImmediate({
      l1Serialized: l1,
      user,
      checkoutJwt,
      paymentInstrument: PAYMENT_INSTRUMENT,
      payee: MERCHANTS[0],
      amount: 27999,
      iat: NOW,
    });
    const result = await verifyChain(decodeSdJwt(l1), decodeSdJwt(l2), {
      issuerPublicJwk: wrongIssuer.publicKey,
      l1Serialized: l1,
      currentTime: NOW,
    });
    expect(result.valid).toBe(false);
  });
});
