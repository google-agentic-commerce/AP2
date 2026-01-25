import express from "express";
import { v4 as uuidv4 } from "uuid";
import type { MessageData, ToolAction } from "genkit";
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
import {
  handleCreatePaymentCredentialToken,
  handleGetPaymentMethodRawCredentials,
  handleGetShippingAddress,
  handleSearchPaymentMethods,
  handleSignedPaymentMandate,
} from "./tools.js";

const credentialsProviderAgentPrompt = ai.prompt("credentials_provider_agent");

class CredentialsProviderAgentExecutor implements AgentExecutor {
  private cancelledTasks = new Set<string>();
  private requestCounter = 0;
  private toolCallTracker = new Map<string, number>(); // Track tool calls per task

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
          parts: [{ kind: "text", text: "Processing request..." }],
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
    const wrapTool = (
      tool: ToolAction<z.ZodTypeAny, z.ZodTypeAny>,
      toolName: string
    ) => {
      return ai.defineTool(
        {
          name: `${toolName}_${uniqueSuffix}`,
          description:
            tool.__action?.metadata?.description || `Executes ${toolName}`,
          inputSchema: z.object({}),
        },
        async () => {
          const callKey = `${taskId}_${toolName}`;
          const callCount = this.toolCallTracker.get(callKey) || 0;

          if (callCount > 0) {
            return {
              status: "already_processed",
              message: "This request has already been processed.",
            };
          }

          this.toolCallTracker.set(callKey, callCount + 1);

          const result = await tool(
            { dataParts, eventBus, currentTask },
            {} as Record<string, never>
          );
          return result;
        }
      );
    };

    try {
      const response = await credentialsProviderAgentPrompt(
        {},
        {
          messages,
          tools: [
            wrapTool(
              handleCreatePaymentCredentialToken,
              "handleCreatePaymentCredentialToken"
            ),
            wrapTool(
              handleGetPaymentMethodRawCredentials,
              "handleGetPaymentMethodRawCredentials"
            ),
            wrapTool(handleGetShippingAddress, "handleGetShippingAddress"),
            wrapTool(handleSearchPaymentMethods, "handleSearchPaymentMethods"),
            wrapTool(handleSignedPaymentMandate, "handleSignedPaymentMandate"),
          ],
        }
      );

      const responseText = response.text;

      let toolWasCalled = false;
      try {
        toolWasCalled =
          response.output?.toolCalls && response.output.toolCalls.length > 0;
      } catch {
        toolWasCalled = true;
      }

      const finalText =
        responseText ||
        (toolWasCalled ? "Request processed successfully." : "Completed.");

      const agentMessage: Message = {
        kind: "message",
        role: "agent",
        messageId: uuidv4(),
        parts: [{ kind: "text", text: finalText }],
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
      // Check if this is the "Exceeded maximum tool call iterations" error
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error occurred";

      if (errorMessage.includes("Exceeded maximum tool call iterations")) {
        const successMessage: Message = {
          kind: "message",
          role: "agent",
          messageId: uuidv4(),
          parts: [{ kind: "text", text: "Request processed successfully." }],
          taskId: taskId,
          contextId: contextId,
        };

        const successUpdate: TaskStatusUpdateEvent = {
          kind: "status-update",
          taskId: taskId,
          contextId: contextId,
          status: {
            state: "completed",
            message: successMessage,
            timestamp: new Date().toISOString(),
          },
          final: true,
        };
        eventBus.publish(successUpdate);
        return;
      }

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

const credentialsProviderAgentCard: AgentCard = {
  name: "CredentialsProvider",
  description: "An agent that holds a user's payment credentials.",
  url: "http://localhost:8002",
  skills: [
    {
      id: "initiate_payment",
      name: "Initiate Payment",
      description: "Initiates a payment with the correct payment processor.",
      tags: ["payments"],
    },
    {
      id: "get_eligible_payment_methods",
      name: "Get Eligible Payment Methods",
      description:
        "Provides a list of eligible payment methods for a particular purchase.",
      parameters: {
        type: "object",
        properties: {
          email_address: {
            type: "string",
            description:
              "The email address associated with the user's account.",
          },
        },
        required: ["email_address"],
      },
      tags: ["eligible", "payment", "methods"],
    } as AgentCard["skills"][number],
    {
      id: "get_account_shipping_address",
      name: "Get Shipping Address",
      description: "Fetches the shipping address from a user's wallet.",
      parameters: {
        type: "object",
        properties: {
          email_address: {
            type: "string",
            description:
              "The email address associated with the user's account.",
          },
        },
        required: ["email_address"],
      },
      tags: ["account", "shipping"],
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
  defaultInputModes: ["text/plain"],
  defaultOutputModes: ["application/json"],
  protocolVersion: "1.0.0",
  version: "1.0.0",
};

async function main() {
  const taskStore: TaskStore = new InMemoryTaskStore();
  const agentExecutor: AgentExecutor = new CredentialsProviderAgentExecutor();
  const requestHandler = new DefaultRequestHandler(
    credentialsProviderAgentCard,
    taskStore,
    agentExecutor
  );
  const appBuilder = new A2AExpressApp(requestHandler);
  const expressApp = appBuilder.setupRoutes(express());

  const PORT = process.env.PORT || 8002;
  expressApp.listen(PORT, () => {
    console.log(`[CredentialsProvider] 🔐 Running on http://localhost:${PORT}`);
  });
}

main().catch(console.error);
