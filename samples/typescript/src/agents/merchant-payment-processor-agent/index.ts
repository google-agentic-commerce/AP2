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

import { initiatePayment } from "./tools.js";

class MerchantPaymentProcessorAgentExecutor implements AgentExecutor {
  private cancelledTasks = new Set<string>();

  public cancelTask = async (taskId: string, eventBus: ExecutionEventBus) => {
    void eventBus; // Required by interface but unused
    this.cancelledTasks.add(taskId);
  };

  async execute(requestContext: RequestContext, eventBus: ExecutionEventBus) {
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
          parts: [{ kind: "text", text: "Processing payment..." }],
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
        `[MerchantPaymentProcessorAgentExecutor] No valid text messages found in history for task ${taskId}.`
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

    const currentTask: Task | undefined = existingTask;

    try {
      const toolResult = await initiatePayment(
        { dataParts, eventBus, currentTask, taskId, contextId },
        {} as Record<string, never>
      );

      const shouldPublishFinalUpdate =
        !toolResult || toolResult.status !== "input-required";

      if (shouldPublishFinalUpdate) {
        const responseText =
          toolResult?.status === "completed"
            ? "Payment completed successfully."
            : toolResult?.message || "Payment processing finished.";

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
      } else {
        const inputRequiredMessage: Message = {
          kind: "message",
          role: "agent",
          messageId: uuidv4(),
          parts: [
            {
              kind: "text",
              text:
                toolResult?.message ||
                "Challenge raised. Please provide the required input.",
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
          final: true,
        };
        eventBus.publish(inputRequiredUpdate);
      }
    } catch (error) {
      console.error(
        `[MerchantPaymentProcessorAgentExecutor] Error processing task ${taskId}:`,
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

const merchantPaymentProcessorAgentCard: AgentCard = {
  name: "MerchantPaymentProcessorAgent",
  description: "An agent that processes card payments on behalf of a merchant.",
  url: "http://localhost:8003",
  skills: [
    {
      id: "card-processor",
      name: "Card Processor",
      description: "Processes card payments.",
      tags: ["payment", "card"],
    },
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
  defaultInputModes: ["text/plain"],
  defaultOutputModes: ["application/json"],
  protocolVersion: "1.0.0",
  version: "1.0.0",
};

async function main() {
  const taskStore: TaskStore = new InMemoryTaskStore();
  const agentExecutor: AgentExecutor =
    new MerchantPaymentProcessorAgentExecutor();
  const requestHandler = new DefaultRequestHandler(
    merchantPaymentProcessorAgentCard,
    taskStore,
    agentExecutor
  );
  const appBuilder = new A2AExpressApp(requestHandler);
  const expressApp = appBuilder.setupRoutes(express());

  const PORT = process.env.PORT || 8003;
  expressApp.listen(PORT, () => {
    console.log(`[PaymentProcessor] 💳 Running on http://localhost:${PORT}`);
  });
}

main().catch(console.error);
