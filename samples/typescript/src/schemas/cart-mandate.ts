import { z } from "genkit";

export const cartMandateSchema = z.object({
  contents: z.object({
    id: z.string().describe("The ID of the cart mandate."),
    userCartConfirmationRequired: z
      .boolean()
      .describe("If the user must confirm the cart."),
    paymentRequest: z
      .object({
        methodData: z.array(
          z.object({
            supportedMethods: z.string().describe("The supported methods."),
            data: z.record(z.any()).describe("The data of the method."),
          })
        ),
        details: z.object({
          id: z.string().describe("The ID of the payment request."),
          displayItems: z.array(
            z.object({
              label: z.string().describe("The label of the display item."),
              amount: z.object({
                currency: z
                  .string()
                  .describe("The three-letter ISO 4217 currency code."),
                value: z.number().describe("The monetary value."),
              }),
              pending: z
                .boolean()
                .describe("If true, indicates the amount is not final."),
              refundPeriod: z
                .number()
                .describe("The refund duration for this item, in days."),
            })
          ),
          shippingOptions: z.array(
            z.object({
              id: z.string().describe("The ID of the shipping option."),
              label: z.string().describe("The label of the shipping option."),
              amount: z.object({
                currency: z
                  .string()
                  .describe("The three-letter ISO 4217 currency code."),
                value: z.number().describe("The monetary value."),
              }),
              selected: z
                .boolean()
                .describe("If the shipping option is selected."),
            })
          ),
          modifiers: z.array(
            z.object({
              supportedMethods: z
                .string()
                .describe(
                  "The payment method ID that this modifier applies to."
                ),
              total: z.object({
                label: z.string().describe("The label of the total."),
                amount: z.object({
                  currency: z
                    .string()
                    .describe("The three-letter ISO 4217 currency code."),
                  value: z.number().describe("The monetary value."),
                }),
                pending: z
                  .boolean()
                  .describe("If true, indicates the amount is not final."),
                refundPeriod: z
                  .number()
                  .describe("The refund duration for this item, in days."),
              }),
              additionalDisplayItems: z.array(
                z.object({
                  label: z
                    .string()
                    .describe("The label of the additional display item."),
                  amount: z.object({
                    currency: z
                      .string()
                      .describe("The three-letter ISO 4217 currency code."),
                    value: z.number().describe("The monetary value."),
                  }),
                  pending: z
                    .boolean()
                    .describe("If true, indicates the amount is not final."),
                  refundPeriod: z
                    .number()
                    .describe("The refund duration for this item, in days."),
                })
              ),
              data: z.record(z.any()).describe("The data of the modifier."),
            })
          ),
          total: z.object({
            label: z
              .string()
              .describe("A human-readable description of the item."),
            amount: z.object({
              currency: z
                .string()
                .describe("The three-letter ISO 4217 currency code."),
              value: z.number().describe("The monetary value."),
            }),
            pending: z.boolean().describe("If the amount is not final."),
            refundPeriod: z
              .number()
              .describe("The refund duration for this item, in days."),
          }),
        }),
        options: z.object({
          requestPayerName: z
            .boolean()
            .describe("If the payer's name should be collected.")
            .optional(),
          requestPayerEmail: z
            .boolean()
            .describe("If the payer's email should be collected.")
            .optional(),
          requestPayerPhone: z
            .boolean()
            .describe("If the payer's phone number should be collected.")
            .optional(),
          requestShipping: z
            .boolean()
            .describe("If the payer's shipping address should be collected.")
            .optional(),
          shippingType: z
            .enum(["shipping", "delivery", "pickup"])
            .optional()
            .describe("Can be `shipping`, `delivery`, or `pickup`."),
        }),
        shippingAddress: z
          .object({
            city: z.string().describe("The city of the shipping address."),
            country: z
              .string()
              .describe("The country of the shipping address."),
            dependentLocality: z
              .string()
              .describe("The dependent locality of the shipping address."),
            organization: z
              .string()
              .describe("The organization of the shipping address."),
            phoneNumber: z
              .string()
              .describe("The phone number of the shipping address."),
            postalCode: z
              .string()
              .describe("The postal code of the shipping address."),
            recipient: z
              .string()
              .describe("The recipient of the shipping address."),
            region: z.string().describe("The region of the shipping address."),
            sortingCode: z
              .string()
              .describe("The sorting code of the shipping address."),
            addressLine: z
              .array(z.string())
              .describe("The address line of the shipping address."),
          })
          .optional()
          .describe("The shipping address of the user."),
      })
      .describe(
        "The W3C PaymentRequest object to initiate payment. This contains the" +
          "items being purchased, prices, and the set of payment methods" +
          "accepted by the merchant for this cart."
      ),
    cartExpiry: z
      .string()
      .describe("When this cart expires, in ISO 8601 format."),
    merchantName: z.string().describe("The name of the merchant."),
  }),
  merchantAuthorization: z
    .string()
    .describe(
      `
      A base64url-encoded JSON Web Token (JWT) that digitally
      signs the cart contents, guaranteeing its authenticity and integrity:
      1. Header includes the signing algorithm and key ID.
      2. Payload includes:
      - iss, sub, aud: Identifiers for the merchant (issuer)
          and the intended recipient (audience), like a payment processor.
      - iat: iat, exp: Timestamps for the token's creation and its
          short-lived expiration (e.g., 5-15 minutes) to enhance security.
      - jti: Unique identifier for the JWT to prevent replay attacks.
      - cart_hash: A secure hash of the CartMandate, ensuring
          integrity. The hash is computed over the canonical JSON
          representation of the CartContents object.
      3. Signature: A digital signature created with the merchant's private
      key. It allows anyone with the public key to verify the token's
      authenticity and confirm that the payload has not been tampered with.
      The entire JWT is base64url encoded to ensure safe transmission.
      `
    )
    .optional(),
});
