/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Real SD-JWT mandate primitives (replacing the earlier stubs), built on
 * @sd-jwt/core. This mirrors the Python AP2 v0.2 reference at
 * code/sdk/python/ap2/sdk/sdjwt/ (sd_jwt.py + kb_sd_jwt.py):
 *
 *   - issueOpenMandate:   issuer signs an SD-JWT with selectively-disclosable
 *                         claims and a `cnf.jwk` holder-binding key (RFC 7800).
 *   - presentClosedMandate: the holder produces a KB-SD-JWT (Key-Binding JWT)
 *                         proving possession of the `cnf` key, bound to a
 *                         nonce + audience (the open->closed delegation hop).
 *   - verifyMandate:      verifies the issuer signature and, when a KB-JWT is
 *                         present, verifies it against the `cnf.jwk` extracted
 *                         from the issuer payload — the same cnf-walk the
 *                         Python chain verifier performs.
 */

import { SDJwtInstance } from '@sd-jwt/core';
import type { DisclosureFrame, KbVerifier, PresentationFrame } from '@sd-jwt/types';
import {
  ALG,
  hasher,
  saltGenerator,
  makeSigner,
  makeVerifier,
  type Es256Jwk,
} from './crypto.js';

export interface OpenMandateInput {
  /** The mandate body (constraints, expiry, description, etc.). */
  claims: Record<string, unknown>;
  /** Top-level claim keys to make selectively disclosable. */
  disclosable: string[];
  /** Issuer (e.g. user device) private key that signs the mandate. */
  issuerPrivateJwk: Es256Jwk;
  /** Holder (e.g. agent) public key bound into `cnf.jwk` for key binding. */
  holderPublicJwk: Es256Jwk;
}

/** Issue an open mandate as an SD-JWT with a `cnf.jwk` holder-binding key. */
export async function issueOpenMandate(input: OpenMandateInput): Promise<string> {
  const signer = await makeSigner(input.issuerPrivateJwk);
  const sdjwt = new SDJwtInstance({
    signer,
    signAlg: ALG,
    hasher,
    hashAlg: 'sha-256',
    saltGenerator,
  });
  const payload = {
    ...input.claims,
    // cnf is NEVER selectively disclosed — it must always be present so a
    // verifier can key-bind the next hop (RFC 7800).
    cnf: { jwk: input.holderPublicJwk },
  };
  const disclosureFrame = { _sd: input.disclosable } as DisclosureFrame<typeof payload>;
  return sdjwt.issue(payload, disclosureFrame);
}

export interface PresentInput {
  /** The open mandate SD-JWT to present. */
  openMandateSdJwt: string;
  /** Disclosable claim keys to reveal in this presentation. */
  disclose: string[];
  /** Holder private key — MUST correspond to the SD-JWT's `cnf.jwk`. */
  holderPrivateJwk: Es256Jwk;
  /** Replay-protection nonce supplied by the verifier. */
  nonce: string;
  /** Intended audience of the presentation. */
  audience: string;
  /** Seconds since epoch for the KB-JWT `iat`. Defaults to now. */
  issuedAt?: number;
}

/** Produce a KB-SD-JWT: a holder-bound presentation of the open mandate. */
export async function presentClosedMandate(input: PresentInput): Promise<string> {
  const kbSigner = await makeSigner(input.holderPrivateJwk);
  const sdjwt = new SDJwtInstance({
    hasher,
    hashAlg: 'sha-256',
    saltGenerator,
    kbSigner,
    kbSignAlg: ALG,
  });
  const presentationFrame = Object.fromEntries(
    input.disclose.map((k) => [k, true]),
  ) as PresentationFrame<Record<string, unknown>>;
  return sdjwt.present(input.openMandateSdJwt, presentationFrame, {
    kb: {
      payload: {
        iat: input.issuedAt ?? Math.floor(Date.now() / 1000),
        aud: input.audience,
        nonce: input.nonce,
      },
    },
  });
}

export interface VerifyInput {
  mandateSdJwt: string;
  /** Issuer public key to check the SD-JWT signature. */
  issuerPublicJwk: Es256Jwk;
  /** Required if the presentation carries a KB-JWT. */
  nonce?: string;
}

export interface VerifyResult {
  payload: Record<string, unknown>;
  /** True when a valid Key-Binding JWT was verified against `cnf.jwk`. */
  keyBound: boolean;
}

/** Verify the issuer signature and, if present, the KB-JWT against cnf.jwk. */
export async function verifyMandate(input: VerifyInput): Promise<VerifyResult> {
  const verifier = await makeVerifier(input.issuerPublicJwk);

  // Decode first to pull the holder key out of `cnf.jwk` — exactly what the
  // Python chain verifier does to resolve each hop's key.
  const decodeInst = new SDJwtInstance({ hasher, hashAlg: 'sha-256' });
  const decoded = await decodeInst.decode(input.mandateSdJwt);
  const issuerPayload = (decoded.jwt?.payload ?? {}) as Record<string, unknown>;
  const cnf = issuerPayload.cnf as { jwk?: Es256Jwk } | undefined;

  let kbVerifier: KbVerifier | undefined;
  if (cnf?.jwk) {
    const holderVerify = await makeVerifier(cnf.jwk);
    kbVerifier = (data: string, sig: string) => holderVerify(data, sig);
  }

  const sdjwt = new SDJwtInstance({
    hasher,
    hashAlg: 'sha-256',
    verifier,
    kbVerifier,
  });

  const result = await sdjwt.verify(
    input.mandateSdJwt,
    input.nonce ? { keyBindingNonce: input.nonce } : undefined,
  );

  return {
    payload: result.payload as Record<string, unknown>,
    keyBound: 'kb' in result && result.kb !== undefined,
  };
}

export { generateKeyPair } from './crypto.js';
