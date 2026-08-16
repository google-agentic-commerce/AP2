// Code generated from code/sdk/schemas/ap2 by scripts/generate.ts. DO NOT EDIT.

import { z } from "zod";

export const PaymentMandateSchema = z
  .object({
    vct: z
      .literal("mandate.payment.1")
      .describe(
        "Verifiable Credential Type claim as defined in SD-JWT. MUST be 'mandate.payment'."
      )
      .default("mandate.payment.1"),
    transaction_id: z
      .string()
      .describe(
        "base64url-encoded hash of the checkout_jwt field value, uniquely identifying the checkout associated with this. The hash algorithm used MUST be the same as the sd_hash field for this sd-jwt, or sha256 if absent."
      ),
    payee: z
      .object({
        id: z.string().describe("Unique identifier for the merchant."),
        name: z.string().describe("Human-readable name of the merchant."),
        website: z
          .string()
          .describe("Website belonging to the merchant.")
          .optional(),
      })
      .describe("The merchant receiving the payment."),
    pisp: z
      .object({
        legal_name: z.string().describe("Legal name of the PISP."),
        brand_name: z.string().describe("Brand name of the PISP."),
        domain_name: z
          .string()
          .describe(
            "Domain name of the PISP as secured by the [eIDAS] QWAC certificate of the TPP."
          ),
      })
      .describe("The Payment Initiation Service Provider.")
      .optional(),
    payment_amount: z
      .object({
        amount: z
          .number()
          .int()
          .describe("Amount in minor units, according to the ISO-4217 spec."),
        currency: z
          .string()
          .describe(
            "ISO-4217 3-letter alphabetic currency code of the payment."
          ),
      })
      .describe(
        'Transaction amount object containing currency (ISO 4217 code, e.g., "USD") and amount (integer minor units per ISO 4217, e.g., 27999 = $279.99). Final value confirmed by the user.'
      ),
    payment_instrument: z
      .object({
        id: z.string().describe("unique identifier for this instrument"),
        type: z
          .string()
          .describe("unique string identifying this category of instrument"),
        description: z
          .string()
          .describe(
            "Description of the instrument to be displayed to the user for informational purposes"
          )
          .optional(),
      })
      .describe("The payment instrument used."),
    execution_date: z
      .string()
      .describe(
        "ISO8601 date of execution of payment. When absent indicates immediate execution."
      )
      .optional(),
    risk_data: z
      .record(z.string(), z.any())
      .describe(
        "An map of relevant risk signals collected by the trusted surface at time of mandate creation."
      )
      .optional(),
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
    "Agreement from a User or an Agent to authorize a particular Payment action."
  );

export type PaymentMandate = z.infer<typeof PaymentMandateSchema>;
