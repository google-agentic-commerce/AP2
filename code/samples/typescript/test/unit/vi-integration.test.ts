/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Cross-role integration test — exercises the exact persisted-file contract the
 * MCP servers use (the serialized SD-JWTs written by shopping-agent-v2 and read
 * back by merchant-agent-mcp / credentials-provider-mcp), with the same
 * aud-pinned verification each role performs. This locks the wiring end-to-end
 * without spawning servers or calling Gemini.
 *
 * File contract (TEMP_DB):
 *   l1.sdjwt, l2.sdjwt            (agent: assembleAndSignMandates)
 *   <chk>.sdjwt, <chk>.l2.sdjwt  (agent: createMandateFulfillment — merchant view)
 *   <pay>.sdjwt, <pay>.l2.sdjwt  (agent: createMandateFulfillment — network view)
 */

import { afterEach, beforeEach, describe, it, expect } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  ACCEPTABLE_ITEMS,
  MERCHANT_AUD,
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
  verifyCheckoutChain,
  verifyPaymentChainAndConstraints,
} from '../../src/common/vi/index.js';

const NOW = 1_900_000_000;

async function makeKey(name: string): Promise<ViKeyPair> {
  const { publicKey, privateKey } = await generateEs256Key();
  return { publicKey, privateKey, kid: ROLE_KIDS[name] ?? `${name}-key-1` };
}

let TEMP_DB: string;
beforeEach(() => {
  TEMP_DB = fs.mkdtempSync(path.join(os.tmpdir(), 'vi-it-'));
});
afterEach(() => {
  fs.rmSync(TEMP_DB, { recursive: true, force: true });
});

const persist = (name: string, content: string): void =>
  fs.writeFileSync(path.join(TEMP_DB, name), content);
const read = (name: string): string => fs.readFileSync(path.join(TEMP_DB, name), 'utf-8');

/**
 * Drive the agent side (issuer L1, user L2, merchant checkout, split L3) and
 * persist every artifact under TEMP_DB exactly as the role servers expect.
 */
async function runAgentSide(amountMaxCents: number) {
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
    amountMax: amountMaxCents,
  });
  persist('l1.sdjwt', l1);
  persist('l2.sdjwt', l2);

  const racket = findProduct('BAB86345')!;
  const checkoutJwt = await createCheckoutJwt([{ sku: racket.sku }], merchant);
  const checkoutHash = checkoutHashFromJwt(checkoutJwt);
  const f = await createAgentFulfillment({
    l2Serialized: l2,
    agent,
    checkoutJwt,
    checkoutHash,
    payee: MERCHANTS[0],
    itemId: racket.sku,
    amount: racket.price, // 27999
    paymentInstrument: PAYMENT_INSTRUMENT,
    iat: NOW,
  });
  const chk = 'chk_test';
  const pay = 'pay_test';
  persist(`${chk}.sdjwt`, f.l3CheckoutSerialized);
  persist(`${chk}.l2.sdjwt`, f.l2CheckoutSerialized);
  persist(`${pay}.sdjwt`, f.l3PaymentSerialized);
  persist(`${pay}.l2.sdjwt`, f.l2PaymentSerialized);

  return { issuer, chk, pay, price: racket.price };
}

describe('Verifiable Intent — cross-role file contract', () => {
  it('completes a purchase: merchant + network verify from disk with aud pinning', async () => {
    const { issuer, chk, pay } = await runAgentSide(40000);

    // Merchant role: read its files, verify the checkout chain (aud-pinned).
    const merchantResult = await verifyCheckoutChain({
      l1Serialized: read('l1.sdjwt'),
      l2CheckoutSerialized: read(`${chk}.l2.sdjwt`),
      l3CheckoutSerialized: read(`${chk}.sdjwt`),
      issuerPublicJwk: issuer.publicKey,
      currentTime: NOW,
      expectedL3CheckoutAud: MERCHANT_AUD,
    });
    expect(merchantResult.valid).toBe(true);

    // Network/CP role: read its files, verify the payment chain + constraints.
    const networkOutcome = await verifyPaymentChainAndConstraints({
      l1Serialized: read('l1.sdjwt'),
      l2PaymentSerialized: read(`${pay}.l2.sdjwt`),
      l3PaymentSerialized: read(`${pay}.sdjwt`),
      issuerPublicJwk: issuer.publicKey,
      currentTime: NOW,
      expectedL3PaymentAud: NETWORK_AUD,
    });
    expect(networkOutcome.valid).toBe(true);
    expect(networkOutcome.constraints?.satisfied).toBe(true);
  });

  it('rejects settlement when the amount exceeds the mandate cap', async () => {
    const { issuer, pay } = await runAgentSide(20000); // cap below the 27999 price

    const networkOutcome = await verifyPaymentChainAndConstraints({
      l1Serialized: read('l1.sdjwt'),
      l2PaymentSerialized: read(`${pay}.l2.sdjwt`),
      l3PaymentSerialized: read(`${pay}.sdjwt`),
      issuerPublicJwk: issuer.publicKey,
      currentTime: NOW,
      expectedL3PaymentAud: NETWORK_AUD,
    });
    expect(networkOutcome.result.valid).toBe(true); // chain is cryptographically valid
    expect(networkOutcome.valid).toBe(false); // but the amount violates the mandate
    expect(networkOutcome.constraints?.satisfied).toBe(false);
  });
});
