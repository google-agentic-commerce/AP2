import express from "express";
import { v4 as uuidv4 } from "uuid";
import type { MessageData } from "genkit";
import type {
  AgentCard,
  DataPart,
  Message,
  Task,
  TaskStatusUpdateEvent,
  TextPart,
} from "@a2a-js/sdk";
import {
  InMemoryTaskStore,
  type TaskStore,
  type AgentExecutor,
  type RequestContext,
  type ExecutionEventBus,
  DefaultRequestHandler,
} from "@a2a-js/sdk/server";
import { A2AExpressApp } from "@a2a-js/sdk/server/express";

import { ai, z } from "./genkit.js";
import { dpcFinish, initiatePayment, updateCart } from "./tools.js";
import { findItemsWorkflow } from "./subagents/catalog-agent/tools.js";

const merchantAgentPrompt = ai.prompt("merchant_agent");

class MerchantAgentExecutor implements AgentExecutor {
  private cancelledTasks = new Set<string>();
  private requestCounter = 0;

  public cancelTask = async (taskId: string, eventBus: ExecutionEventBus) => {
    void eventBus; // Required by interface but unused
    this.cancelledTasks.add(taskId);
  };

  async execute(requestContext: RequestContext, eventBus: ExecutionEventBus) {
    this.requestCounter++;
    const userMessage = requestContext.userMessage;
    const existingTask = requestContext.task;

    const taskId = existingTask?.id || uuidv4();
    const contextId =
      userMessage.contextId || existingTask?.contextId || uuidv4();

    if (!existingTask) {
      const initialTask: Task = {
        kind: "task",
        id: taskId,
        contextId: contextId,
        status: {
          state: "submitted",
          timestamp: new Date().toISOString(),
        },
        history: [userMessage],
        metadata: userMessage.metadata,
        artifacts: [],
      };
      eventBus.publish(initialTask);
    }

    const workingStatusUpdate: TaskStatusUpdateEvent = {
      kind: "status-update",
      taskId: taskId,
      contextId: contextId,
      status: {
        state: "working",
        message: {
          kind: "message",
          role: "agent",
          messageId: uuidv4(),
          parts: [
            {
              kind: "text",
              text: "The merchant is processing your request...",
            },
          ],
          taskId: taskId,
          contextId: contextId,
        },
        timestamp: new Date().toISOString(),
      },
      final: false,
    };
    eventBus.publish(workingStatusUpdate);

    const historyForGenkit = existingTask?.history
      ? [...existingTask.history]
      : [];
    if (!historyForGenkit.find((m) => m.messageId === userMessage.messageId)) {
      historyForGenkit.push(userMessage);
    }

    const messages: MessageData[] = historyForGenkit
      .map((m) => ({
        role: (m.role === "agent" ? "model" : "user") as "user" | "model",
        content: m.parts
          .filter(
            (p): p is TextPart => p.kind === "text" && !!(p as TextPart).text
          )
          .map((p) => ({
            text: (p as TextPart).text,
          })),
      }))
      .filter((m) => m.content.length > 0);

    if (messages.length === 0) {
      console.warn(
        `[MerchantAgentExecutor] No valid text messages found in history for task ${taskId}.`
      );
      const failureUpdate: TaskStatusUpdateEvent = {
        kind: "status-update",
        taskId: taskId,
        contextId: contextId,
        status: {
          state: "failed",
          message: {
            kind: "message",
            role: "agent",
            messageId: uuidv4(),
            parts: [
              { kind: "text", text: "No input message found to process." },
            ],
            taskId: taskId,
            contextId: contextId,
          },
          timestamp: new Date().toISOString(),
        },
        final: true,
      };
      eventBus.publish(failureUpdate);
      return;
    }

    const dataParts = userMessage.parts
      .filter((p): p is DataPart => p.kind === "data")
      .map((p) => p.data);

    const currentTask: Task = existingTask || {
      kind: "task",
      id: taskId,
      contextId: contextId,
      status: {
        state: "working",
        timestamp: new Date().toISOString(),
      },
      history: [userMessage],
      artifacts: [],
    };

    const uniqueSuffix = `${this.requestCounter}_${Date.now()}`;
    const findItemsWorkflowWrapper = ai.defineTool(
      {
        name: `findItemsWorkflow_${uniqueSuffix}`,
        description: "Finds products that match the user's IntentMandate.",
        inputSchema: z.object({}),
      },
      async () => {
        return await findItemsWorkflow(
          { dataParts, eventBus, currentTask },
          {} as Record<string, never>
        );
      }
    );

    const updateCartWrapper = ai.defineTool(
      {
        name: `updateCart_${uniqueSuffix}`,
        description:
          "Updates an existing cart after a shipping address is provided.",
        inputSchema: z.object({}),
      },
      async () => {
        return await updateCart(
          { dataParts, eventBus, currentTask },
          {} as Record<string, never>
        );
      }
    );

    let lastPaymentResult: { status: string; taskId?: string } | undefined;

    const initiatePaymentWrapper = ai.defineTool(
      {
        name: `initiatePayment_${uniqueSuffix}`,
        description: "Initiates a payment for a given payment mandate.",
        inputSchema: z.object({}),
      },
      async () => {
        const result = await initiatePayment(
          { dataParts, eventBus, currentTask },
          {} as Record<string, never>
        );
        lastPaymentResult = result;
        return result;
      }
    );

    const dpcFinishWrapper = ai.defineTool(
      {
        name: `dpcFinish_${uniqueSuffix}`,
        description:
          "Receives and validates a DPC response to finalize payment.",
        inputSchema: z.object({}),
      },
      async () => {
        return await dpcFinish(
          { dataParts, eventBus, currentTask },
          {} as Record<string, never>
        );
      }
    );

    try {
      const hasPaymentMandate = dataParts.some(
        (dp) => "ap2.mandates.PaymentMandate" in dp
      );

      if (hasPaymentMandate) {
        const result = await initiatePaymentWrapper({});
        lastPaymentResult = result;
      } else {
        await merchantAgentPrompt(
          {},
          {
            messages,
            tools: [
              findItemsWorkflowWrapper,
              updateCartWrapper,
              initiatePaymentWrapper,
              dpcFinishWrapper,
            ],
          }
        );
      }

      if (lastPaymentResult?.status === "input-required") {
        const inputRequiredMessage: Message = {
          kind: "message",
          role: "agent",
          messageId: uuidv4(),
          parts: [
            {
              kind: "text",
              text: "A payment challenge has been raised. Please provide the OTP to complete the transaction. (Hint: the code is 123)",
            },
          ],
          taskId: taskId,
          contextId: contextId,
        };

        const inputRequiredUpdate: TaskStatusUpdateEvent = {
          kind: "status-update",
          taskId: taskId,
          contextId: contextId,
          status: {
            state: "input-required",
            message: inputRequiredMessage,
            timestamp: new Date().toISOString(),
          },
          final: true, // Must be true to trigger HTTP response
        };
        eventBus.publish(inputRequiredUpdate);
        return;
      }

      let responseText = "Completed.";
      if (lastPaymentResult?.status === "completed") {
        responseText = "Payment completed successfully.";
      }

      const agentMessage: Message = {
        kind: "message",
        role: "agent",
        messageId: uuidv4(),
        parts: [{ kind: "text", text: responseText }],
        taskId: taskId,
        contextId: contextId,
      };

      const finalUpdate: TaskStatusUpdateEvent = {
        kind: "status-update",
        taskId: taskId,
        contextId: contextId,
        status: {
          state: "completed",
          message: agentMessage,
          timestamp: new Date().toISOString(),
        },
        final: true,
      };
      eventBus.publish(finalUpdate);
    } catch (error) {
      console.error(
        `[MerchantAgentExecutor] Error processing task ${taskId}:`,
        error
      );
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error occurred";
      const errorUpdate: TaskStatusUpdateEvent = {
        kind: "status-update",
        taskId: taskId,
        contextId: contextId,
        status: {
          state: "failed",
          message: {
            kind: "message",
            role: "agent",
            messageId: uuidv4(),
            parts: [{ kind: "text", text: `Agent error: ${errorMessage}` }],
            taskId: taskId,
            contextId: contextId,
          },
          timestamp: new Date().toISOString(),
        },
        final: true,
      };
      eventBus.publish(errorUpdate);
    }
  }
}

