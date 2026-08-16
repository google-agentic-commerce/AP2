// Code generated from code/sdk/schemas/ap2 by scripts/generate.ts. DO NOT EDIT.

import { z } from "zod";

export const CheckoutMandateSchema = z
  .object({
    vct: z
      .literal("mandate.checkout.1")
      .describe(
        "Verifiable Credential Type claim as defined in SD-JWT. MUST be 'mandate.checkout'."
      )
      .default("mandate.checkout.1"),
    checkout_jwt: z
      .string()
      .describe(
        "base64url-encoded serialized merchant-signed JWT of the Checkout payload."
      ),
    checkout_hash: z
      .string()
      .describe(
        "base64url-encoded hash of the checkout_jwt field value, uniquely identifying this checkout. If this checkout mandate is presented as an sd-jwt and the _sd_alg field is present then the hash algorithm used MUST match the _sd_alg field. Otherwise, sha-256 MUST be used."
      ),
    iat: z
      .number()
      .int()
      .describe("The creation timestamp as a Unix epoch.")
      .optional(),
    exp: z
      .number()
      .int()
      .describe("The expiration timestamp as a Unix epoch.")
      .optional(),
  })
  .describe(
    "Agreement from a User or an Agent to authorize a particular Checkout action."
  );

export type CheckoutMandate = z.infer<typeof CheckoutMandateSchema>;
