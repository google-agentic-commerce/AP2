/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Covers the two fidelity upgrades:
 *  - constraint checker (amount + merchant allowlist)
 *  - hash binding: a payment presentation bound to checkout A must NOT verify
 *    under checkout B's hash (replay protection).
 */

import { describe, it, expect } from 'vitest';
import {
  checkConstraints,
  generateKeyPair,
  issueOpenMandate,
  presentClosedMandate,
  verifyMandate,
} from '../../src/common/sdjwt/index.js';

describe('constraint checker', () => {
  it('passes when price within cap and merchant allowed', () => {
    const r = checkConstraints(
      { price: 150, currency: 'USD', merchant: 'acme' },
      { priceCap: 200, currency: 'USD', allowedMerchants: ['acme', 'globex'] },
    );
    expect(r.meetsConstraints).toBe(true);
    expect(r.violations).toEqual([]);
  });

  it('fails when price exceeds the cap', () => {
    const r = checkConstraints({ price: 250 }, { priceCap: 200 });
    expect(r.meetsConstraints).toBe(false);
    expect(r.violations[0]).toContain('exceeds cap');
  });

  it('fails when merchant not in allowlist', () => {
    const r = checkConstraints(
      { price: 10, merchant: 'sketchy' },
      { priceCap: 100, allowedMerchants: ['acme'] },
    );
    expect(r.meetsConstraints).toBe(false);
    expect(r.violations[0]).toContain('not in allowlist');
  });

  it('ignores merchant when the mandate does not restrict merchants', () => {
    const r = checkConstraints({ price: 10, merchant: 'anyone' }, { priceCap: 100 });
    expect(r.meetsConstraints).toBe(true);
  });
});

describe('hash binding (replay protection)', () => {
  it('rejects a payment presentation under a different checkout hash', async () => {
    const user = await generateKeyPair(); // issuer
    const agent = await generateKeyPair(); // holder (cnf)
    const checkoutHashA = 'checkout-A-hash';
    const checkoutHashB = 'checkout-B-hash';

    const openPayment = await issueOpenMandate({
      claims: { kind: 'open_payment', constraint_price_cap: 200 },
      disclosable: [],
      issuerPrivateJwk: user.privateKey,
      holderPublicJwk: agent.publicKey,
    });

    // Agent presents the payment mandate bound to checkout A.
    const closedForA = await presentClosedMandate({
      openMandateSdJwt: openPayment,
      disclose: [],
      holderPrivateJwk: agent.privateKey,
      nonce: checkoutHashA,
      audience: 'credentials-provider',
    });

    // Verifying under checkout A's hash succeeds and is key-bound.
    const okA = await verifyMandate({
      mandateSdJwt: closedForA,
      issuerPublicJwk: user.publicKey,
      nonce: checkoutHashA,
    });
    expect(okA.keyBound).toBe(true);

    // The same presentation must NOT verify under checkout B's hash.
    await expect(
      verifyMandate({ mandateSdJwt: closedForA, issuerPublicJwk: user.publicKey, nonce: checkoutHashB }),
    ).rejects.toThrow();
  });
});
