/**
 * SD-JWT decoder utility.
 *
 * Decodes SD-JWT tokens (IETF SD-JWT spec) into their component parts:
 *   <issuer_jwt>~<disclosure_1>~<disclosure_2>~...~<kb_jwt>
 *
 * Also decodes `~~`-joined dSD-JWT delegation chains
 * (draft-gco-oauth-delegate-sd-jwt-00 §6), where each hop is itself a full
 * SD-JWT of the form above: `<hop_0>~~<hop_1>~~...~~<hop_n>`.
 *
 * Ported from ap2/internal_skills/format_mandate_logs/scripts/format_logs.py.
 * Pure client-side, no network calls.
 */

export interface DecodedJwt {
  header: Record<string, unknown>;
  payload: Record<string, unknown>;
  signature: string;
  raw: string;
}

export interface DecodedDisclosure {
  salt: string;
  /** Present when disclosure is [salt, key, value]; absent for array items [salt, value] */
  key?: string;
  value: unknown;
  /** base64url SHA-256 digest of the raw disclosure string */
  digest: string;
  /** The raw base64url encoded disclosure string */
  raw: string;
}

export interface DecodedSdJwt {
  issuerJwt: DecodedJwtWithDiagnostics;
  disclosures: DecodedDisclosure[];
  kbJwt?: DecodedJwtWithDiagnostics;
  /**
   * Present when the decoded token was a `~~`-joined dSD-JWT delegation
   * chain: one entry per hop, in order. `issuerJwt`/`disclosures`/`kbJwt`
   * above always describe hop 0, so existing single-hop callers keep
   * working unchanged for both single tokens and chains.
   */
  hops?: DecodedSdJwt[];
}

/** Decode base64url (with or without padding) to a UTF-8 string. */
export function b64urlToString(s: string): string {
  const padded = s + '='.repeat((4 - (s.length % 4)) % 4);
  const base64 = padded.replace(/-/g, '+').replace(/_/g, '/');
  // atob returns a binary string; convert bytes back to UTF-8.
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new TextDecoder('utf-8').decode(bytes);
}

