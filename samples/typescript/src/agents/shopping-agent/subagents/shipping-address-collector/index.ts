import express from "express";
import { v4 as uuidv4 } from "uuid";
import type { MessageData } from "genkit";
import type {
  AgentCard,
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
import { getShippingAddress } from "./tools.js";
import { getState, setCurrentContext } from "../../../../store/state.js";

const shippingAddressCollectorAgentPrompt = ai.prompt(
  "shipping_address_collector_agent"
);

class ShippingAddressCollectorAgentExecutor implements AgentExecutor {
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
            { kind: "text", text: "Setting up your delivery details..." },
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
        `[ShippingAddressCollectorAgentExecutor] No valid text messages found in history for task ${taskId}.`
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
      const response = await shippingAddressCollectorAgentPrompt(
        {},
        {
          messages,
          tools: [getShippingAddress],
        }
      );

      const responseText = response.text;
      const isTaskComplete = !!getState().shippingAddress;

      const finalResponseText = isTaskComplete
        ? `Shipping address collected successfully: ${getState().shippingAddress?.recipient || "Unknown"}, ${getState().shippingAddress?.city || ""}, ${getState().shippingAddress?.region || ""}`
        : responseText;

      const agentMessage: Message = {
        kind: "message",
        role: "agent",
        messageId: uuidv4(),
        parts: [{ kind: "text", text: finalResponseText || "Completed." }],
        taskId: taskId,
        contextId: contextId,
      };
      const taskState = isTaskComplete ? "completed" : "working";

      if (isTaskComplete && getState().shippingAddress) {
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
                  shippingAddress: getState().shippingAddress,
                  userEmail: getState().userEmail,
                },
              },
            ],
          },
        };
        eventBus.publish(artifactUpdate);
      }

      const update: TaskStatusUpdateEvent = {
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
      eventBus.publish(update);
    } catch (error) {
      console.error(
        `[ShippingAddressCollectorAgentExecutor] Error processing task ${taskId}:`,
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

const shippingAddressCollectorAgentCard: AgentCard = {
  name: "ShippingAddressCollectorAgent",
  description:
    "A subagent that collects shipping address information from users.",
  url: "http://localhost:8007",
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
    new ShippingAddressCollectorAgentExecutor();
  const requestHandler = new DefaultRequestHandler(
    shippingAddressCollectorAgentCard,
    taskStore,
    agentExecutor
  );
  const appBuilder = new A2AExpressApp(requestHandler);
  const expressApp = appBuilder.setupRoutes(express());

  const PORT = process.env.PORT || 8007;
  expressApp.listen(PORT, () => {
    console.log(
      `[ShippingAddressCollector] 📦 Running on http://localhost:${PORT}`
    );
  });
}

main().catch(console.error);
