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

import { v4 as uuidv4 } from 'uuid';
import type { Runner } from '@google/adk';
import type {
  DataPart,
  Message,
  Task,
  TaskStatusUpdateEvent,
  TextPart,
} from '@a2a-js/sdk';
import type {
  AgentExecutor,
  RequestContext,
  ExecutionEventBus,
} from '@a2a-js/sdk/server';
import { sessionService } from '../config/session.js';
import { setA2AContext, clearA2AContext } from './a2a-context.js';

interface ADKEvent {
  author: string;
  content?: {
    parts?: Array<{
      text?: string;
      thought?: boolean;
      functionCall?: { name: string; args: unknown; id: string };
      functionResponse?: { name: string; response: unknown; id: string };
    }>;
    role?: string;
  };
  finishReason?: string;
  usageMetadata?: unknown;
}

interface BaseExecutorOptions {
  agentName: string;
  appName: string;
  runner: Runner;
  workingMessage: string;
  /** Maximum number of LLM calls per request. Defaults to 10. */
  maxLlmCalls?: number;
  /** Called before ADK agent runs. Return modified message text or undefined to use original. */
  preprocessMessage?: (params: {
    userText: string;
    dataParts: Record<string, unknown>[];
    existingTask: Task | undefined;
    session: { state: Record<string, unknown> };
  }) => string | undefined;
  /** Called after ADK event loop. Return to override default completion behavior. */
  postprocessResult?: (params: {
    responseText: string;
    toolWasCalled: boolean;
    lastToolResult: Record<string, unknown> | undefined;
    session: { state: Record<string, unknown> };
    eventBus: ExecutionEventBus;
    taskId: string;
    contextId: string;
  }) => TaskStatusUpdateEvent | null | undefined;
  /** Called before session creation to inject extra state. */
  initSessionState?: (params: {
    dataParts: Record<string, unknown>[];
    session: { state: Record<string, unknown> };
  }) => void;
  /**
   * Called after session init but before ADK runner executes.
   * Return a TaskStatusUpdateEvent to short-circuit execution (e.g., when a
   * previous result is cached). Return undefined to proceed normally.
   */
  shouldShortCircuit?: (params: {
    session: { state: Record<string, unknown> };
    dataParts: Record<string, unknown>[];
    eventBus: ExecutionEventBus;
    taskId: string;
    contextId: string;
  }) => TaskStatusUpdateEvent | undefined;
}

/**
 * Base executor that implements the common A2A agent execution pattern.
 * Reduces ~200 lines of boilerplate per server to ~20 lines of config.
 */
export class BaseAgentExecutor implements AgentExecutor {
  private cancelledTasks = new Map<string, number>();
  private static readonly CANCELLED_TASK_TTL_MS = 5 * 60 * 1000; // 5 minutes
  private options: BaseExecutorOptions;

  constructor(options: BaseExecutorOptions) {
    this.options = options;
    // Periodic cleanup of expired cancellation entries
    setInterval(() => {
      const now = Date.now();
      for (const [taskId, timestamp] of this.cancelledTasks) {
        if (now - timestamp > BaseAgentExecutor.CANCELLED_TASK_TTL_MS) {
          this.cancelledTasks.delete(taskId);
        }
      }
    }, 60_000).unref();
  }

  public cancelTask = async (taskId: string, eventBus: ExecutionEventBus) => {
    this.cancelledTasks.set(taskId, Date.now());
    eventBus.publish({
      kind: 'status-update',
      taskId,
      contextId: '',
      status: {
        state: 'canceled',
        timestamp: new Date().toISOString(),
      },
      final: true,
    } satisfies TaskStatusUpdateEvent);
    eventBus.finished();
  };

  private isTaskCancelled(taskId: string): boolean {
    return this.cancelledTasks.has(taskId);
  }

