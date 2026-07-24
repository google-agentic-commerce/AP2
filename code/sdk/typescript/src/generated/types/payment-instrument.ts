// Code generated from code/sdk/schemas/ap2 by scripts/generate.ts. DO NOT EDIT.

import { z } from "zod";

export const PaymentInstrumentSchema = z
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
  .describe("Instrument used for payment.");

export type PaymentInstrument = z.infer<typeof PaymentInstrumentSchema>;
