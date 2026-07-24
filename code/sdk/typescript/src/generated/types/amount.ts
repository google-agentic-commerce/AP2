// Code generated from code/sdk/schemas/ap2 by scripts/generate.ts. DO NOT EDIT.

import { z } from 'zod';

export const AmountSchema = z
  .object({
    amount: z
      .number()
      .int()
      .describe('Amount in minor units, according to the ISO-4217 spec.'),
    currency: z
      .string()
      .describe('ISO-4217 3-letter alphabetic currency code of the payment.'),
  })
  .describe('Schema defining an Amount and Current object');

export type Amount = z.infer<typeof AmountSchema>;
