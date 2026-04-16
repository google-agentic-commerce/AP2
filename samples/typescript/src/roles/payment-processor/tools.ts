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
  MessageSendParams,
  SendMessageSuccessResponse,
  Task,
  TaskArtifactUpdateEvent,
  TaskStatusUpdateEvent,
} from "@a2a-js/sdk";
import type { ExecutionEventBus } from "@a2a-js/sdk/server";
import { findDataPart, parseCanonicalObject } from "../../common/utils/message.js";
import { getA2AContextFromTool } from "../../common/server/a2a-context.js";
import type { PaymentMandate } from "../../common/types/payment-mandate.js";
import type { PaymentReceipt } from "../../common/types/payment-receipt.js";
import { paymentMandateSchema } from "../../common/schemas/payment-mandate.js";
import { DATA_KEYS } from "../../common/constants/index.js";

const PAYMENT_MANDATE_DATA_KEY = DATA_KEYS.PAYMENT_MANDATE;
const PAYMENT_RECEIPT_DATA_KEY = DATA_KEYS.PAYMENT_RECEIPT;

// TODO(production): Replace with real OTP verification against issuer/network API.
function challengeResponseIsValid(challengeResponse: string): boolean {
  return challengeResponse === "123"; // Demo-only hardcoded OTP
}

function getCredentialsProviderUrl(
  paymentMandate: PaymentMandate
): string | null {
  const details = paymentMandate.paymentMandateContents.paymentResponse.details;
  if (!details) return null;
  const tokenObj = details.token as
    | { value?: string; url?: string }
    | string
    | undefined;
  if (typeof tokenObj === "object" && tokenObj?.url) {
    return tokenObj.url;
  }
  return null;
}

/**
 * Request payment credentials from the credentials provider.
 * For x402, the signed payload is already in payment_response.details.
 */
async function requestPaymentCredential(
  paymentMandate: PaymentMandate,
  contextId: string,
  debugMode: boolean = false,
  paymentMethod: string = "CARD"
): Promise<unknown> {
  if (paymentMethod === "x402") {
    // For x402, the signed payload is already in the payment_response.details
    return paymentMandate.paymentMandateContents.paymentResponse.details?.value;
  }

  const credentialsProviderUrl = getCredentialsProviderUrl(paymentMandate);
  if (!credentialsProviderUrl) {
    throw new Error(
      "Could not resolve credentials provider URL from payment mandate token."
    );
  }

  const client = await A2AClient.fromCardUrl(credentialsProviderUrl);

  const message: MessageSendParams = {
    message: {
      messageId: uuidv4(),
      role: "user",
      contextId,
      parts: [
        {
          kind: "text",
          text: "Give me the payment method credentials for the given token.",
        },
        { kind: "data", data: { [PAYMENT_MANDATE_DATA_KEY]: paymentMandate } },
        { kind: "data", data: { debug_mode: debugMode } },
      ],
      kind: "message",
    },
  };

  const response = await client.sendMessage(message);

  if ("error" in response) {
    throw new Error(response.error.message);
  }

  const result = (response as SendMessageSuccessResponse).result;
  if (result.kind === "task") {
    const task = result as Task;
    if (!task.artifacts || task.artifacts.length === 0) {
      throw new Error("Failed to find the payment method data.");
    }

    const firstArtifact = task.artifacts[0];
    if (firstArtifact.parts && firstArtifact.parts.length > 0) {
      const dataPart = firstArtifact.parts.find((p) => p.kind === "data");
      if (dataPart && dataPart.kind === "data") {
        return dataPart.data;
      }
    }
  }

  throw new Error("Failed to retrieve payment credentials.");
}

/**
 * Create a PaymentReceipt from the payment mandate
 */
function createPaymentReceipt(paymentMandate: PaymentMandate): PaymentReceipt {
  const paymentId = uuidv4();
  const contents = paymentMandate.paymentMandateContents;
  const paymentMethod = process.env.PAYMENT_METHOD || "CARD";
  const methodName =
    paymentMethod === "x402"
      ? "https://www.x402.org/"
      : contents.paymentResponse.methodName;

  return {
    paymentMandateId: contents.paymentMandateId,
    timestamp: new Date().toISOString(),
    paymentId,
    amount: contents.paymentDetailsTotal.amount,
    paymentStatus: {
      kind: "success",
      merchantConfirmationId: paymentId,
      pspConfirmationId: paymentId,
    },
    paymentMethodDetails: {
      methodName,
    },
  };
}

/**
 * Send the payment receipt to the credentials provider.
 * For x402, skip this step
 */
async function sendPaymentReceiptToCredentialsProvider(
  paymentReceipt: PaymentReceipt,
  paymentMandate: PaymentMandate,
  contextId: string,
  debugMode: boolean = false
): Promise<void> {
  const paymentMethod = process.env.PAYMENT_METHOD || "CARD";
  if (paymentMethod === "x402") {
    console.log(
      "Skipping sending payment receipt to credentials provider for x402."
    );
    return;
  }

  const credentialsProviderUrl = getCredentialsProviderUrl(paymentMandate);
  if (!credentialsProviderUrl) {
    console.warn(
      "Could not resolve credentials provider URL; skipping receipt delivery."
    );
    return;
  }

  const client = await A2AClient.fromCardUrl(credentialsProviderUrl);

  const message: MessageSendParams = {
    message: {
      messageId: uuidv4(),
      role: "user",
      contextId,
      parts: [
        {
          kind: "text",
          text: "Here is the payment receipt. No action is required.",
        },
        { kind: "data", data: { [PAYMENT_RECEIPT_DATA_KEY]: paymentReceipt } },
        { kind: "data", data: { debug_mode: debugMode } },
      ],
      kind: "message",
    },
  };

  await client.sendMessage(message);
}

