/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Plain ES256 compact JWS (JWT) helpers — distinct from the SD-JWT mandate
 * format. Used for artifacts that are signed but not selectively disclosed:
 * the merchant-signed checkout JWT and the PSP-signed payment receipt.
 *
 * Built directly on the ES256 signer/verifier from crypto.ts (ECDSA P-256),
 * producing a standard `<base64url header>.<base64url payload>.<base64url sig>`
 * compact JWS.
 */

import { ALG, makeSigner, makeVerifier, type Es256Jwk } from './crypto.js';

function b64urlJson(value: unknown): string {
  return Buffer.from(JSON.stringify(value)).toString('base64url');
}

/** Sign a payload as a compact ES256 JWS. */
export async function signJwtEs256(
  payload: Record<string, unknown>,
  privateJwk: Es256Jwk,
): Promise<string> {
  const signer = await makeSigner(privateJwk);
  const header = { alg: ALG, typ: 'JWT' };
  const signingInput = `${b64urlJson(header)}.${b64urlJson(payload)}`;
  const signature = await signer(signingInput);
  return `${signingInput}.${signature}`;
}

/**
 * Verify a compact ES256 JWS and return its payload.
 * @throws if the token is malformed or the signature does not verify.
 */
export async function verifyJwtEs256(
  compact: string,
  publicJwk: Es256Jwk,
): Promise<Record<string, unknown>> {
  const parts = compact.split('.');
  if (parts.length !== 3) {
    throw new Error('malformed JWT: expected three dot-separated segments');
  }
  const [headerB64, payloadB64, signature] = parts;
  const verifier = await makeVerifier(publicJwk);
  const ok = await verifier(`${headerB64}.${payloadB64}`, signature);
  if (!ok) {
    throw new Error('invalid JWT signature');
  }
  return JSON.parse(Buffer.from(payloadB64, 'base64url').toString('utf-8')) as Record<
    string,
    unknown
  >;
}
