/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * File-backed ES256 keypair store. Each role (user, agent, merchant, psp)
 * persists its keypair as `<name>_key.jwk.json` under a shared TEMP_DB so that
 * separate processes (the agent and each MCP subprocess) can resolve the same
 * public keys and verify each other's signatures.
 */

import fs from 'node:fs';
import path from 'node:path';
import { generateKeyPair, type Es256Jwk, type Es256KeyPair } from './crypto.js';

function keyPath(tempDb: string, name: string): string {
  return path.join(tempDb, `${name}_key.jwk.json`);
}

/** Load the named keypair, generating + persisting it on first use. */
export async function loadOrCreateKeyPair(tempDb: string, name: string): Promise<Es256KeyPair> {
  try {
    return JSON.parse(fs.readFileSync(keyPath(tempDb, name), 'utf-8')) as Es256KeyPair;
  } catch {
    const pair = await generateKeyPair();
    fs.mkdirSync(tempDb, { recursive: true });
    fs.writeFileSync(keyPath(tempDb, name), JSON.stringify(pair));
    return pair;
  }
}

/** Read just the public JWK of a previously persisted keypair (null if absent). */
export function loadPublicJwk(tempDb: string, name: string): Es256Jwk | null {
  try {
    return (JSON.parse(fs.readFileSync(keyPath(tempDb, name), 'utf-8')) as Es256KeyPair).publicKey;
  } catch {
    return null;
  }
}
