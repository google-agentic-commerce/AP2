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
 * TypeScript type declarations for the digitalbazaar VC ecosystem.
 *
 * These libraries are JavaScript-only; these types provide a typed surface
 * for the parts of the API we use.
 */

// -- Ed25519 Key Pair --

export interface Ed25519KeyPairExport {
  id: string;
  type: 'Ed25519VerificationKey2020';
  controller: string;
  publicKeyMultibase: string;
  privateKeyMultibase?: string;
}

export interface Ed25519KeyPairInstance {
  id: string;
  type: string;
  controller: string;
  publicKeyMultibase: string;
  privateKeyMultibase?: string;
  signer(): { sign(params: { data: Uint8Array }): Promise<Uint8Array> };
  verifier(): { verify(params: { data: Uint8Array; signature: Uint8Array }): Promise<boolean> };
  export(options: { publicKey?: boolean; privateKey?: boolean }): Promise<Ed25519KeyPairExport>;
}

// -- Signature Suite --

export interface Ed25519Signature2020Instance {
  verificationMethod: string;
}

// -- Verifiable Credential --

export interface VerifiableCredential {
  '@context': string[];
  id?: string;
  type: string[];
  issuer: string | { id: string; [key: string]: unknown };
  issuanceDate: string;
  expirationDate?: string;
  credentialSubject: CredentialSubject | CredentialSubject[];
  proof?: Proof;
  [key: string]: unknown;
}

export interface CredentialSubject {
  id?: string;
  [key: string]: unknown;
}

export interface Proof {
  type: string;
  created: string;
  verificationMethod: string;
  proofPurpose: string;
  proofValue: string;
  [key: string]: unknown;
}

// -- Verifiable Presentation --

export interface VerifiablePresentation {
  '@context': string[];
  type: string[];
  verifiableCredential?: VerifiableCredential[];
  holder?: string;
  id?: string;
  proof?: Proof;
}

// -- Verification Results --

export interface VerifyCredentialResult {
  verified: boolean;
  results?: Array<{ verified: boolean; error?: Error }>;
  error?: Error;
}

export interface VerifyPresentationResult {
  verified: boolean;
  presentationResult?: { verified: boolean; error?: Error };
  credentialResults?: VerifyCredentialResult[];
  error?: Error;
}

// -- Document Loader --

export interface DocumentLoaderResult {
  contextUrl: string | null;
  documentUrl: string;
  document: unknown;
}

export type DocumentLoader = (url: string) => Promise<DocumentLoaderResult>;
