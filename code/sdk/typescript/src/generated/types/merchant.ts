// Code generated from code/sdk/schemas/ap2 by scripts/generate.ts. DO NOT EDIT.

import { z } from "zod";

export const MerchantSchema = z
  .object({
    id: z.string().describe("Unique identifier for the merchant."),
    name: z.string().describe("Human-readable name of the merchant."),
    website: z
      .string()
      .describe("Website belonging to the merchant.")
      .optional(),
  })
  .describe("Schema defining a Mechant object");

export type Merchant = z.infer<typeof MerchantSchema>;
