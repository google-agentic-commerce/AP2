/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Spike: proves the @sd-jwt/core mandate primitives do real SD-JWT with
 * selective disclosure + ES256 + cnf.jwk key binding (KB-SD-JWT) — the
 * AP2 v0.2 open->closed delegation hop. Runs without Gemini / any server.
 */

import { describe, it, expect } from 'vitest';
import {
  generateKeyPair,
  issueOpenMandate,
  presentClosedMandate,
  verifyMandate,
} from '../../src/common/sdjwt/index.js';

describe('SD-JWT mandate primitives (spike)', () => {
  it('issues an open mandate as a real SD-JWT with selective disclosure', async () => {
    const issuer = await generateKeyPair(); // user device key
    const holder = await generateKeyPair(); // agent key

    const sdjwt = await issueOpenMandate({
      claims: {
        merchant: 'acme-shoes',
        amount_cap: 20000, // minor units
        currency: 'USD',
        item: 'supershoe-gold-9',
      },
      disclosable: ['amount_cap', 'item'],
      issuerPrivateJwk: issuer.privateKey,
      holderPublicJwk: holder.publicKey,
    });

    // Compact SD-JWT form: <jwt>~<disclosure>~...~  (tilde separated)
    expect(sdjwt.split('~').length).toBeGreaterThan(1);
  });

  it('verifies the issuer signature (no key binding on the bare SD-JWT)', async () => {
    const issuer = await generateKeyPair();
    const holder = await generateKeyPair();

    const sdjwt = await issueOpenMandate({
      claims: { merchant: 'acme-shoes', amount_cap: 20000, item: 'x' },
      disclosable: ['amount_cap', 'item'],
      issuerPrivateJwk: issuer.privateKey,
      holderPublicJwk: holder.publicKey,
    });

    const result = await verifyMandate({
      mandateSdJwt: sdjwt,
      issuerPublicJwk: issuer.publicKey,
    });

    expect(result.payload.merchant).toBe('acme-shoes');
    // cnf must survive (never disclosed) so the next hop can key-bind.
    expect((result.payload.cnf as { jwk?: unknown }).jwk).toBeDefined();
    expect(result.keyBound).toBe(false);
  });

  it('presents a closed mandate (KB-SD-JWT) and verifies the key binding', async () => {
    const issuer = await generateKeyPair();
    const holder = await generateKeyPair();
    const nonce = 'verifier-nonce-123';
    const audience = 'credentials-provider';

    const open = await issueOpenMandate({
      claims: { merchant: 'acme-shoes', amount_cap: 20000, item: 'supershoe' },
      disclosable: ['amount_cap', 'item'],
      issuerPrivateJwk: issuer.privateKey,
      holderPublicJwk: holder.publicKey,
    });

    const closed = await presentClosedMandate({
      openMandateSdJwt: open,
      disclose: ['amount_cap'], // reveal only the cap, keep `item` hidden
      holderPrivateJwk: holder.privateKey,
      nonce,
      audience,
    });

    const verified = await verifyMandate({
      mandateSdJwt: closed,
      issuerPublicJwk: issuer.publicKey,
      nonce,
    });

    expect(verified.keyBound).toBe(true);
    // selective disclosure: amount_cap revealed, item withheld
    expect(verified.payload.amount_cap).toBe(20000);
    expect(verified.payload.item).toBeUndefined();
    expect(verified.payload.merchant).toBe('acme-shoes'); // always-disclosed
  });

  it('rejects key binding signed by the wrong holder key', async () => {
    const issuer = await generateKeyPair();
    const holder = await generateKeyPair();
    const attacker = await generateKeyPair();

    const open = await issueOpenMandate({
      claims: { merchant: 'acme', amount_cap: 100, item: 'y' },
      disclosable: ['amount_cap'],
      issuerPrivateJwk: issuer.privateKey,
      holderPublicJwk: holder.publicKey, // cnf binds the real holder
    });

    // Attacker presents with their own key instead of the cnf-bound holder key.
    const forged = await presentClosedMandate({
      openMandateSdJwt: open,
      disclose: ['amount_cap'],
      holderPrivateJwk: attacker.privateKey,
      nonce: 'n',
      audience: 'credentials-provider',
    });

    await expect(
      verifyMandate({ mandateSdJwt: forged, issuerPublicJwk: issuer.publicKey, nonce: 'n' }),
    ).rejects.toThrow();
  });
});
