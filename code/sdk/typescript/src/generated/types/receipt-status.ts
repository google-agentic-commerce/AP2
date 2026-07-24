// Code generated from code/sdk/schemas/ap2 by scripts/generate.ts. DO NOT EDIT.

import { z } from 'zod';

export const ReceiptStatusSchema = z
  .enum(['Success', 'Error'])
  .describe('The status of a receipt.');

export type ReceiptStatus = z.infer<typeof ReceiptStatusSchema>;
