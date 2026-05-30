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

export const paymentSuccessSchema = z.object({
  kind: z.literal("success"),
  merchantConfirmationId: z
    .string()
    .describe("A unique identifier for the transaction confirmation at the merchant."),
  pspConfirmationId: z
    .string()
    .optional()
    .describe("A unique identifier for the transaction confirmation at the PSP."),
  networkConfirmationId: z
    .string()
    .optional()
    .describe("A unique identifier for the transaction confirmation at the network."),
});

export const paymentErrorSchema = z.object({
  kind: z.literal("error"),
  errorMessage: z
    .string()
    .describe("A human-readable message explaining the error and how to proceed."),
});

export const paymentFailureSchema = z.object({
  kind: z.literal("failure"),
  failureMessage: z
    .string()
    .describe("A human-readable message explaining the failure and how to proceed."),
});

export const paymentStatusSchema = z.discriminatedUnion("kind", [
  paymentSuccessSchema,
  paymentErrorSchema,
  paymentFailureSchema,
]);

export const paymentReceiptSchema = z.object({
  paymentMandateId: z
    .string()
    .describe("A unique identifier for the processed payment mandate."),
  timestamp: z
    .string()
    .describe("The date and time the payment receipt was created, in ISO 8601 format."),
  paymentId: z
    .string()
    .describe("A unique identifier for the payment."),
  amount: z.object({
    currency: z.string().describe("The three-letter ISO 4217 currency code."),
    value: z.number().describe("The monetary value."),
  }).describe("The monetary amount of the payment."),
  paymentStatus: paymentStatusSchema
    .describe("The status of the payment."),
  paymentMethodDetails: z
    .record(z.string(), z.unknown())
    .optional()
    .describe("The payment method used for the transaction."),
});
