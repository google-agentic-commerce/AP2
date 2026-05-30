/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import { LlmAgent } from "@google/adk";
import { DEBUG_MODE_INSTRUCTIONS } from "../../common/constants/index.js";
import { initiatePayment } from "./tools.js";

/**
 * Payment Processor Agent (ADK)
 *
 * Processes card payments on behalf of merchants with OTP challenge support.
 */
export const paymentProcessorAgent = new LlmAgent({
  name: "payment_processor_agent",
  model: "gemini-2.5-flash",
  description: "An agent that processes card payments on behalf of a merchant.",
  instruction: `You are a payment processor agent that handles card payments.

When you receive a payment mandate, call the initiatePayment tool to process it.
The tool will handle the OTP challenge flow automatically.

Call the initiatePayment tool exactly once per request. After the tool returns
a result, respond with a brief summary of the outcome. Do not call the tool
again after it has already returned.

${DEBUG_MODE_INSTRUCTIONS}`,
  tools: [initiatePayment],
});
