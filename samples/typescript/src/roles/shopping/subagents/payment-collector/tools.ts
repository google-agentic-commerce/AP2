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

import { FunctionTool } from "@google/adk";
import { z } from "zod";
import { v4 as uuidv4 } from "uuid";
import { A2AClient } from "@a2a-js/sdk/client";
import type {
  Artifact,
  DataPart,
  MessageSendParams,
  SendMessageSuccessResponse,
  Task,
} from "@a2a-js/sdk";
import type { CartMandate } from "../../../../common/types/cart-mandate.js";
import { AGENT_URLS } from "../../../index.js";
import { A2A_DATA_KEYS } from "../../../../common/constants/index.js";

const PAYMENT_METHOD_DATA_DATA_KEY = A2A_DATA_KEYS.PAYMENT_METHOD_DATA;

// Helper function
function getFirstDataPart(
  artifacts: Artifact[]
): Record<string, unknown> | null {
  for (const artifact of artifacts) {
    for (const part of artifact.parts) {
      if (part.kind === "data") {
        return (part as DataPart).data as Record<string, unknown>;
      }
    }
  }
  return null;
}

/**
 * Tool 1: Get Payment Methods
 *
 * Gets the user's payment methods from the credentials provider.
 */
export const getPaymentMethods = new FunctionTool({
  name: "get_payment_methods",
  description: "Gets the user's payment methods from the credentials provider.",
  parameters: z.object({
    userEmail: z.string().describe("The user's email address"),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error("Missing execution context");
    const { userEmail } = input;

    // Read cartMandate from shared session state (set by parent shopping agent)
    const cartMandate = context.state.get("cartMandate") as
      | CartMandate
      | undefined;
    if (!cartMandate) {
      throw new Error("No cart mandate found in session state.");
    }

    const shoppingContextId = context.state.get("shoppingContextId") as
      | string
      | undefined;

    const sendParams: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: "user",
        contextId: shoppingContextId || uuidv4(),
        parts: [
          {
            kind: "text",
            text: "Get the user's payment methods.",
          },
          {
            kind: "data",
            data: {
              user_email: userEmail,
            },
          },
        ],
        kind: "message",
      },
    };

    // Add payment method data from cart mandate
    for (const methodData of cartMandate.contents.paymentRequest.methodData) {
      sendParams.message.parts.push({
        kind: "data",
        data: {
          [PAYMENT_METHOD_DATA_DATA_KEY]: methodData,
        },
      });
    }

    const client = await A2AClient.fromCardUrl(AGENT_URLS.CREDENTIALS_PROVIDER);
    const response = await client.sendMessage(sendParams);

    if ("error" in response) {
      console.error(
        "Error in credentials provider agent:",
        response.error.message
      );
      throw new Error(response.error.message);
    }

    const result = (response as SendMessageSuccessResponse).result;

    if (result.kind !== "task") {
      throw new Error("Expected task response");
    }

    const task = result as Task;
    const paymentMethods = getFirstDataPart(task.artifacts ?? []);
    return paymentMethods;
  },
});

/**
 * Tool 2: Get Payment Credential Token
 *
 * Gets a payment credential token from the credentials provider.
 */
export const getPaymentCredentialToken = new FunctionTool({
  name: "get_payment_credential_token",
  description: "Gets a payment credential token from the credentials provider.",
  parameters: z.object({
    userEmail: z.string().describe("The user's email address"),
    paymentMethodAlias: z
      .string()
      .describe("The payment method alias chosen by the user"),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error("Missing execution context");
    const { userEmail, paymentMethodAlias } = input;

    const shoppingContextId = context.state.get("shoppingContextId") as
      | string
      | undefined;

    const sendParams: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: "user",
        contextId: shoppingContextId || uuidv4(),
        parts: [
          {
            kind: "text",
            text: "Get a payment credential token for the user's payment method.",
          },
          {
            kind: "data",
            data: {
              user_email: userEmail,
              payment_method_alias: paymentMethodAlias,
            },
          },
        ],
        kind: "message",
      },
    };

    const client = await A2AClient.fromCardUrl(AGENT_URLS.CREDENTIALS_PROVIDER);
    const response = await client.sendMessage(sendParams);

    if ("error" in response) {
      console.error("Error:", response.error.message);
      throw new Error(response.error.message);
    }

    const result = (response as SendMessageSuccessResponse).result;

    if (result.kind !== "task") {
      throw new Error("Expected task response");
    }

    const task = result as Task;

    // Extract data parts from artifacts
    const extractedDataParts = (task.artifacts ?? []).map((artifact) => {
      const parts: unknown[] = [];
      for (const part of artifact.parts) {
        if (part.kind === "data") {
          parts.push((part as DataPart).data);
        }
      }
      return parts;
    });

    // Get first data part
    const getFirstItem = (
      dataParts: unknown[][]
    ): Record<string, unknown> | null => {
      for (const dataPart of dataParts) {
        for (const item of dataPart) {
          return item as Record<string, unknown>;
        }
      }
      return null;
    };

    const data = getFirstItem(extractedDataParts);
    const token = data?.token as string | undefined;

    const credentialsProviderUrl = AGENT_URLS.CREDENTIALS_PROVIDER;
    context.state.set("paymentCredentialToken", token);
    context.state.set("paymentCredentialTokenObject", {
      value: token,
      url: credentialsProviderUrl,
    });

    return {
      status: "success",
      token,
    };
  },
});
