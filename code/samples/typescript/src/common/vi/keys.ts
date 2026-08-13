/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * File-backed ES256 (P-256) JWK key store for the Verifiable Intent roles.
 * Each role (issuer, user, agent, merchant, psp) persists its keypair as
 * `<name>_key.jwk.json` under a shared TEMP_DB so the agent and each MCP
 * subprocess resolve the same public keys and can verify each other's
 * signatures. Keys carry a stable `kid` matching the Python reference, used
 * for the SD-JWT header `kid` and the `cnf.jwk` key-binding (RFC 7800).
 */

import fs from 'node:fs';
import path from 'node:path';
import { generateEs256Key, type Es256Jwk } from 'verifiable-intent-js';

export interface ViKeyPair {
  publicKey: Es256Jwk;
  privateKey: Es256Jwk;
  kid: string;
}

/** Stable per-role key ids, mirroring python/examples/helpers.py. */
export const ROLE_KIDS: Record<string, string> = {
  issuer: 'mastercard-issuer-key-1',
  user: 'user-device-key-1',
  agent: 'agent-key-1',
  merchant: 'merchant-key-1',
  psp: 'psp-key-1',
};

function keyPath(tempDb: string, name: string): string {
  return path.join(tempDb, `${name}_key.jwk.json`);
}

function kidFor(name: string): string {
  return ROLE_KIDS[name] ?? `${name}-key-1`;
}

/** Load the named keypair, generating + persisting it (with a stable kid) on first use. */
export async function loadOrCreateViKey(tempDb: string, name: string): Promise<ViKeyPair> {
  try {
    const raw = JSON.parse(fs.readFileSync(keyPath(tempDb, name), 'utf-8')) as Partial<ViKeyPair>;
    if (raw.publicKey && raw.privateKey) {
      return { publicKey: raw.publicKey, privateKey: raw.privateKey, kid: raw.kid ?? kidFor(name) };
    }
  } catch {
    /* fall through to generate */
  }
  const { publicKey, privateKey } = await generateEs256Key();
  const pair: ViKeyPair = { publicKey, privateKey, kid: kidFor(name) };
  fs.mkdirSync(tempDb, { recursive: true });
  fs.writeFileSync(keyPath(tempDb, name), JSON.stringify(pair));
  return pair;
}

/** Read just the public JWK of a previously persisted keypair (null if absent). */
export function loadViPublicJwk(tempDb: string, name: string): Es256Jwk | null {
  try {
    return (JSON.parse(fs.readFileSync(keyPath(tempDb, name), 'utf-8')) as ViKeyPair).publicKey;
  } catch {
    return null;
  }
}
