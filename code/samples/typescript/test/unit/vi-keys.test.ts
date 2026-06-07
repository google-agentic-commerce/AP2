/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Tests for the file-backed ES256 key store (src/common/vi/keys.ts) — the
 * shared infrastructure every role server uses to persist + resolve keys across
 * processes. Previously 0% covered. Runs against a throwaway temp TEMP_DB.
 */

import { afterEach, beforeEach, describe, it, expect } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  ROLE_KIDS,
  decodeSdJwt,
  generateEs256Key,
  issueIssuerCredential,
  loadOrCreateViKey,
  loadViPublicJwk,
  verifySdJwtSignature,
} from '../../src/common/vi/index.js';

let TEMP_DB: string;
beforeEach(() => {
  TEMP_DB = fs.mkdtempSync(path.join(os.tmpdir(), 'vi-keys-'));
});
afterEach(() => {
  fs.rmSync(TEMP_DB, { recursive: true, force: true });
});

describe('VI key store', () => {
  it('generates + persists a keypair on first use and reloads it unchanged', async () => {
    const first = await loadOrCreateViKey(TEMP_DB, 'issuer');
    expect(first.publicKey.kty).toBe('EC');
    expect(first.privateKey.d).toBeTruthy(); // private scalar present
    expect(fs.existsSync(path.join(TEMP_DB, 'issuer_key.jwk.json'))).toBe(true);

    const second = await loadOrCreateViKey(TEMP_DB, 'issuer');
    expect(second).toEqual(first); // same jwk + kid, loaded from disk
  });

  it('assigns the documented per-role kids and falls back to <name>-key-1', async () => {
    for (const role of ['issuer', 'user', 'agent', 'merchant', 'psp']) {
      const pair = await loadOrCreateViKey(TEMP_DB, role);
      expect(pair.kid).toBe(ROLE_KIDS[role]);
    }
    const unknown = await loadOrCreateViKey(TEMP_DB, 'auditor');
    expect(unknown.kid).toBe('auditor-key-1');
  });

  it('loadViPublicJwk returns the public jwk after creation and null when missing', async () => {
    expect(loadViPublicJwk(TEMP_DB, 'merchant')).toBeNull();
    const pair = await loadOrCreateViKey(TEMP_DB, 'merchant');
    const pub = loadViPublicJwk(TEMP_DB, 'merchant');
    expect(pub).toEqual(pair.publicKey);
    expect((pub as { d?: string }).d).toBeUndefined(); // no private scalar leaked
  });

  it('loads a legacy keypair (no kid) with the default kid', async () => {
    const { publicKey, privateKey } = await generateEs256Key();
    fs.writeFileSync(path.join(TEMP_DB, 'merchant_key.jwk.json'), JSON.stringify({ publicKey, privateKey }));
    const pair = await loadOrCreateViKey(TEMP_DB, 'merchant');
    expect(pair.kid).toBe('merchant-key-1');
    expect(pair.publicKey).toEqual(publicKey);
  });

  it('a persisted issuer key actually signs a verifiable credential', async () => {
    const issuer = await loadOrCreateViKey(TEMP_DB, 'issuer');
    const user = await loadOrCreateViKey(TEMP_DB, 'user');
    const l1 = await issueIssuerCredential({
      userPublicJwk: user.publicKey,
      issuer,
      sub: 'u',
      iat: 1_900_000_000,
    });
    expect(await verifySdJwtSignature(decodeSdJwt(l1), issuer.publicKey)).toBe(true);
  });
});
