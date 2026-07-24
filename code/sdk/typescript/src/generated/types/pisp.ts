// Code generated from code/sdk/schemas/ap2 by scripts/generate.ts. DO NOT EDIT.

import { z } from "zod";

export const PispSchema = z
  .object({
    legal_name: z.string().describe("Legal name of the PISP."),
    brand_name: z.string().describe("Brand name of the PISP."),
    domain_name: z
      .string()
      .describe(
        "Domain name of the PISP as secured by the [eIDAS] QWAC certificate of the TPP."
      ),
  })
  .describe(
    "Schema defining a Payment Initiation Service Provider (PISP) object"
  );

export type Pisp = z.infer<typeof PispSchema>;