  async execute(requestContext: RequestContext, eventBus: ExecutionEventBus) {
    const { agentName, appName, runner, workingMessage } = this.options;
    const userMessage = requestContext.userMessage;
    const existingTask = requestContext.task;

    const taskId = existingTask?.id || uuidv4();
    const contextId =
      userMessage.contextId || existingTask?.contextId || uuidv4();

    // Publish initial task if new
    if (!existingTask) {
      const initialTask: Task = {
        kind: 'task',
        id: taskId,
        contextId,
        status: {
          state: 'submitted',
          timestamp: new Date().toISOString(),
        },
        history: [userMessage],
        metadata: userMessage.metadata,
        artifacts: [],
      };
      eventBus.publish(initialTask);
    }

    // Publish working status
    eventBus.publish({
      kind: 'status-update',
      taskId,
      contextId,
      status: {
        state: 'working',
        message: {
          kind: 'message',
          role: 'agent',
          messageId: uuidv4(),
          parts: [{ kind: 'text', text: workingMessage }],
          taskId,
          contextId,
        },
        timestamp: new Date().toISOString(),
      },
      final: false,
    } satisfies TaskStatusUpdateEvent);

    // Extract text from message
    const userText = userMessage.parts
      .filter((p): p is TextPart => p.kind === 'text' && !!(p as TextPart).text)
      .map((p) => p.text)
      .join('\n');

    if (!userText) {
      eventBus.publish({
        kind: 'status-update',
        taskId,
        contextId,
        status: {
          state: 'failed',
          message: {
            kind: 'message',
            role: 'agent',
            messageId: uuidv4(),
            parts: [{ kind: 'text', text: 'No input message found to process.' }],
            taskId,
            contextId,
          },
          timestamp: new Date().toISOString(),
        },
        final: true,
      } satisfies TaskStatusUpdateEvent);
      eventBus.finished();
      return;
    }

    // Extract dataParts from A2A message
    const dataParts = userMessage.parts
      .filter((p): p is DataPart => p.kind === 'data')
      .map((p) => p.data);

    const currentTask: Task = existingTask || {
      kind: 'task',
      id: taskId,
      contextId,
      status: {
        state: 'working',
        timestamp: new Date().toISOString(),
      },
      history: [userMessage],
      artifacts: [],
    };

    try {
      // Get or create ADK session
      let session = await sessionService.getSession({
        appName,
        userId: 'user',
        sessionId: contextId,
      });

      if (!session) {
        session = await sessionService.createSession({
          appName,
          userId: 'user',
          sessionId: contextId,
        });
      }

      // Allow subclass to inject extra session state
      if (this.options.initSessionState) {
        this.options.initSessionState({ dataParts, session });
      }

      // Allow subclass to short-circuit before running the ADK agent
      if (this.options.shouldShortCircuit) {
        const shortCircuit = this.options.shouldShortCircuit({
          session,
          dataParts,
          eventBus,
          taskId,
          contextId,
        });
        if (shortCircuit) {
          eventBus.publish(shortCircuit);
          eventBus.finished();
          return;
        }
      }

      // Store A2A context in a side-channel that bypasses ADK's cloneDeep.
      // ADK's InMemorySessionService deep-clones session state on every
      // getSession() call, which breaks live object references (eventBus,
      // currentTask). The side-channel Map lets tools look up these objects
      // by session ID without going through cloneDeep.
      setA2AContext(session.id, { dataParts, eventBus, currentTask });

      try {
        // Allow subclass to preprocess the message
        let messageText = this.options.preprocessMessage?.({
          userText,
          dataParts,
          existingTask,
          session,
        }) ?? userText;

        // Append a structured summary of A2A data parts so the LLM knows
        // what data is available and can decide which tool to call. Tools
        // access the full objects via the side-channel, but the LLM needs
        // visibility into available keys and values to make correct decisions.
        if (dataParts.length > 0) {
          const dataPartSummaries = dataParts.map((dp) => {
            const entries = Object.entries(dp).map(([key, value]) => {
              // For large objects, show type + top-level keys; for scalars show the value
              if (value && typeof value === 'object') {
                const topKeys = Object.keys(value as Record<string, unknown>).slice(0, 5);
                return `  ${key}: {${topKeys.join(', ')}${topKeys.length < Object.keys(value as Record<string, unknown>).length ? ', ...' : ''}}`;
              }
              return `  ${key}: ${JSON.stringify(value)}`;
            });
            return entries.join('\n');
          });
          messageText += `\n\n[Available data parts — call the appropriate tool to process them, do NOT ask the user for this data]:\n${dataPartSummaries.join('\n')}`;
        }

        // Run ADK agent with a bounded number of LLM calls to prevent infinite loops
        const events = runner.runAsync({
          userId: 'user',
          sessionId: session.id,
          newMessage: {
            role: 'user',
            parts: [{ text: messageText }],
          },
          runConfig: {
            maxLlmCalls: this.options.maxLlmCalls ?? 10,
          },
        });

        // Collect response and stream intermediate status updates
        let responseText = '';
        let toolWasCalled = false;
        let lastToolResult: Record<string, unknown> | undefined;
        let agentEventCount = 0;

        for await (const event of events) {
          // Check for cancellation during execution
          if (this.isTaskCancelled(taskId)) {
            eventBus.finished();
            return;
          }

          const adkEvent = event as unknown as ADKEvent;
          // Count and extract content from any agent-authored event (root or
          // sub_agent). Sub_agents handle most user-facing replies in
          // multi-agent flows, so restricting to the root agent loses content.
          if (adkEvent.author && adkEvent.author !== 'user') {
            agentEventCount++;
            const parts = adkEvent.content?.parts;
            if (parts && Array.isArray(parts)) {
              // Extract text responses (skip internal thought parts)
              const textContent = parts.find((c) => c.text && !c.thought);
              if (textContent?.text) {
                responseText = textContent.text;
              }
              // Detect function calls
              if (parts.some((c) => c.functionCall)) {
                toolWasCalled = true;
              }
              // Extract function response results
              const funcResponse = parts.find((c) => c.functionResponse);
              if (funcResponse?.functionResponse?.response) {
                lastToolResult = funcResponse.functionResponse.response as Record<string, unknown>;
              }
            }
          }
        }

        // Detect silent LLM failures: no agent events means the model
        // likely returned an error that the ADK swallowed
        if (agentEventCount === 0) {
          console.error(`[${agentName}] No events received from ADK — possible LLM API error`);
          eventBus.publish({
            kind: 'status-update',
            taskId,
            contextId,
            status: {
              state: 'failed',
              message: {
                kind: 'message',
                role: 'agent',
                messageId: uuidv4(),
                parts: [{ kind: 'text', text: 'Agent failed: no response from LLM. Check API key and model configuration.' }],
                taskId,
                contextId,
              },
              timestamp: new Date().toISOString(),
            },
            final: true,
          } satisfies TaskStatusUpdateEvent);
          eventBus.finished();
          return;
        }

        // Re-fetch session to pick up state changes made by tools during
        // the runner execution. ADK's InMemorySessionService deep-clones on
        // getSession(), so the `session` variable from before the run is stale.
        const updatedSession = await sessionService.getSession({
          appName,
          userId: 'user',
          sessionId: contextId,
        });

        // Allow subclass to handle special post-processing
        if (this.options.postprocessResult) {
          const override = this.options.postprocessResult({
            responseText,
            toolWasCalled,
            lastToolResult,
            session: updatedSession || session,
            eventBus,
            taskId,
            contextId,
          });
          if (override) {
            eventBus.publish(override);
            eventBus.finished();
            return;
          }
          // If postprocessResult returns null, it handled publishing itself
          if (override === null) {
            eventBus.finished();
            return;
          }
        }

        // Default: publish completion
        const finalText = responseText ||
          (toolWasCalled ? 'Request processed successfully.' : 'Completed.');

        const agentMessage: Message = {
          kind: 'message',
          role: 'agent',
          messageId: uuidv4(),
          parts: [{ kind: 'text', text: finalText }],
          taskId,
          contextId,
        };

        eventBus.publish({
          kind: 'status-update',
          taskId,
          contextId,
          status: {
            state: 'completed',
            message: agentMessage,
            timestamp: new Date().toISOString(),
          },
          final: true,
        } satisfies TaskStatusUpdateEvent);
        eventBus.finished();

      } finally {
        clearA2AContext(session.id);
      }

    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';

      console.error(`[${agentName}] Error:`, errorMessage);

      eventBus.publish({
        kind: 'status-update',
        taskId,
        contextId,
        status: {
          state: 'failed',
          message: {
            kind: 'message',
            role: 'agent',
            messageId: uuidv4(),
            parts: [{ kind: 'text', text: `Agent error: ${errorMessage}` }],
            taskId,
            contextId,
          },
          timestamp: new Date().toISOString(),
        },
        final: true,
      } satisfies TaskStatusUpdateEvent);
      eventBus.finished();
    }
  }
}
