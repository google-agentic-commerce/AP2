/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * v1 (human-present) Verifiable Intent wiring tests — exercises the exact
 * facade functions the AP2 v1 roles call:
 *   - shopping-agent signMandatesOnUserDevice  -> createImmediateUserAuthorization
 *     (L1 issuer credential + L2 immediate user mandate, JSON envelope carried
 *     in the PaymentMandate's userAuthorization; AP2 major units -> VI minor)
 *   - merchant-payment-processor-agent initiatePayment -> verifyImmediateUserAuthorization
 *     (chain verification with issuer key + aud pinning, then amount/currency/
 *     payee cross-check against the AP2 PaymentMandate)
 *
 * Runs entirely in-process (no servers / no Gemini). A fixed `currentTime`
 * keeps verification deterministic.
 */

import { describe, it, expect } from 'vitest';
import {
  MERCHANTS,
  NETWORK_AUD,
  PAYMENT_INSTRUMENT,
  ROLE_KIDS,
  type Dict,
  type ViKeyPair,
  createCheckoutJwt,
  createImmediateUserAuthorization,
  decodeSdJwt,
  generateEs256Key,
  resolveDisclosures,
  verifyImmediateUserAuthorization,
} from '../../src/common/vi/index.js';

const NOW = 1_900_000_000; // fixed, deterministic timestamp

async function makeKey(name: string): Promise<ViKeyPair> {
  const { publicKey, privateKey } = await generateEs256Key();
  return { publicKey, privateKey, kid: ROLE_KIDS[name] ?? `${name}-key-1` };
}

/** The shopping-agent side: sign a v1 purchase into a userAuthorization envelope. */
async function signV1Purchase(amountMajor = 279.99) {
  const issuer = await makeKey('issuer');
  const user = await makeKey('user');
  const merchant = await makeKey('merchant');

  // The merchant's cart commitment the L2 binds to (cartMandate.merchantAuthorization).
  const checkoutJwt = await createCheckoutJwt([{ sku: 'BAB86345', quantity: 1 }], merchant);

  const userAuthorization = await createImmediateUserAuthorization({
    issuer,
    user,
    sub: 'shopping-agent-user',
    checkoutJwt,
    paymentInstrument: PAYMENT_INSTRUMENT,
    payee: MERCHANTS[0], // Tennis Warehouse — closed mandates require name + website
    amountMajor,
    currency: 'USD',
    promptSummary: 'Purchase: Babolat Pure Aero Tennis Racket',
    iat: NOW,
  });

  return { issuer, userAuthorization, amountMajor };
}

describe('Verifiable Intent — v1 human-present userAuthorization wiring', () => {
  it('signs an immediate chain that verifies against the matching AP2 payment mandate', async () => {
    const { issuer, userAuthorization } = await signV1Purchase();

    const outcome = await verifyImmediateUserAuthorization({
      userAuthorization,
      issuerPublicJwk: issuer.publicKey,
      expectedAmountMajor: 279.99,
      expectedCurrency: 'USD',
      expectedPayeeName: 'Tennis Warehouse',
      currentTime: NOW,
    });

    expect(outcome.valid).toBe(true);
    expect(outcome.errors).toEqual([]);
    expect(outcome.result?.valid).toBe(true);
  });

  it('converts the AP2 major-unit amount to minor units in the L2 mandate', async () => {
    const { userAuthorization } = await signV1Purchase(279.99);

    const envelope = JSON.parse(userAuthorization) as { l1: string; l2: string };
    const claims = await resolveDisclosures(decodeSdJwt(envelope.l2));
    const payment = ((claims.delegate_payload as Dict[] | undefined) ?? []).find(
      (d) => d.vct === 'mandate.payment.1',
    )!;
    const paymentAmount = payment.payment_amount as Dict;

    expect(paymentAmount.amount).toBe(27999); // 279.99 major -> 27999 minor
    expect(paymentAmount.currency).toBe('USD');
    // The L2 aud is stamped for the payment network the processor pins.
    const l2Payload = decodeSdJwt(envelope.l2).payload as Dict;
    expect(l2Payload.aud).toBe(NETWORK_AUD);
  });

  it('rejects when the AP2 payment mandate amount differs from the signed mandate', async () => {
    const { issuer, userAuthorization } = await signV1Purchase(279.99);

    const outcome = await verifyImmediateUserAuthorization({
      userAuthorization,
      issuerPublicJwk: issuer.publicKey,
      expectedAmountMajor: 300.0, // tampered total
      expectedCurrency: 'USD',
      expectedPayeeName: 'Tennis Warehouse',
      currentTime: NOW,
    });

    expect(outcome.result?.valid).toBe(true); // chain itself is cryptographically valid
    expect(outcome.valid).toBe(false);
    expect(outcome.errors.some((e) => e.includes('amount mismatch'))).toBe(true);
  });

  it('rejects when the payee differs from the signed mandate', async () => {
    const { issuer, userAuthorization } = await signV1Purchase();

    const outcome = await verifyImmediateUserAuthorization({
      userAuthorization,
      issuerPublicJwk: issuer.publicKey,
      expectedAmountMajor: 279.99,
      expectedCurrency: 'USD',
      expectedPayeeName: 'Evil Merchant',
      currentTime: NOW,
    });

    expect(outcome.valid).toBe(false);
    expect(outcome.errors.some((e) => e.includes('payee mismatch'))).toBe(true);
  });

  it('rejects a tampered L2 (signature no longer verifies)', async () => {
    const { issuer, userAuthorization } = await signV1Purchase();
    const envelope = JSON.parse(userAuthorization) as { l1: string; l2: string };

    // Flip a character in the L2 base JWT payload segment.
    const parts = envelope.l2.split('~');
    const jwtParts = parts[0].split('.');
    const payload = jwtParts[1];
    jwtParts[1] = (payload[0] === 'A' ? 'B' : 'A') + payload.slice(1);
    parts[0] = jwtParts.join('.');
    const tampered = JSON.stringify({ l1: envelope.l1, l2: parts.join('~') });

    const outcome = await verifyImmediateUserAuthorization({
      userAuthorization: tampered,
      issuerPublicJwk: issuer.publicKey,
      expectedAmountMajor: 279.99,
      currentTime: NOW,
    });

    expect(outcome.valid).toBe(false);
    expect(outcome.errors.length).toBeGreaterThan(0);
  });

  it('rejects the legacy fake userAuthorization string (fail closed)', async () => {
    const { issuer } = await signV1Purchase();

    const outcome = await verifyImmediateUserAuthorization({
      userAuthorization: 'cart_hash_123_payment_hash_456',
      issuerPublicJwk: issuer.publicKey,
      expectedAmountMajor: 279.99,
      currentTime: NOW,
    });

    expect(outcome.valid).toBe(false);
    expect(outcome.result).toBeNull();
  });

  it('rejects the chain against the wrong issuer key', async () => {
    const { userAuthorization } = await signV1Purchase();
    const wrongIssuer = await makeKey('issuer');

    const outcome = await verifyImmediateUserAuthorization({
      userAuthorization,
      issuerPublicJwk: wrongIssuer.publicKey,
      expectedAmountMajor: 279.99,
      currentTime: NOW,
    });

    expect(outcome.valid).toBe(false);
    expect(outcome.result?.valid).toBe(false);
  });

  it('rejects a presentation addressed to a different audience (aud pinning)', async () => {
    const { issuer, userAuthorization } = await signV1Purchase();

    const outcome = await verifyImmediateUserAuthorization({
      userAuthorization,
      issuerPublicJwk: issuer.publicKey,
      expectedAmountMajor: 279.99,
      expectedL2Aud: 'https://other-network.example',
      currentTime: NOW,
    });

    expect(outcome.valid).toBe(false);
    expect(outcome.errors.some((e) => e.includes('L2 aud mismatch'))).toBe(true);
  });

  it('rejects an expired user mandate', async () => {
    const { issuer, userAuthorization } = await signV1Purchase();

    const outcome = await verifyImmediateUserAuthorization({
      userAuthorization,
      issuerPublicJwk: issuer.publicKey,
      expectedAmountMajor: 279.99,
      currentTime: NOW + 901 + 300, // past the 900s immediate TTL + clock skew
    });

    expect(outcome.valid).toBe(false);
  });
});