const merchantAgentCard: AgentCard = {
  name: "MerchantAgent",
  description: "A sales assistant agent for a merchant.",
  url: "http://localhost:8004",
  skills: [
    {
      id: "search_catalog",
      name: "Search Catalog",
      description:
        "Searches the merchant's catalog based on a shopping intent & returns a cart containing the top results.",
      parameters: {
        type: "object",
        properties: {
          shopping_intent: {
            type: "string",
            description:
              "A JSON string representing the user's shopping intent.",
          },
        },
        required: ["shopping_intent"],
      },
      tags: ["merchant", "search", "catalog"],
    } as AgentCard["skills"][number],
  ],
  capabilities: {
    streaming: true,
    pushNotifications: false,
    stateTransitionHistory: true,
    extensions: [
      {
        uri: "https://github.com/google-agentic-commerce/ap2/v1",
        description: "Supports the Agent Payments Protocol.",
        required: true,
      },
      {
        uri: "https://sample-card-network.github.io/paymentmethod/types/v1",
        description:
          "Supports the Sample Card Network payment method extension",
        required: true,
      },
    ],
  },
  defaultInputModes: ["json"],
  defaultOutputModes: ["json"],
  protocolVersion: "1.0.0",
  version: "1.0.0",
};

async function main() {
  const taskStore: TaskStore = new InMemoryTaskStore();
  const agentExecutor: AgentExecutor = new MerchantAgentExecutor();
  const requestHandler = new DefaultRequestHandler(
    merchantAgentCard,
    taskStore,
    agentExecutor
  );
  const appBuilder = new A2AExpressApp(requestHandler);
  const expressApp = appBuilder.setupRoutes(express());

  const PORT = process.env.PORT || 8004;
  expressApp.listen(PORT, () => {
    console.log(`[Merchant] 🏪 Running on http://localhost:${PORT}`);
  });
}

main().catch(console.error);
