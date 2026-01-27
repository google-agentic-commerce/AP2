import type { intentMandateSchema } from "../schemas/intent-mandate.js";
import type { z } from "genkit";

export type IntentMandate = z.infer<typeof intentMandateSchema>;
