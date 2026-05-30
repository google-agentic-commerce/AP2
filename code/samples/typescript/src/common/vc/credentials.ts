/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * W3C Verifiable Credential issuance and verification utilities.
 *
 * Uses @digitalbazaar/vc with Ed25519Signature2020 to issue and verify
 * payment credential VCs within the AP2 multi-agent system.
 */
import { v4 as uuidv4 } from 'uuid';
// @ts-expect-error - JS-only module without type declarations
import * as vc from '@digitalbazaar/vc';
// @ts-expect-error - JS-only module without type declarations
import { Ed25519Signature2020 } from '@digitalbazaar/ed25519-signature-2020';
import { getKeyManager } from './key-manager.js';
import { documentLoader } from './document-loader.js';
import { AP2_CONTEXT_URL } from './ap2-context.js';
import type {
  VerifiableCredential,
  VerifiablePresentation,
  VerifyCredentialResult,
  VerifyPresentationResult,
} from './types.js';

const CREDENTIALS_CONTEXT_V1 = 'https://www.w3.org/2018/credentials/v1';
const ED25519_2020_CONTEXT = 'https://w3id.org/security/suites/ed25519-2020/v1';

/**
 * Build a signing suite from the current key manager state.
 */
function buildSigningSuite(): InstanceType<typeof Ed25519Signature2020> {
  const { keyPair } = getKeyManager();
  return new Ed25519Signature2020({ key: keyPair });
}

/**
 * Build a verification suite (no private key needed).
 */
function buildVerificationSuite(): InstanceType<typeof Ed25519Signature2020> {
  return new Ed25519Signature2020();
}

// -- Credential Issuance --

export interface IssuePaymentCredentialOptions {
  /** The subject holding the credential (e.g., user email or DID). */
  subjectId?: string;
  /** The payment method data to embed in the credential. */
  paymentMethod: Record<string, unknown>;
  /** The payment mandate ID this credential is bound to. */
  paymentMandateId?: string;
}

/**
 * Issue a W3C Verifiable Credential for a payment method.
 *
 * The credential embeds the payment method data as the credentialSubject
 * and is signed by the credentials-provider's Ed25519 key.
 *
 * @returns A signed VerifiableCredential object.
 */
export async function issuePaymentCredential(
  options: IssuePaymentCredentialOptions
): Promise<VerifiableCredential> {
  const { paymentMethod, subjectId, paymentMandateId } = options;
  const { issuerId } = getKeyManager();
  const suite = buildSigningSuite();

  const credential: Record<string, unknown> = {
    '@context': [CREDENTIALS_CONTEXT_V1, ED25519_2020_CONTEXT, AP2_CONTEXT_URL],
    id: `urn:uuid:${uuidv4()}`,
    type: ['VerifiableCredential', 'PaymentCredential'],
    issuer: issuerId,
    issuanceDate: new Date().toISOString(),
    credentialSubject: {
      ...(subjectId ? { id: subjectId } : {}),
      type: 'PaymentMethod',
      ...paymentMethod,
      ...(paymentMandateId ? { paymentMandateId } : {}),
    },
  };

  const signedCredential: VerifiableCredential = await vc.issue({
    credential,
    suite,
    documentLoader,
  });

  return signedCredential;
}

// -- Credential Verification --

/**
 * Verify a W3C Verifiable Credential.
 *
 * Checks the cryptographic signature and validates the credential structure.
 *
 * @returns The verification result with `verified: true/false`.
 */
export async function verifyCredential(
  credential: VerifiableCredential
): Promise<VerifyCredentialResult> {
  const suite = buildVerificationSuite();

  const result: VerifyCredentialResult = await vc.verifyCredential({
    credential,
    suite,
    documentLoader,
  });

  return result;
}

/**
 * Verify a credential and extract the credentialSubject if valid.
 *
 * @returns The credential subject data, or throws if verification fails.
 */
export async function verifyAndExtractSubject(
  credential: VerifiableCredential
): Promise<Record<string, unknown>> {
  const result = await verifyCredential(credential);

  if (!result.verified) {
    const errorMsg = result.error?.message ?? 'Unknown verification error';
    throw new Error(`Credential verification failed: ${errorMsg}`);
  }

  const subject = credential.credentialSubject;
  if (Array.isArray(subject)) {
    return subject[0] as Record<string, unknown>;
  }
  return subject as Record<string, unknown>;
}

// -- Verifiable Presentations --

/**
 * Create an unsigned Verifiable Presentation wrapping one or more VCs.
 *
 * Unsigned presentations are sufficient for the AP2 inter-agent flow
 * because the A2A transport layer provides message authenticity.
 */
export function createPresentation(
  credentials: VerifiableCredential | VerifiableCredential[],
  holder?: string
): VerifiablePresentation {
  return vc.createPresentation({
    verifiableCredential: credentials,
    holder,
    version: 1.0,
  });
}

/**
 * Verify an unsigned Verifiable Presentation and all contained credentials.
 */
export async function verifyPresentation(
  presentation: VerifiablePresentation
): Promise<VerifyPresentationResult> {
  const suite = buildVerificationSuite();

  return vc.verify({
    presentation,
    suite,
    unsignedPresentation: true,
    documentLoader,
  });
}
