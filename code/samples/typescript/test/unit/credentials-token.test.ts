/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Phase 2: proves the credentials-provider payment token round-trips through
 * SD-JWT (replacing the W3C VC token). createToken issues an ES256 SD-JWT
 * credential; verifyToken cryptographically verifies it and reconstructs the
 * payment method. Runs without any server.
 */

import { describe, it, expect, beforeAll } from 'vitest';
import {
  initIssuerKey,
  createToken,
  updateToken,
  verifyToken,
} from '../../src/roles/credentials-provider-agent/account-manager.js';

const EMAIL = 'bugsbunny@gmail.com';
const ALIAS = 'American Express ending in 4444';
const MANDATE_ID = 'pm_test_123';

describe('credentials-provider SD-JWT token (Phase 2)', () => {
  beforeAll(async () => {
    await initIssuerKey();
  });

  it('issues an SD-JWT token (compact form, not JSON-LD VC)', async () => {
    const token = await createToken(EMAIL, ALIAS);
    // SD-JWT compact form is tilde-separated; a W3C VC would be a JSON object.
    expect(token).toContain('~');
    expect(token.trimStart().startsWith('{')).toBe(false);
  });

  it('round-trips the payment method through createToken -> verifyToken', async () => {
    const token = await createToken(EMAIL, ALIAS);
    updateToken(token, MANDATE_ID);

    const pm = await verifyToken(token, MANDATE_ID);
    expect(pm).not.toBeNull();
    expect(pm?.alias).toBe(ALIAS);
    expect(pm?.type).toBe('CARD'); // restored from payment_method_type
    // selectively-disclosable sensitive fields survive a full presentation
    expect((pm as Record<string, unknown>).token).toBe('1111000000000000');
    expect((pm as Record<string, unknown>).cryptogram).toBe('fake_cryptogram_abc123');
    // credential metadata must NOT leak into the reconstructed payment method
    expect((pm as Record<string, unknown>).sub).toBeUndefined();
    expect((pm as Record<string, unknown>).cnf).toBeUndefined();
    expect((pm as Record<string, unknown>).payment_method_alias).toBeUndefined();
  });

  it('rejects a token whose mandate binding does not match', async () => {
    const token = await createToken(EMAIL, ALIAS);
    updateToken(token, MANDATE_ID);
    await expect(verifyToken(token, 'wrong_mandate')).rejects.toThrow('Invalid token');
  });

  it('rejects an unknown token', async () => {
    await expect(verifyToken('not-a-real-token', MANDATE_ID)).rejects.toThrow('Invalid token');
  });
});
// SD-JWT signature/key-binding forgery is covered at the crypto layer in
// sdjwt-mandate.test.ts ("rejects key binding signed by the wrong holder key").
