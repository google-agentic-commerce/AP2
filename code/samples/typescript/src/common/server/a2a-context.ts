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

import type { Task } from '@a2a-js/sdk';
import type { ExecutionEventBus } from '@a2a-js/sdk/server';

/**
 * Per-request A2A context that must bypass ADK's session cloneDeep.
 *
 * ADK's InMemorySessionService deep-clones session state on every
 * getSession/createSession call, which breaks live object references
 * (eventBus methods, task object identity). This module-level Map
 * provides a side-channel for tools to access these live objects.
 */
export interface A2AContext {
  dataParts: Record<string, unknown>[];
  eventBus: ExecutionEventBus;
  currentTask: Task;
}

const contextStore = new Map<string, A2AContext>();

/** Store A2A context for a session. Called by executor before runner.runAsync. */
export function setA2AContext(sessionId: string, ctx: A2AContext): void {
  contextStore.set(sessionId, ctx);
}

/** Retrieve A2A context inside a tool. Uses the session ID from tool context. */
export function getA2AContext(sessionId: string): A2AContext | undefined {
  return contextStore.get(sessionId);
}

/** No-op event bus for ADK dev mode (npm run dev) where no A2A server is running. */
const noopEventBus: ExecutionEventBus = {
  publish: () => {},
  finished: () => {},
} as unknown as ExecutionEventBus;

/**
 * Retrieve A2A context from a tool's execution context.
 * This is the primary API for tools to access dataParts, eventBus, and currentTask.
 *
 * When running in ADK dev mode (npm run dev), no BaseAgentExecutor is active,
 * so no A2A context exists. In that case, returns a fallback context with
 * empty dataParts and a no-op eventBus so tools degrade gracefully.
 *
 * @param toolContext - The tool's execution context (second arg of FunctionTool.execute)
 * @returns The A2A context with dataParts, eventBus, and currentTask
 */
export function getA2AContextFromTool(toolContext: {
  invocationContext: { session: { id: string } };
}): A2AContext {
  const sessionId = toolContext.invocationContext.session.id;
  const ctx = contextStore.get(sessionId);
  if (!ctx) {
    // ADK dev mode fallback: no A2A server running, return safe defaults
    console.warn(
      `[A2A] No context for session ${sessionId} — running in ADK dev mode. ` +
      'Using fallback (empty dataParts, no-op eventBus).'
    );
    return {
      dataParts: [],
      eventBus: noopEventBus,
      currentTask: {
        kind: 'task',
        id: sessionId,
        contextId: sessionId,
        status: { state: 'working', timestamp: new Date().toISOString() },
        history: [],
        artifacts: [],
      } as Task,
    };
  }
  return ctx;
}

/** Clean up after request completes. Called by executor after runner finishes. */
export function clearA2AContext(sessionId: string): void {
  contextStore.delete(sessionId);
}
