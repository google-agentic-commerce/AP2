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
 * Key pair management for VC operations.
 *
 * Generates Ed25519 key pairs and registers the corresponding controller
 * documents and verification methods with the document loader so that
 * issued credentials can be verified offline.
 */
// @ts-expect-error - JS-only module without type declarations
import { Ed25519VerificationKey2020 } from '@digitalbazaar/ed25519-verification-key-2020';
import type { Ed25519KeyPairInstance, Ed25519KeyPairExport } from './types.js';
import { registerDocument } from './document-loader.js';

/** Default issuer DID-like identifier for the credentials provider. */
const DEFAULT_ISSUER_ID = 'https://ap2.example/issuers/credentials-provider';

interface KeyManagerOptions {
  /** The issuer identifier (URL or DID). */
  issuerId?: string;
}

interface KeyManagerState {
  keyPair: Ed25519KeyPairInstance;
  issuerId: string;
  verificationMethodId: string;
}

let _state: KeyManagerState | null = null;

/**
 * Initialize the key manager: generate (or load) an Ed25519 key pair and
 * register the controller document + verification method with the
 * document loader.
 *
 * This should be called once at application startup.
 */
export async function initKeyManager(
  options: KeyManagerOptions = {}
): Promise<KeyManagerState> {
  const issuerId = options.issuerId ?? DEFAULT_ISSUER_ID;

  // Generate a new key pair with the issuer as the controller
  const keyPair: Ed25519KeyPairInstance = await Ed25519VerificationKey2020.generate({
    controller: issuerId,
  });

  // The key's id is auto-assigned as `${controller}#${keyFingerprint}`
  const verificationMethodId = keyPair.id;

  // Register the controller document so the document loader can resolve it.
  // This is what verifiers look up to find the public key.
  // The controller document must use security/v2 context because it defines
  // assertionMethod, authentication, and verificationMethod terms.
  const controllerDoc = {
    '@context': [
      'https://w3id.org/security/v2',
      'https://w3id.org/security/suites/ed25519-2020/v1',
    ],
    id: issuerId,
    assertionMethod: [verificationMethodId],
    authentication: [verificationMethodId],
    verificationMethod: [
      {
        id: verificationMethodId,
        type: 'Ed25519VerificationKey2020',
        controller: issuerId,
        publicKeyMultibase: keyPair.publicKeyMultibase,
      },
    ],
  };

  registerDocument(issuerId, controllerDoc);

  // Also register the verification method URL directly so the signature
  // verifier can dereference it by its full id.
  registerDocument(verificationMethodId, {
    '@context': 'https://w3id.org/security/suites/ed25519-2020/v1',
    id: verificationMethodId,
    type: 'Ed25519VerificationKey2020',
    controller: issuerId,
    publicKeyMultibase: keyPair.publicKeyMultibase,
  });

  _state = { keyPair, issuerId, verificationMethodId };
  return _state;
}

/** Get the current key manager state. Throws if not initialized. */
export function getKeyManager(): KeyManagerState {
  if (!_state) {
    throw new Error(
      'Key manager not initialized. Call initKeyManager() first.'
    );
  }
  return _state;
}

/** Export the key pair (public key only by default). */
export async function exportKeyPair(
  options: { includePrivateKey?: boolean } = {}
): Promise<Ed25519KeyPairExport> {
  const { keyPair } = getKeyManager();
  return keyPair.export({
    publicKey: true,
    privateKey: options.includePrivateKey ?? false,
  });
}

/** Reset the key manager (useful for testing). */
export function resetKeyManager(): void {
  _state = null;
}
