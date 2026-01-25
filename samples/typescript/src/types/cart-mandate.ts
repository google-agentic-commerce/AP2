import type { cartMandateSchema } from "../schemas/cart-mandate.js";
import type { z } from "genkit";

export type CartMandate = z.infer<typeof cartMandateSchema>;
