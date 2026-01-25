import { z } from "genkit";

export const intentMandateSchema = z.object({
  naturalLanguageDescription: z.string(),
  userCartConfirmationRequired: z.boolean(),
  merchants: z.array(z.string()).optional(),
  skus: z.array(z.string()).optional(),
  requiresRefundability: z.boolean().optional(),
  intentExpiry: z.string(),
});
