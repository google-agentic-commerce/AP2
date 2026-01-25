import { ai, z } from "./genkit.js";
import { A2AClient } from "@a2a-js/sdk/client";
import type {
  MessageSendParams,
  SendMessageSuccessResponse,
  Task,
  TaskStatusUpdateEvent,
} from "@a2a-js/sdk";
import { v4 as uuidv4 } from "uuid";
import type { ExecutionEventBus } from "@a2a-js/sdk/server";
import { findDataPart, parseCanonicalObject } from "../../utils/message.js";
import type { PaymentMandate } from "../../types/payment-mandate.js";
import { paymentMandateSchema } from "../../schemas/payment-mandate.js";

const PAYMENT_MANDATE_DATA_KEY = "ap2.mandates.PaymentMandate";

function challengeResponseIsValid(challengeResponse: string): boolean {
  return challengeResponse === "123";
}

async function requestPaymentCredential(
  paymentMandate: PaymentMandate,
  contextId: string,
  debugMode: boolean = false
): Promise<unknown> {
  const credentialsProviderUrl =
    "http://localhost:8002/.well-known/agent-card.json";

  const client = await A2AClient.fromCardUrl(credentialsProviderUrl);

  const message: MessageSendParams = {
    message: {
      messageId: uuidv4(),
      role: "user",
      contextId: contextId,
      parts: [
        {
          kind: "text",
          text: "Give me the payment method credentials for the given token.",
        },
        {
          kind: "data",
          data: {
            [PAYMENT_MANDATE_DATA_KEY]: paymentMandate,
          },
        },
        {
          kind: "data",
          data: {
            debug_mode: debugMode,
          },
        },
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
    taskId: taskId,
    contextId: contextId,
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
          {
            kind: "data",
            data: { challenge: challengeData },
          },
        ],
        taskId: taskId,
        contextId: contextId,
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
  await requestPaymentCredential(paymentMandate, contextId, debugMode);

  const successUpdate: TaskStatusUpdateEvent = {
    kind: "status-update",
    taskId: taskId,
    contextId: contextId,
    status: {
      state: "completed",
      message: {
        kind: "message",
        role: "agent",
        messageId: uuidv4(),
        parts: [
          {
            kind: "text",
            text: "{'status': 'success'}",
          },
        ],
        taskId: taskId,
        contextId: contextId,
      },
      timestamp: new Date().toISOString(),
    },
    final: true,
  };

  eventBus.publish(successUpdate);
}

export const initiatePayment = ai.defineTool(
  {
    name: "initiatePayment",
    description: "Initiates a payment for a given payment mandate.",
    inputSchema: z.object({
      dataParts: z
        .array(z.record(z.unknown()))
        .describe(
          "The data parts from the request, expected to contain a PaymentMandate and optionally a challenge response."
        ),
      eventBus: z
        .custom<ExecutionEventBus>()
        .describe("The event bus to add artifacts and complete the task."),
      currentTask: z.custom<Task>().optional(),
      taskId: z.string().optional().describe("The task ID from the executor"),
      contextId: z
        .string()
        .optional()
        .describe("The context ID from the executor"),
    }),
  },
  async (input) => {
    const { dataParts, eventBus, currentTask } = input;
    const taskId = input.taskId || currentTask?.id || uuidv4();
    const contextId = input.contextId || currentTask?.contextId || uuidv4();

    const paymentMandate = parseCanonicalObject<PaymentMandate>(
      PAYMENT_MANDATE_DATA_KEY,
      dataParts,
      paymentMandateSchema
    );

    if (!paymentMandate) {
      throw new Error("Missing payment_mandate.");
    }

    const challengeResponse = findDataPart("challenge_response", dataParts) as
      | string
      | null;
    const debugMode =
      (findDataPart("debug_mode", dataParts) as boolean | null) || false;

    if (!currentTask) {
      await raiseChallenge(eventBus, taskId, contextId);
      return { status: "input-required", message: "Challenge raised" };
    }

    if (currentTask.status.state === "input-required") {
      if (!challengeResponse) {
        throw new Error("Challenge response is required.");
      }

      if (!challengeResponseIsValid(challengeResponse)) {
        const statusUpdate: TaskStatusUpdateEvent = {
          kind: "status-update",
          taskId: taskId,
          contextId: contextId,
          status: {
            state: "input-required",
            message: {
              kind: "message",
              role: "agent",
              messageId: uuidv4(),
              parts: [
                {
                  kind: "text",
                  text: "Challenge response incorrect.",
                },
              ],
              taskId: taskId,
              contextId: contextId,
            },
            timestamp: new Date().toISOString(),
          },
          final: false,
        };
        eventBus.publish(statusUpdate);
        return { status: "input-required", message: "Invalid challenge" };
      }

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
  }
);
