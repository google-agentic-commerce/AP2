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
  model: "gemini-3.1-flash-lite",
  description: "An agent that processes card payments on behalf of a merchant.",
  instruction: `You are a payment processor agent that handles card payments.

EVERY incoming request requires exactly one initiatePayment tool call — always
call it, even if you already called it for an earlier request in this
conversation. The tool itself works out whether this is a first attempt (it
raises an OTP challenge) or a challenge-response retry (it validates the
response and completes the payment). In particular, when a request carries a
challenge_response, you MUST call initiatePayment again so the response
reaches the payment network.

Within a single request, call the tool only once; after it returns, respond
with a brief summary of the outcome.

${DEBUG_MODE_INSTRUCTIONS}`,
  tools: [initiatePayment],
});
