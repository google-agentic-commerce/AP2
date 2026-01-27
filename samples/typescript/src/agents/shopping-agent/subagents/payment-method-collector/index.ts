import express from "express";
import { v4 as uuidv4 } from "uuid";
import { type MessageData, z } from "genkit";
import type {
  AgentCard,
  DataPart,
  Message,
  Task,
  TaskStatusUpdateEvent,
  TaskArtifactUpdateEvent,
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
import { getPaymentMethods, getPaymentCredentialToken } from "./tools.js";
import {
  getState,
  setState,
  setCurrentContext,
} from "../../../../store/state.js";
import type { CartMandate } from "../../../../types/cart-mandate.js";

const paymentMethodCollectorAgentPrompt = ai.prompt(
  "payment_method_collector_agent"
);

class PaymentMethodCollectorAgentExecutor implements AgentExecutor {
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

    setCurrentContext(contextId);

    const dataParts = userMessage.parts
      .filter((p): p is DataPart => p.kind === "data")
      .map((p) => p.data as Record<string, unknown>);

    for (const dataPart of dataParts) {
      if (dataPart.cartMandate) {
        setState({ cartMandate: dataPart.cartMandate as CartMandate });
      }
      if (dataPart.shoppingContextId) {
        setState({ shoppingContextId: dataPart.shoppingContextId as string });
      }
    }

    if (getState().paymentCredentialToken) {
      const completionMessage: Message = {
        kind: "message",
        role: "agent",
        messageId: uuidv4(),
        parts: [
          {
            kind: "text",
            text: `Payment method is already collected. Token: ${getState().paymentCredentialToken.substring(
              0,
              20
            )}...`,
          },
        ],
        taskId: taskId,
        contextId: contextId,
      };

      const completionUpdate: TaskStatusUpdateEvent = {
        kind: "status-update",
        taskId: taskId,
        contextId: contextId,
        status: {
          state: "completed",
          message: completionMessage,
          timestamp: new Date().toISOString(),
        },
        final: true,
      };
      eventBus.publish(completionUpdate);
      return;
    }

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
              text: "Retrieving your available payment methods...",
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
        `[PaymentMethodCollectorAgentExecutor] No valid text messages found in history for task ${taskId}.`
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
      const transferBackToRootAgent = ai.defineTool(
        {
          name: "transfer_back_to_root_agent",
          description:
            "Completes the payment method collection and returns to the main agent.",
          inputSchema: z.object({}),
        },
        async () => ({
          status: "completed",
          message: "Payment method collected successfully.",
        })
      );

      const response = await paymentMethodCollectorAgentPrompt(
        {},
        {
          messages,
          tools: [
            getPaymentMethods,
            getPaymentCredentialToken,
            transferBackToRootAgent,
          ],
        }
      );

      const responseText = response.text;

      const agentMessage: Message = {
        kind: "message",
        role: "agent",
        messageId: uuidv4(),
        parts: [{ kind: "text", text: responseText || "Completed." }],
        taskId: taskId,
        contextId: contextId,
      };

      const isTaskComplete = !!getState().paymentCredentialToken;
      const taskState = isTaskComplete ? "completed" : "working";

      if (isTaskComplete && getState().paymentCredentialToken) {
        const artifactUpdate: TaskArtifactUpdateEvent = {
          kind: "artifact-update",
          taskId: taskId,
          contextId: contextId,
          artifact: {
            artifactId: uuidv4(),
            parts: [
              {
                kind: "data",
                data: {
                  paymentCredentialToken: getState().paymentCredentialToken,
                },
              },
            ],
          },
        };
        eventBus.publish(artifactUpdate);
      }

      const finalUpdate: TaskStatusUpdateEvent = {
        kind: "status-update",
        taskId: taskId,
        contextId: contextId,
        status: {
          state: taskState,
          message: agentMessage,
          timestamp: new Date().toISOString(),
        },
        final: isTaskComplete,
      };
      eventBus.publish(finalUpdate);
    } catch (error) {
      console.error(
        `[PaymentMethodCollectorAgentExecutor] Error processing task ${taskId}:`,
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

const paymentMethodCollectorAgentCard: AgentCard = {
  name: "PaymentMethodCollectorAgent",
  description:
    "A subagent that collects payment method information from users.",
  url: "http://localhost:8006",
  skills: [],
  capabilities: {
    streaming: true,
    pushNotifications: false,
    stateTransitionHistory: true,
  },
  defaultInputModes: ["json"],
  defaultOutputModes: ["json"],
  protocolVersion: "1.0.0",
  version: "1.0.0",
};

async function main() {
  const taskStore: TaskStore = new InMemoryTaskStore();
  const agentExecutor: AgentExecutor =
    new PaymentMethodCollectorAgentExecutor();
  const requestHandler = new DefaultRequestHandler(
    paymentMethodCollectorAgentCard,
    taskStore,
    agentExecutor
  );
  const appBuilder = new A2AExpressApp(requestHandler);
  const expressApp = appBuilder.setupRoutes(express());

  const PORT = process.env.PORT || 8006;
  expressApp.listen(PORT, () => {
    console.log(
      `[PaymentMethodCollector] 💳 Running on http://localhost:${PORT}`
    );
  });
}

main().catch(console.error);
