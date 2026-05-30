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
 * Custom document loader for VC operations.
 *
 * Combines the built-in credential/security contexts from the digitalbazaar
 * packages with a local store for issuer controller documents and
 * verification method resolution. This avoids any network fetches.
 */
import type { DocumentLoader, DocumentLoaderResult } from './types.js';

// @ts-expect-error - JS-only module without type declarations
import { contexts as credentialContexts } from '@digitalbazaar/credentials-context';
// @ts-expect-error - JS-only module without type declarations
import { contexts as securityContexts } from '@digitalbazaar/security-context';
// @ts-expect-error - JS-only module without type declarations
import ed25519Context from 'ed25519-signature-2020-context';
import { AP2_CONTEXT_URL, ap2PaymentContext } from './ap2-context.js';

/**
 * In-memory store for dynamically registered documents (controller docs,
 * verification methods). Populated by the key manager when keys are created.
 */
const localDocuments = new Map<string, unknown>();

/** Register a document so the loader can resolve it by URL. */
export function registerDocument(url: string, document: unknown): void {
  localDocuments.set(url, document);
}

/** Remove a registered document. */
export function unregisterDocument(url: string): void {
  localDocuments.delete(url);
}

/** Clear all registered documents (useful for testing). */
export function clearDocuments(): void {
  localDocuments.clear();
}

/**
 * Build a static context map from the bundled packages.
 */
function buildStaticContexts(): Map<string, unknown> {
  const contexts = new Map<string, unknown>();

  // W3C Credentials contexts (v1, v2)
  for (const [url, doc] of credentialContexts as Map<string, unknown>) {
    contexts.set(url, doc);
  }

  // Security contexts (v1, v2)
  for (const [url, doc] of securityContexts as Map<string, unknown>) {
    contexts.set(url, doc);
  }

  // Ed25519 2020 suite context
  for (const [url, doc] of ed25519Context.contexts as Map<string, unknown>) {
    contexts.set(url, doc);
  }

  // AP2 custom payment context
  contexts.set(AP2_CONTEXT_URL, ap2PaymentContext);

  return contexts;
}

const staticContexts = buildStaticContexts();

/**
 * Document loader that resolves:
 * 1. Static W3C/security/Ed25519 contexts from bundled packages
 * 2. Dynamically registered local documents (controller docs, keys)
 *
 * Never makes network requests.
 */
export const documentLoader: DocumentLoader = async (
  url: string
): Promise<DocumentLoaderResult> => {
  // Check static contexts first
  const staticDoc = staticContexts.get(url);
  if (staticDoc !== undefined) {
    return {
      contextUrl: null,
      documentUrl: url,
      document: staticDoc,
    };
  }

  // Check dynamically registered documents
  const localDoc = localDocuments.get(url);
  if (localDoc !== undefined) {
    return {
      contextUrl: null,
      documentUrl: url,
      document: localDoc,
    };
  }

  throw new Error(
    `Document loader unable to load URL "${url}". ` +
    'Ensure the document is registered or a known context.'
  );
};
