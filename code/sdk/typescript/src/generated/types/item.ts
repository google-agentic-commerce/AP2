// Code generated from code/sdk/schemas/ap2 by scripts/generate.ts. DO NOT EDIT.

import { z } from 'zod';

export const ItemSchema = z
  .object({
    id: z
      .string()
      .describe(
        'The product identifier, often the SKU, required to resolve the product details associated with this line item.',
      ),
    title: z.string().describe('Product title.'),
    price: z
      .number()
      .int()
      .gte(0)
      .describe(
        "Unit price in the currency's minor unit as defined by ISO 4217.",
      ),
    image_url: z.string().url().describe('Product image URI.').optional(),
  })
  .describe(
    'Product details for a line item. Matches UCP types/item.json (2026-04-08).',
  );

export type Item = z.infer<typeof ItemSchema>;
