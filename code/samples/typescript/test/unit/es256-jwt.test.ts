/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Proves the plain ES256 JWS helpers used for the merchant checkout JWT and
 * the PSP payment receipt: sign, verify, and reject tampered / wrong-key tokens.
 */

import { describe, it, expect } from 'vitest';
import { generateKeyPair, signJwtEs256, verifyJwtEs256 } from '../../src/common/sdjwt/index.js';

describe('ES256 plain JWT (checkout JWT / PSP receipt)', () => {
  it('signs and verifies a compact ES256 JWS', async () => {
    const key = await generateKeyPair();
    const jwt = await signJwtEs256({ iss: 'merchant-agent', amount: 15000 }, key.privateKey);
    expect(jwt.split('.').length).toBe(3);
    const payload = await verifyJwtEs256(jwt, key.publicKey);
    expect(payload.iss).toBe('merchant-agent');
    expect(payload.amount).toBe(15000);
  });

  it('rejects a token verified with the wrong key', async () => {
    const signer = await generateKeyPair();
    const other = await generateKeyPair();
    const jwt = await signJwtEs256({ iss: 'merchant-payment-processor' }, signer.privateKey);
    await expect(verifyJwtEs256(jwt, other.publicKey)).rejects.toThrow();
  });

  it('rejects a tampered payload', async () => {
    const key = await generateKeyPair();
    const jwt = await signJwtEs256({ status: 'settled' }, key.privateKey);
    const [h, , s] = jwt.split('.');
    const forgedPayload = Buffer.from(JSON.stringify({ status: 'refunded' })).toString('base64url');
    const tampered = `${h}.${forgedPayload}.${s}`;
    await expect(verifyJwtEs256(tampered, key.publicKey)).rejects.toThrow();
  });
});
