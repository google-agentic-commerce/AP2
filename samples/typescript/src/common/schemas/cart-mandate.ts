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

import { z } from "zod";
import { shippingAddressSchema } from "./shipping-address.js";

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
            data: z.record(z.string(), z.any()).describe("The data of the method."),
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
                .optional()
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
                .optional()
                .describe("If the shipping option is selected."),
            })
          ).optional(),
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
                  .optional()
                  .describe("If true, indicates the amount is not final."),
                refundPeriod: z
                  .number()
                  .describe("The refund duration for this item, in days."),
              }).optional(),
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
                    .optional()
                    .describe("If true, indicates the amount is not final."),
                  refundPeriod: z
                    .number()
                    .describe("The refund duration for this item, in days."),
                })
              ).optional(),
              data: z.record(z.string(), z.any()).optional().describe("The data of the modifier."),
            })
          ).optional(),
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
            pending: z.boolean().optional().describe("If the amount is not final."),
            refundPeriod: z
              .number()
              .default(30)
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
        shippingAddress: shippingAddressSchema
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
