import express from "express";
import { v4 as uuidv4 } from "uuid";
import type { MessageData } from "genkit";
import type {
  AgentCard,
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

import { ai } from "./genkit.js";
import {
  createPaymentMandate,
  initiatePayment,
  initiatePaymentWithOtp,
  sendMessageToSubagent,
  sendSignedPaymentMandateToCredentialsProvider,
  signMandatesOnUserDevice,
  updateCart,
} from "./tools.js";
import { getState, setCurrentContext } from "../../store/state.js";

const shoppingAgentPrompt = ai.prompt("shopping_agent");

class ShoppingAgentExecutor implements AgentExecutor {
  private cancelledTasks = new Set<string>();
  public cancelTask = async (taskId: string) => {
    this.cancelledTasks.add(taskId);
  };

  async execute(requestContext: RequestContext, eventBus: ExecutionEventBus) {
    const userMessage = requestContext.userMessage;
    const existingTask = requestContext.task;

    const taskId = existingTask?.id || uuidv4();
    const contextId =
      userMessage.contextId || existingTask?.contextId || uuidv4();

    setCurrentContext(contextId);

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
              text: "Your personal shopping assistant is working on your request...",
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
        `[ShoppingAgentExecutor] No valid text messages found in history for task ${taskId}.`
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

    try {
      const response = await shoppingAgentPrompt(
        {},
        {
          messages,
          tools: [
            sendMessageToSubagent,
            createPaymentMandate,
            initiatePayment,
            initiatePaymentWithOtp,
            sendSignedPaymentMandateToCredentialsProvider,
            signMandatesOnUserDevice,
            updateCart,
          ],
        }
      );

      const responseText = response.text;

      const agentMessage: Message = {
        kind: "message",
        role: "agent",
        messageId: uuidv4(),
        parts: [
          { kind: "text", text: responseText || "Working on your request..." },
        ],
        taskId: taskId,
        contextId: contextId,
      };

      const isWorkflowComplete = Boolean(getState().paymentReceipt);

      const statusUpdate: TaskStatusUpdateEvent = {
        kind: "status-update",
        taskId: taskId,
        contextId: contextId,
        status: {
          state: isWorkflowComplete ? "completed" : "working",
          message: agentMessage,
          timestamp: new Date().toISOString(),
        },
        final: isWorkflowComplete,
      };
      eventBus.publish(statusUpdate);
    } catch (error) {
      console.error(
        `[ShoppingAgentExecutor] Error processing task ${taskId}:`,
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

const shoppingAgentCard: AgentCard = {
  name: "ShoppingAgent",
  description: "A shopping agent",
  url: "http://localhost:8001",
  skills: [],
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
  const agentExecutor: AgentExecutor = new ShoppingAgentExecutor();
  const requestHandler = new DefaultRequestHandler(
    shoppingAgentCard,
    taskStore,
    agentExecutor
  );
  const appBuilder = new A2AExpressApp(requestHandler);
  const expressApp = appBuilder.setupRoutes(express());
  const PORT = process.env.PORT || 8001;
  expressApp.listen(PORT, () => {
    console.log(`[ShoppingAgent] 🛒 Running on http://localhost:${PORT}`);
  });
}

main().catch(console.error);
