// Code generated from code/sdk/schemas/ap2 by scripts/generate.ts. DO NOT EDIT.

import { z } from "zod";

export const JwkSchema = z
  .object({
    kty: z.literal("EC").describe("Key type."),
    crv: z.literal("P-256").describe("Curve name.").optional(),
    x: z
      .string()
      .regex(new RegExp("^[A-Za-z0-9_-]{43}$"))
      .describe("Base64url-encoded x coordinate of the EC public key.")
      .optional(),
    y: z
      .string()
      .regex(new RegExp("^[A-Za-z0-9_-]{43}$"))
      .describe("Base64url-encoded y coordinate of the EC public key.")
      .optional(),
    use: z
      .enum(["sig", "enc"])
      .describe("Public key use. 'sig' for signature, 'enc' for encryption.")
      .optional(),
    key_ops: z
      .array(
        z.enum([
          "sign",
          "verify",
          "encrypt",
          "decrypt",
          "wrapKey",
          "unwrapKey",
          "deriveKey",
          "deriveBits",
        ])
      )
      .describe(
        "Key operations. Identifies the operations the key is intended for."
      )
      .optional(),
    alg: z
      .literal("ES256")
      .describe("Algorithm. Must be 'ES256' for P-256 curve signing.")
      .optional(),
    kid: z
      .string()
      .describe("Key ID (§4.5). Arbitrary string used to match a specific key.")
      .optional(),
    x5u: z
      .string()
      .url()
      .describe(
        "X.509 URL (§4.6). URI pointing to an X.509 public key certificate or chain."
      )
      .optional(),
    x5c: z
      .array(z.string())
      .describe(
        "X.509 certificate chain (§4.7). Array of base64-encoded (not base64url) DER PKIX certificates."
      )
      .optional(),
    x5t: z
      .string()
      .describe(
        "X.509 SHA-1 thumbprint (§4.8). Base64url-encoded SHA-1 digest of the DER encoding of the certificate."
      )
      .optional(),
    "x5t#S256": z
      .string()
      .describe(
        "X.509 SHA-256 thumbprint (§4.9). Base64url-encoded SHA-256 digest of the DER encoding of the certificate."
      )
      .optional(),
  })
  .strict()
  .describe("An EC P-256 public key in JWK format (RFC 7517).");

export type Jwk = z.infer<typeof JwkSchema>;
