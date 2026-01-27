import type {
  MessageSendParams,
  SendMessageSuccessResponse,
  Task,
  TaskArtifactUpdateEvent,
  TaskStatusUpdateEvent,
} from "@a2a-js/sdk";
import { ai, z } from "./genkit.js";
import type { ExecutionEventBus } from "@a2a-js/sdk/server";
import { findDataPart, parseCanonicalObject } from "../../utils/message.js";
import type { PaymentItem } from "../../types/payment-item.js";
import { v4 as uuidv4 } from "uuid";
import type { PaymentMandate } from "../../types/payment-mandate.js";
import { paymentMandateSchema } from "../../schemas/payment-mandate.js";
import { A2AClient } from "@a2a-js/sdk/client";

const FAKE_JWT = "eyJhbGciOiJSUzI1NiIsImtpZIwMjQwOTA...";
const CART_MANDATE_DATA_KEY = "ap2.mandates.CartMandate";
const PAYMENT_MANDATE_DATA_KEY = "ap2.mandates.PaymentMandate";

const PAYMENT_PROCESSORS_BY_PAYMENT_METHOD_TYPE: Record<string, string> = {
  CARD: "http://localhost:8003/.well-known/agent-card.json",
};

function getPaymentProcessorTaskId(task: Task | undefined): string | null {
  if (!task || !task.history) {
    return null;
  }

  for (const message of task.history) {
    if (message.taskId && message.taskId !== task.id) {
      return message.taskId;
    }
  }

  return null;
}

export const updateCart = ai.defineTool(
  {
    name: "updateCart",
    description:
      "Updates an existing cart after a shipping address is provided.",
    inputSchema: z.object({
      dataParts: z
        .array(z.record(z.unknown()))
        .describe("An array of data part contents from the request."),
      eventBus: z
        .custom<ExecutionEventBus>()
        .describe("The event bus to add artifacts and complete the task."),
      currentTask: z.custom<Task>(),
    }),
  },
  async (input) => {
    const { dataParts, eventBus, currentTask } = input;

    const cartId = findDataPart("cartId", dataParts) as string | null;
    if (!cartId) {
      throw new Error("Missing cart id.");
    }

    const shippingAddress = findDataPart(
      "shippingAddress",
      dataParts
    ) as Record<string, unknown> | null;
    if (!shippingAddress) {
      throw new Error("Missing shipping address.");
    }

    const { getCartMandate, getRiskData } = await import("./storage.js");
    const cartMandate = getCartMandate(cartId);
    if (!cartMandate) {
      throw new Error(`CartMandate not found for cart_id: ${cartId}`);
    }

    const riskData = getRiskData(currentTask.contextId);
    if (!riskData) {
      throw new Error(
        `Missing risk_data for context_id: ${currentTask.contextId}`
      );
    }

    cartMandate.contents.paymentRequest.shippingAddress = shippingAddress;

    const taxAndShippingCosts: PaymentItem[] = [
      {
        label: "Shipping",
        amount: {
          currency: "USD",
          value: 2.0,
        },
        refundPeriod: 30,
      },
      {
        label: "Tax",
        amount: {
          currency: "USD",
          value: 1.5,
        },
        refundPeriod: 30,
      },
    ];

    const paymentRequest = cartMandate.contents.paymentRequest;

    if (!paymentRequest.details.displayItems) {
      paymentRequest.details.displayItems = taxAndShippingCosts;
    } else {
      paymentRequest.details.displayItems.push(...taxAndShippingCosts);
    }

    paymentRequest.details.total.amount.value =
      paymentRequest.details.displayItems.reduce(
        (acc, curr) => acc + curr.amount.value,
        0
      );

    cartMandate.merchantAuthorization = FAKE_JWT;

    const artifactUpdate: TaskArtifactUpdateEvent = {
      kind: "artifact-update",
      taskId: currentTask.id,
      contextId: currentTask.contextId,
      artifact: {
        artifactId: uuidv4(),
        parts: [
          {
            kind: "data",
            data: {
              [CART_MANDATE_DATA_KEY]: cartMandate,
            },
          },
          {
            kind: "data",
            data: {
              risk_data: riskData,
            },
          },
        ],
      },
    };

    eventBus.publish(artifactUpdate);

    return { status: "success", cartMandate };
  }
);

