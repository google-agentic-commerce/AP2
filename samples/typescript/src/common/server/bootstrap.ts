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

import express from 'express';
import type { Server } from 'http';
import type { AgentCard } from '@a2a-js/sdk';
import {
  InMemoryTaskStore,
  type AgentExecutor,
  DefaultRequestHandler,
} from '@a2a-js/sdk/server';
import { A2AExpressApp } from '@a2a-js/sdk/server/express';
import { createRateLimiter, validateA2ARequest } from './middleware.js';

interface BootstrapOptions {
  agentCard: AgentCard;
  agentExecutor: AgentExecutor;
  port: number;
  label: string;
}

/**
 * Bootstraps an A2A Express server with rate limiting and validation.
 * Returns the HTTP server handle for graceful shutdown and testing.
 */
export function bootstrapServer(options: BootstrapOptions): Server {
  const { agentCard, agentExecutor, port, label } = options;

  const taskStore = new InMemoryTaskStore();
  const requestHandler = new DefaultRequestHandler(
    agentCard,
    taskStore,
    agentExecutor
  );

  const appBuilder = new A2AExpressApp(requestHandler);
  const app = express();

  // Parse JSON bodies before validation middleware can inspect them.
  // A JSON error handler is required here because the SDK adds its own
  // express.json() + jsonErrorHandler on the router, but this app-level
  // parser runs first. Without a handler, a SyntaxError from malformed
  // JSON (e.g. bad escape sequences) propagates to Express's default
  // error handler which crashes the agent process.
  app.use(express.json());
  app.use((err: Error, _req: express.Request, res: express.Response, next: express.NextFunction) => {
    if (err instanceof SyntaxError && 'body' in err) {
      res.status(400).json({
        jsonrpc: '2.0',
        id: null,
        error: {
          code: -32700,
          message: 'Parse error: invalid JSON in request body.',
        },
      });
      return;
    }
    next(err);
  });

  // Apply middleware before A2A routes
  app.use(createRateLimiter({ windowMs: 60_000, maxRequests: 60 }));
  app.use(validateA2ARequest);

  // Health check endpoint
  app.get('/health', (_req: express.Request, res: express.Response) => {
    res.json({ status: 'ok', agent: agentCard.name, timestamp: new Date().toISOString() });
  });

  const expressApp = appBuilder.setupRoutes(app);

  const PORT = process.env.PORT || port;
  const server = expressApp.listen(PORT, () => {
    console.log(`[${label}] Running on http://localhost:${PORT}`);
  });

  // Workaround: keep the event loop alive on Node v23+ with tsx where
  // ADK agent imports can cause the server's TCP handle to be unref'd
  const keepAlive = setInterval(() => {}, 1 << 30);
  server.on('close', () => clearInterval(keepAlive));

  return server;
}
