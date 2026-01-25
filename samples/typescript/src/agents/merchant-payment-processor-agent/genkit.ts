import "dotenv/config";
import { googleAI } from "@genkit-ai/googleai";
import { genkit } from "genkit";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

export const ai = genkit({
  plugins: [googleAI()],
  model: googleAI.model("gemini-2.5-flash"),
  promptDir: dirname(fileURLToPath(import.meta.url)),
});

export { z } from "genkit";
