// Code generated from code/sdk/schemas/ap2 by scripts/generate.ts. DO NOT EDIT.

import { z } from 'zod';

export const PaymentReceiptSchema = z
  .record(z.string(), z.any())
  .and(
    z.any().superRefine((x, ctx) => {
      const schemas = [
        z.object({
          status: z.literal('Success'),
          iss: z.string().describe('The issuer of the receipt.'),
          iat: z
            .number()
            .int()
            .describe('The creation timestamp as a Unix epoch.'),
          reference: z
            .string()
            .describe(
              'The hash of the closed Mandate that this receipt is binding to.',
            ),
          error: z
            .string()
            .describe(
              'A unique error code. Present if and only if status is Error.',
            )
            .optional(),
          error_description: z
            .string()
            .describe(
              'A human-readable error description. Present if and only if status is Error.',
            )
            .optional(),
          payment_id: z
            .string()
            .describe('A unique identifier for the payment.'),
          psp_confirmation_id: z
            .string()
            .describe(
              'A unique identifier for the transaction confirmation at the PSP. Present only if status is Success.',
            ),
          network_confirmation_id: z
            .string()
            .describe(
              'A unique identifier for the transaction confirmation at the network. Present only if status is Success.',
            ),
        }),
        z.object({
          status: z.literal('Error'),
          iss: z.string().describe('The issuer of the receipt.'),
          iat: z
            .number()
            .int()
            .describe('The creation timestamp as a Unix epoch.'),
          reference: z
            .string()
            .describe(
              'The hash of the closed Mandate that this receipt is binding to.',
            ),
          error: z
            .string()
            .describe(
              'A unique error code. Present if and only if status is Error.',
            ),
          error_description: z
            .string()
            .describe(
              'A human-readable error description. Present if and only if status is Error.',
            ),
          payment_id: z
            .string()
            .describe('A unique identifier for the payment.'),
          psp_confirmation_id: z
            .string()
            .describe(
              'A unique identifier for the transaction confirmation at the PSP. Present only if status is Success.',
            )
            .optional(),
          network_confirmation_id: z
            .string()
            .describe(
              'A unique identifier for the transaction confirmation at the network. Present only if status is Success.',
            )
            .optional(),
        }),
      ];
      const { errors, failed } = schemas.reduce<{
        errors: z.core.$ZodIssue[];
        failed: number;
      }>(
        ({ errors, failed }, schema) =>
          ((result) =>
            result.error
              ? {
                  errors: [...errors, ...result.error.issues],
                  failed: failed + 1,
                }
              : { errors, failed })(schema.safeParse(x)),
        { errors: [], failed: 0 },
      );
      const passed = schemas.length - failed;
      if (passed !== 1) {
        ctx.addIssue(
          errors.length
            ? {
                path: [],
                code: 'invalid_union',
                errors: [errors],
                message:
                  'Invalid input: Should pass single schema. Passed ' + passed,
              }
            : {
                path: [],
                code: 'custom',
                errors: [errors],
                message:
                  'Invalid input: Should pass single schema. Passed ' + passed,
              },
        );
      }
    }),
  )
  .describe(
    'Receipt that supplies information about the final state of a payment.',
  );

export type PaymentReceipt = z.infer<typeof PaymentReceiptSchema>;