/** SHA-256 digest of a string returned as base64url (no padding). */
async function sha256Base64Url(input: string): Promise<string> {
  const data = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest('SHA-256', data);
  const bytes = new Uint8Array(digest);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/**
 * Extended decoded JWT shape used when payload JSON fails to parse (e.g. the
 * token was truncated or contained a stray character from an LLM emission).
 * When `payloadError` is set, `payload` is empty and the caller should fall
 * back to `rawPayloadString` for display.
 */
export interface DecodedJwtWithDiagnostics extends DecodedJwt {
  /** Raw decoded UTF-8 string of the payload section (before JSON.parse). */
  rawPayloadString?: string;
  /** JSON parse error message, when payload could not be parsed. */
  payloadError?: string;
  /** Header parse error message, when header could not be parsed. */
  headerError?: string;
}

/**
 * Decode a compact JWS (header.payload.signature) into parts.
 *
 * Resilient: if the payload fails to JSON-parse we still return the header and
 * the raw decoded string so the caller can surface diagnostics. A header parse
 * failure is also captured rather than thrown.
 */
export function decodeJwt(token: string): DecodedJwtWithDiagnostics {
  const parts = token.split('.');
  if (parts.length < 2) {
    throw new Error('Malformed JWT: missing payload section');
  }

  let header: Record<string, unknown> = {};
  let headerError: string | undefined;
  try {
    header = JSON.parse(b64urlToString(parts[0])) as Record<string, unknown>;
  } catch (e) {
    headerError = (e as Error).message;
  }

  let payload: Record<string, unknown> = {};
  let rawPayloadString: string | undefined;
  let payloadError: string | undefined;
  if (parts[1]) {
    try {
      rawPayloadString = b64urlToString(parts[1]);
    } catch (e) {
      payloadError = `base64url decode failed: ${(e as Error).message}`;
    }
    if (rawPayloadString !== undefined) {
      try {
        payload = JSON.parse(rawPayloadString) as Record<string, unknown>;
      } catch (e) {
        payloadError = (e as Error).message;
      }
    }
  }

  return {
    header,
    payload,
    signature: parts[2] ?? '',
    raw: token,
    rawPayloadString,
    payloadError,
    headerError,
  };
}

/** Splits off trailing disclosures / optional KB-JWT common to both decoders. */
function splitHopSegments(segments: string[]): {rest: string[]; kbJwtSegment?: string} {
  const rest = segments.slice(1);
  // Trailing empty string indicates the trailing `~` at end of issuance form.
  if (rest.length > 0 && rest[rest.length - 1] === '') rest.pop();

  // Last segment is a KB-JWT if it looks like `header.payload.sig` (three parts).
  if (rest.length > 0) {
    const last = rest[rest.length - 1];
    if (last.includes('.') && last.split('.').length === 3) {
      rest.pop();
      return {rest, kbJwtSegment: last};
    }
  }
  return {rest};
}

function decodeDisclosures(
  raws: string[],
  digestFor: (raw: string) => string,
): DecodedDisclosure[] {
  const disclosures: DecodedDisclosure[] = [];
  for (const raw of raws) {
    if (!raw) continue;
    try {
      const decoded = JSON.parse(b64urlToString(raw)) as unknown;
      if (Array.isArray(decoded)) {
        if (decoded.length === 3) {
          disclosures.push({
            salt: String(decoded[0]),
            key: String(decoded[1]),
            value: decoded[2],
            digest: digestFor(raw),
            raw,
          });
        } else if (decoded.length === 2) {
          disclosures.push({
            salt: String(decoded[0]),
            value: decoded[1],
            digest: digestFor(raw),
            raw,
          });
        }
      }
    } catch {
      // Skip malformed disclosure.
    }
  }
  return disclosures;
}

/** Decodes a single SD-JWT hop: `<jwt>~<disc1>~...~<optional kb_jwt>`. */
async function decodeSingleHop(token: string): Promise<DecodedSdJwt> {
  const segments = token.split('~');
  if (segments.length < 1) {
    throw new Error('Malformed SD-JWT: empty token');
  }
  const issuerJwt = decodeJwt(segments[0]);
  const {rest, kbJwtSegment} = splitHopSegments(segments);
  const kbJwt = kbJwtSegment ? tryDecodeJwt(kbJwtSegment) : undefined;

  const digests = new Map<string, string>();
  for (const raw of rest) {
    if (!raw) continue;
    digests.set(raw, await sha256Base64Url(raw));
  }
  const disclosures = decodeDisclosures(rest, (raw) => digests.get(raw) ?? '');

  return {issuerJwt, disclosures, kbJwt};
}

function decodeSingleHopSync(token: string): DecodedSdJwt {
  const segments = token.split('~');
  if (segments.length < 1) {
    throw new Error('Malformed SD-JWT: empty token');
  }
  const issuerJwt = decodeJwt(segments[0]);
  const {rest, kbJwtSegment} = splitHopSegments(segments);
  const kbJwt = kbJwtSegment ? tryDecodeJwt(kbJwtSegment) : undefined;
  const disclosures = decodeDisclosures(rest, () => '');

  return {issuerJwt, disclosures, kbJwt};
}

function tryDecodeJwt(segment: string): DecodedJwtWithDiagnostics | undefined {
  try {
    return decodeJwt(segment);
  } catch {
    // Not a JWT after all; caller already popped it, so it's simply dropped.
    return undefined;
  }
}

/**
 * Decode an SD-JWT token, or a `~~`-joined dSD-JWT delegation chain, into
 * its parts. For a chain, `hops` holds every hop fully decoded and the
 * top-level `issuerJwt`/`disclosures`/`kbJwt` describe hop 0.
 */
export async function decodeSdJwt(token: string): Promise<DecodedSdJwt> {
  const hopTokens = token.split('~~');
  const hops = await Promise.all(hopTokens.map(decodeSingleHop));
  return hops.length > 1 ? {...hops[0], hops} : hops[0];
}

/**
 * Synchronous variant of decodeSdJwt that omits the per-disclosure SHA-256
 * digest (digest is only computed via the async WebCrypto API).
 *
 * Useful when the caller doesn't need digests and wants to render synchronously.
 */
export function decodeSdJwtSync(token: string): DecodedSdJwt {
  const hopTokens = token.split('~~');
  const hops = hopTokens.map(decodeSingleHopSync);
  return hops.length > 1 ? {...hops[0], hops} : hops[0];
}
