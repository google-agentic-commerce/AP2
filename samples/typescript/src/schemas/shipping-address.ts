import { z } from "genkit";

export const shippingAddressSchema = z.object({
  city: z.string(),
  country: z.string(),
  dependent_locality: z.string().optional(),
  organization: z.string().optional(),
  phone_number: z.string().optional(),
  postal_code: z.string(),
  recipient: z.string(),
  region: z.string(),
  sorting_code: z.string().optional(),
  address_line: z.array(z.string()),
});
