// Code generated from code/sdk/schemas/ap2 by scripts/generate.ts. DO NOT EDIT.

import { z } from 'zod';

export const OpenPaymentMandateSchema = z
  .object({
    vct: z
      .literal('mandate.payment.open.1')
      .describe(
        "Verifiable Credential Type claim as defined in SD-JWT. MUST be 'mandate.payment.open'.",
      )
      .default('mandate.payment.open.1'),
    constraints: z
      .array(
        z.any().superRefine((x, ctx) => {
          const schemas = [
            z
              .object({
                type: z
                  .literal('payment.agent_recurrence')
                  .describe('Constraint type identifier.')
                  .default('payment.agent_recurrence'),
                frequency: z
                  .enum([
                    'ON_DEMAND',
                    'DAILY',
                    'WEEKLY',
                    'BIWEEKLY',
                    'MONTHLY',
                    'QUARTERLY',
                    'ANNUALLY',
                  ])
                  .describe('Frequency of allowed recurrences.'),
                max_occurrences: z
                  .number()
                  .int()
                  .describe('Maximum number of allowed occurrences.')
                  .optional(),
              })
              .describe(
                'Provides conditions for the agent to reuse this Payment Mandate multiple times.',
              ),
            z
              .object({
                type: z
                  .literal('payment.allowed_payees')
                  .describe('Constraint type identifier.')
                  .default('payment.allowed_payees'),
                allowed: z
                  .array(
                    z
                      .object({
                        id: z
                          .string()
                          .describe('Unique identifier for the merchant.'),
                        name: z
                          .string()
                          .describe('Human-readable name of the merchant.'),
                        website: z
                          .string()
                          .describe('Website belonging to the merchant.')
                          .optional(),
                      })
                      .describe('Schema defining a Mechant object'),
                  )
                  .describe('Array of allowed Merchant objects.'),
              })
              .describe('Defines the set of possible payees.'),
            z
              .object({
                type: z
                  .literal('payment.allowed_payment_instruments')
                  .describe('Constraint type identifier.')
                  .default('payment.allowed_payment_instruments'),
                allowed: z
                  .array(
                    z
                      .object({
                        id: z
                          .string()
                          .describe('unique identifier for this instrument'),
                        type: z
                          .string()
                          .describe(
                            'unique string identifying this category of instrument',
                          ),
                        description: z
                          .string()
                          .describe(
                            'Description of the instrument to be displayed to the user for informational purposes',
                          )
                          .optional(),
                      })
                      .describe('Instrument used for payment.'),
                  )
                  .describe('Array of allowed payment instruments.'),
              })
              .describe(
                'Defines the set of possible payment instruments for this Payment Mandate.',
              ),
            z
              .object({
                type: z
                  .literal('payment.allowed_pisps')
                  .describe('Constraint type identifier.')
                  .default('payment.allowed_pisps'),
                allowed: z
                  .array(
                    z
                      .object({
                        legal_name: z
                          .string()
                          .describe('Legal name of the PISP.'),
                        brand_name: z
                          .string()
                          .describe('Brand name of the PISP.'),
                        domain_name: z
                          .string()
                          .describe(
                            'Domain name of the PISP as secured by the [eIDAS] QWAC certificate of the TPP.',
                          ),
                      })
                      .describe(
                        'Schema defining a Payment Initiation Service Provider (PISP) object',
                      ),
                  )
                  .describe('Array of allowed PISPs.'),
              })
              .describe(
                'Defines the set of Payment Initiation Service Providers (PISPs) authorized to facilitate the transaction.',
              ),
            z
              .object({
                type: z
                  .literal('payment.amount_range')
                  .describe('Constraint type identifier.')
                  .default('payment.amount_range'),
                currency: z.string().describe('ISO4217 Alpha-3 currency code.'),
                max: z
                  .number()
                  .int()
                  .describe(
                    'Maximum allowed amount in minor (cents) unit of currency.',
                  ),
                min: z
                  .number()
                  .int()
                  .describe(
                    'Minimal amount in minor (cents) unit of currency. If absent, there is no minimum.',
                  )
                  .optional(),
              })
              .describe('Defines the valid range for the payment amount'),
            z
              .object({
                type: z
                  .literal('payment.budget')
                  .describe('Constraint type identifier.')
                  .default('payment.budget'),
                max: z.number().describe('Maximum amount for the budget.'),
                currency: z
                  .string()
                  .describe(
                    'ISO4217 Alpha-3 defining the currency of the amount.',
                  ),
              })
              .describe(
                'Defines the maximum total amount that can be spent when using the payment.agent_recurrence constraint.',
              ),
            z
              .object({
                type: z
                  .literal('payment.execution_date')
                  .describe('Constraint type identifier.')
                  .default('payment.execution_date'),
                not_before: z
                  .string()
                  .describe('Earliest valid execution date.')
                  .optional(),
                not_after: z
                  .string()
                  .describe('Latest valid execution date.')
                  .optional(),
              })
              .describe(
                'Defines the valid time window for the payment execution.',
              ),
            z
              .object({
                type: z
                  .literal('payment.reference')
                  .describe('Constraint type identifier.')
                  .default('payment.reference'),
                conditional_transaction_id: z
                  .string()
                  .describe('Digest of the associated Open Checkout Mandate.'),
              })
              .describe(
                'Constrains the payment to a specific checkout reference.',
              ),
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
                      'Invalid input: Should pass single schema. Passed ' +
                      passed,
                  }
                : {
                    path: [],
                    code: 'custom',
                    errors: [errors],
                    message:
                      'Invalid input: Should pass single schema. Passed ' +
                      passed,
                  },
            );
          }
        }),
      )
      .describe(
        'Array of constraints that the future checkout action must abide by.',
      ),
    cnf: z
      .record(z.string(), z.any())
      .describe(
        'Confirmation claim as defined in RFC 7800 section 3.1. Used for key binding.',
      ),
    payee: z
      .object({
        id: z.string().describe('Unique identifier for the merchant.'),
        name: z.string().describe('Human-readable name of the merchant.'),
        website: z
          .string()
          .describe('Website belonging to the merchant.')
          .optional(),
      })
      .describe('Schema defining a Mechant object')
      .optional(),
    payment_amount: z
      .object({
        amount: z
          .number()
          .int()
          .describe('Amount in minor units, according to the ISO-4217 spec.'),
        currency: z
          .string()
          .describe(
            'ISO-4217 3-letter alphabetic currency code of the payment.',
          ),
      })
      .describe(
        'Transaction amount object containing currency (ISO 4217 code, e.g., "USD") and amount (integer minor units per ISO 4217, e.g., 27999 = $279.99). Pre-set by the user at time of mandate creation.',
      )
      .optional(),
    payment_instrument: z
      .object({
        id: z.string().describe('unique identifier for this instrument'),
        type: z
          .string()
          .describe('unique string identifying this category of instrument'),
        description: z
          .string()
          .describe(
            'Description of the instrument to be displayed to the user for informational purposes',
          )
          .optional(),
      })
      .describe('Instrument used for payment.')
      .optional(),
    pisp: z
      .object({
        legal_name: z.string().describe('Legal name of the PISP.'),
        brand_name: z.string().describe('Brand name of the PISP.'),
        domain_name: z
          .string()
          .describe(
            'Domain name of the PISP as secured by the [eIDAS] QWAC certificate of the TPP.',
          ),
      })
      .describe(
        'Schema defining a Payment Initiation Service Provider (PISP) object',
      )
      .optional(),
    execution_date: z
      .string()
      .describe(
        'ISO8601 date of execution of payment. When absent indicates immediate execution.',
      )
      .optional(),
    risk_data: z
      .record(z.string(), z.any())
      .describe(
        'An map of relevant risk signals collected by the trusted surface at time of mandate creation.',
      )
      .optional(),
    iat: z
      .number()
      .int()
      .describe('The creation timestamp as a Unix epoch.')
      .optional(),
    exp: z
      .number()
      .int()
      .describe('The expiration timestamp as a Unix epoch.')
      .optional(),
  })
  .describe(
    'Agreement between a user and an agent (or chain of agents) to authorize future payment actions.',
  );

export type OpenPaymentMandate = z.infer<typeof OpenPaymentMandateSchema>;