export const initiatePayment = ai.defineTool(
  {
    name: "initiatePayment",
    description:
      "Initiates a payment for a given payment mandate. Use to make a payment.",
    inputSchema: z.object({
      dataParts: z
        .array(z.record(z.unknown()))
        .describe(
          "The data parts from the request, expected to contain a PaymentMandate and optionally a challenge response."
        ),
      eventBus: z
        .custom<ExecutionEventBus>()
        .describe("The event bus to add artifacts and complete the task."),
      currentTask: z.custom<Task>(),
    }),
  },
  async (input) => {
    const { dataParts, eventBus, currentTask } = input;

    const paymentMandate = parseCanonicalObject<PaymentMandate>(
      PAYMENT_MANDATE_DATA_KEY,
      dataParts,
      paymentMandateSchema
    );

    if (!paymentMandate) {
      throw new Error("Missing payment_mandate.");
    }

    const riskData = findDataPart("risk_data", dataParts) as string | null;
    if (!riskData) {
      throw new Error("Missing risk_data.");
    }

    const paymentMethodType =
      paymentMandate.paymentMandateContents.paymentResponse.methodName;

    const processorUrl =
      PAYMENT_PROCESSORS_BY_PAYMENT_METHOD_TYPE[paymentMethodType];

    if (!processorUrl) {
      throw new Error(
        `No payment processor found for method: ${paymentMethodType}`
      );
    }

    const client = await A2AClient.fromCardUrl(processorUrl);

    const message: MessageSendParams = {
      message: {
        messageId: uuidv4(),
        role: "user",
        contextId: currentTask.contextId,
        parts: [
          {
            kind: "text",
            text: "Call the initiatePayment tool to process this payment. The payment mandate and risk data are provided in the data parts of this message.",
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
              risk_data: riskData,
            },
          },
        ],
        kind: "message",
      },
    };

    const challengeResponse = findDataPart("challenge_response", dataParts) as
      | string
      | null;
    if (challengeResponse) {
      message.message.parts.push({
        kind: "data",
        data: { challenge_response: challengeResponse },
      });
    }

    const paymentProcessorTaskId = getPaymentProcessorTaskId(currentTask);
    if (paymentProcessorTaskId) {
      message.message.taskId = paymentProcessorTaskId;
    }

    const response = await client.sendMessage(message);

    if ("error" in response) {
      throw new Error(response.error.message);
    }

    const result = (response as SendMessageSuccessResponse).result;
    if (result.kind === "task") {
      const task = result as Task;

      const statusUpdate: TaskStatusUpdateEvent = {
        kind: "status-update",
        taskId: currentTask.id,
        contextId: currentTask.contextId,
        status: {
          state: task.status.state,
          message: task.status.message,
          timestamp: new Date().toISOString(),
        },
        final: false,
      };

      const terminalStates = ["completed", "failed", "canceled", "rejected"];
      if (terminalStates.includes(task.status.state)) {
        statusUpdate.final = true;
      }

      eventBus.publish(statusUpdate);

      return {
        status: task.status.state,
        taskId: task.id,
      };
    }

    throw new Error("Unexpected response type from payment processor");
  }
);

export const dpcFinish = ai.defineTool(
  {
    name: "dpcFinish",
    description: `
        Receives and validates a DPC response to finalize payment.
        This tool receives the Digital Payment Credential (DPC) response, in the form
        of an OpenID4VP JSON, validates it, and simulates payment finalization.
    `,
    inputSchema: z.object({
      dataParts: z
        .array(z.record(z.unknown()))
        .describe(
          "The data parts from the request, expected to contain a DPC response."
        ),
      eventBus: z
        .custom<ExecutionEventBus>()
        .describe("The event bus to add artifacts and complete the task."),
      currentTask: z.custom<Task>(),
    }),
  },
  async (input) => {
    const { dataParts, eventBus, currentTask } = input;

    const dpcResponse = findDataPart("dpcResponse", dataParts) as Record<
      string,
      unknown
    > | null;
    if (!dpcResponse) {
      throw new Error("Missing dpc_response.");
    }

    const artifactUpdate: TaskArtifactUpdateEvent = {
      kind: "artifact-update",
      taskId: currentTask.id,
      contextId: currentTask.contextId,
      artifact: {
        artifactId: uuidv4(),
        parts: [
          {
            kind: "data",
            data: { paymentStatus: "SUCCESS", transactionId: "txn_1234567890" },
          },
        ],
      },
    };
    eventBus.publish(artifactUpdate);

    return { status: "success" };
  }
);
