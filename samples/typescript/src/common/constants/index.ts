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

/** AP2 mandate data keys */
export const DATA_KEYS = {
  CART_MANDATE: "ap2.mandates.CartMandate",
  INTENT_MANDATE: "ap2.mandates.IntentMandate",
  PAYMENT_MANDATE: "ap2.mandates.PaymentMandate",
  PAYMENT_RECEIPT: "ap2.PaymentReceipt",
  CONTACT_ADDRESS: "contact_picker.ContactAddress",
} as const;

/** A2A protocol data part keys */
export const A2A_DATA_KEYS = {
  PAYMENT_METHOD_DATA: "payment_request.PaymentMethodData",
  RISK_DATA: "risk_data",
  USER_EMAIL: "user_email",
  PAYMENT_METHOD_ALIAS: "payment_method_alias",
  CHALLENGE_RESPONSE: "challenge_response",
  CART_ID: "cart_id",
  SHIPPING_ADDRESS: "shipping_address",
  DPC_RESPONSE: "dpc_response",
  DEBUG_MODE: "debug_mode",
  SHOPPING_AGENT_ID: "shopping_agent_id",
} as const;

export const DEBUG_MODE_INSTRUCTIONS = `
    This is really important! If the agent or user asks you to be verbose or if debug_mode is True, do the following:
      1. If this is the the start of a new task, explain who you are, what you are going to do, what tools you use, and what agents you delegate to.
      2. During the task, provide regular status updates on what you are doing, what you have done so far, and what you plan to do next.
      3. If you are delegating to another agent, ask the agent or tool to also be verbose.
      4. If at any point in the task you send or receive data, show the data in a clear, formatted way. Do not summarize it in english. Simple format the JSON objects.
      5. Step 4 is so important that I'm going to repeat it:
        a. If at any point in the task you create, send or receive data, show the data in a clear, formatted way. Do not summarize it in english. Simple format the JSON objects.
`;