async function raiseChallenge(
  eventBus: ExecutionEventBus,
  taskId: string,
  contextId: string
): Promise<void> {
  const challengeData = {
    type: "otp",
    display_text:
      "The payment method issuer sent a verification code to the phone " +
      "number on file, please enter it below. It will be shared with the " +
      "issuer so they can authorize the transaction." +
      "(Demo only hint: the code is 123)",
  };

  const statusUpdate: TaskStatusUpdateEvent = {
    kind: "status-update",
    taskId,
    contextId,
    status: {
      state: "input-required",
      message: {
        kind: "message",
        role: "agent",
        messageId: uuidv4(),
        parts: [
          {
            kind: "text",
            text: "Please provide the challenge response to complete the payment.",
          },
          { kind: "data", data: { challenge: challengeData } },
        ],
        taskId,
        contextId,
      },
      timestamp: new Date().toISOString(),
    },
    final: true,
  };

  eventBus.publish(statusUpdate);
}

async function completePayment(
  paymentMandate: PaymentMandate,
  eventBus: ExecutionEventBus,
  taskId: string,
  contextId: string,
  debugMode: boolean = false
): Promise<void> {
  const paymentMethod = process.env.PAYMENT_METHOD || "CARD";

  // Request payment credentials from credentials provider
  await requestPaymentCredential(
    paymentMandate,
    contextId,
    debugMode,
    paymentMethod
  );

  // Create payment receipt
  const paymentReceipt = createPaymentReceipt(paymentMandate);

  // Send receipt to credentials provider
  await sendPaymentReceiptToCredentialsProvider(
    paymentReceipt,
    paymentMandate,
    contextId,
    debugMode
  );

  // Publish receipt as artifact with canonical key
  const receiptArtifact: TaskArtifactUpdateEvent = {
    kind: "artifact-update",
    taskId,
    contextId,
    artifact: {
      artifactId: uuidv4(),
      parts: [
        { kind: "data", data: { [PAYMENT_RECEIPT_DATA_KEY]: paymentReceipt } },
      ],
    },
  };
  eventBus.publish(receiptArtifact);

  const successUpdate: TaskStatusUpdateEvent = {
    kind: "status-update",
    taskId,
    contextId,
    status: {
      state: "completed",
      message: {
        kind: "message",
        role: "agent",
        messageId: uuidv4(),
        parts: [{ kind: "text", text: "{'status': 'success'}" }],
        taskId,
        contextId,
      },
      timestamp: new Date().toISOString(),
    },
    final: true,
  };

  eventBus.publish(successUpdate);
}

/**
 * ADK Tool: Initiate Payment
 *
 * Handles payment processing with OTP challenge flow.
 */
export const initiatePayment = new FunctionTool({
  name: "initiatePayment",
  description:
    "Initiates a payment for a given payment mandate. Handles OTP challenge flow.",
  parameters: z.object({
    _trigger: z.boolean().optional().describe("Tool trigger"),
  }),
  execute: async (input, context) => {
    if (!context) throw new Error("Missing execution context");
    const { dataParts, eventBus, currentTask } = getA2AContextFromTool(context);
    const taskId = currentTask?.id || uuidv4();
    const contextId = currentTask?.contextId || uuidv4();

    let paymentMandate: PaymentMandate;
    try {
      paymentMandate = parseCanonicalObject<PaymentMandate>(
        PAYMENT_MANDATE_DATA_KEY,
        dataParts,
        paymentMandateSchema
      );
    } catch {
      return {
        error:
          "PaymentMandate not found in request data. Report this error to the caller.",
      };
    }

    const challengeResponse = findDataPart("challenge_response", dataParts) as
      | string
      | null;
    const debugMode =
      (findDataPart("debug_mode", dataParts) as boolean | null) || false;

    // Initial request - raise challenge
    if (!currentTask) {
      await raiseChallenge(eventBus, taskId, contextId);
      return { status: "input-required", message: "Challenge raised" };
    }

    // Handle challenge response
    if (currentTask.status.state === "input-required") {
      if (!challengeResponse) {
        return {
          error:
            "Challenge response is required but was not provided. Report this error to the caller.",
        };
      }

      if (!challengeResponseIsValid(challengeResponse)) {
        const statusUpdate: TaskStatusUpdateEvent = {
          kind: "status-update",
          taskId,
          contextId,
          status: {
            state: "input-required",
            message: {
              kind: "message",
              role: "agent",
              messageId: uuidv4(),
              parts: [{ kind: "text", text: "Challenge response incorrect." }],
              taskId,
              contextId,
            },
            timestamp: new Date().toISOString(),
          },
          final: false,
        };
        eventBus.publish(statusUpdate);
        return { status: "input-required", message: "Invalid challenge" };
      }

      // Valid challenge response - complete payment
      await completePayment(
        paymentMandate,
        eventBus,
        taskId,
        contextId,
        debugMode
      );
      return { status: "completed", message: "Payment completed" };
    }

    return { status: "unknown", message: "Unexpected task state" };
  },
});
