// Code generated from code/sdk/schemas/ap2 by scripts/generate.ts. DO NOT EDIT.

import { z } from "zod";

export const OpenCheckoutMandateSchema = z
  .object({
    vct: z
      .literal("mandate.checkout.open.1")
      .describe(
        "Verifiable Credential Type claim as defined in SD-JWT. MUST be 'mandate.checkout.open'."
      )
      .default("mandate.checkout.open.1"),
    constraints: z
      .array(
        z.union([
          z
            .object({
              type: z
                .literal("checkout.allowed_merchants")
                .describe("Constraint type identifier.")
                .default("checkout.allowed_merchants"),
              allowed: z
                .array(
                  z
                    .object({
                      id: z
                        .string()
                        .describe("Unique identifier for the merchant."),
                      name: z
                        .string()
                        .describe("Human-readable name of the merchant."),
                      website: z
                        .string()
                        .describe("Website belonging to the merchant.")
                        .optional(),
                    })
                    .describe("Schema defining a Mechant object")
                )
                .describe("Array of allowed Merchant objects."),
            })
            .describe(
              "Defines the set of possible merchants for this Checkout Mandate."
            ),
          z
            .object({
              type: z
                .literal("checkout.line_items")
                .describe("Constraint type identifier.")
                .default("checkout.line_items"),
              items: z
                .array(
                  z
                    .object({
                      id: z
                        .string()
                        .describe("Identifier for the line item requirement."),
                      acceptable_items: z
                        .array(
                          z
                            .object({
                              id: z
                                .string()
                                .describe(
                                  "Unique identifier for the line item. Will often be the SKU."
                                ),
                              title: z.string().describe("Title of the item."),
                            })
                            .describe(
                              "Defines an item that may be present in the Checkout Mandate."
                            )
                        )
                        .describe(
                          "Defines a set of line items that are acceptable for this line item requirement. One and only one must be present in the Checkout Mandate."
                        ),
                      quantity: z
                        .number()
                        .int()
                        .gt(0)
                        .describe("Required quantity of matching items."),
                    })
                    .describe(
                      "Defines a line item that must be present in the Checkout Mandate."
                    )
                )
                .min(1)
                .describe("Array of line item requirements."),
            })
            .describe(
              "Defines the sets of line items that are to be present in the Checkout Mandate."
            ),
        ])
      )
      .describe(
        "Array of constraints that the future checkout action must abide by."
      ),
    cnf: z
      .record(z.string(), z.any())
      .describe(
        "Confirmation claim defined in RFC 7800 section 3.1. Used for key binding."
      ),
    iat: z
      .number()
      .int()
      .describe("The creation timestamp as a Unix epoch.")
      .optional(),
    exp: z
      .number()
      .int()
      .describe("The expiration timestamp as a Unix epoch.")
      .optional(),
  })
  .describe(
    "Agreement between a user and an agent (or chain of agents) to authorize future checkout actions."
  );

export type OpenCheckoutMandate = z.infer<typeof OpenCheckoutMandateSchema>;
