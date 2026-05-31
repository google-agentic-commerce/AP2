/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * ES256 crypto primitives for SD-JWT, backed by @sd-jwt/crypto-nodejs
 * (WebCrypto under the hood). AP2 v0.2 mandates ES256 (ECDSA P-256) for
 * mandate SD-JWTs, so this is the single algorithm used across issue,
 * present (key-binding), and verify.
 */

import { ES256, digest, generateSalt } from '@sd-jwt/crypto-nodejs';
import type { Hasher, SaltGenerator, Signer, Verifier } from '@sd-jwt/types';

/** A P-256 JSON Web Key (public or private). */
export type Es256Jwk = JsonWebKey;

export interface Es256KeyPair {
  publicKey: Es256Jwk;
  privateKey: Es256Jwk;
}

export const ALG = ES256.alg; // "ES256"

/** Hasher (sha-256) compatible with @sd-jwt SDJwtInstance config. */
export const hasher: Hasher = (data, alg) => digest(data, alg);

/** Salt generator for selective-disclosure commitments. */
export const saltGenerator: SaltGenerator = (length: number) => generateSalt(length);

export async function generateKeyPair(): Promise<Es256KeyPair> {
  return ES256.generateKeyPair();
}

export async function makeSigner(privateJwk: Es256Jwk): Promise<Signer> {
  return ES256.getSigner(privateJwk);
}

export async function makeVerifier(publicJwk: Es256Jwk): Promise<Verifier> {
  return ES256.getVerifier(publicJwk);
}
