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

import type { Request, Response, NextFunction } from 'express';

/**
 * Simple in-memory rate limiter for A2A endpoints.
 * Tracks request counts per IP within a fixed window.
 */
export function createRateLimiter(options: {
  windowMs: number;
  maxRequests: number;
}) {
  const { windowMs, maxRequests } = options;
  const requestCounts = new Map<string, { count: number; resetTime: number }>();

  // Periodic cleanup of expired entries
  const cleanupTimer = setInterval(() => {
    const now = Date.now();
    for (const [key, entry] of requestCounts) {
      if (now > entry.resetTime) {
        requestCounts.delete(key);
      }
    }
  }, windowMs);
  cleanupTimer.unref();

  return (req: Request, res: Response, next: NextFunction): void => {
    const clientIp = req.ip || req.socket.remoteAddress || 'unknown';
    const now = Date.now();

    const entry = requestCounts.get(clientIp);

    if (!entry || now > entry.resetTime) {
      requestCounts.set(clientIp, { count: 1, resetTime: now + windowMs });
      next();
      return;
    }

    if (entry.count >= maxRequests) {
      const requestId = req.body?.id ?? null;
      res.status(429).json({
        jsonrpc: '2.0',
        id: requestId,
        error: {
          code: -32000,
          message: 'Too many requests. Please try again later.',
        },
      });
      return;
    }

    entry.count++;
    next();
  };
}

/**
 * Validates that incoming JSON-RPC requests have the required A2A structure.
 */
export function validateA2ARequest(req: Request, res: Response, next: NextFunction): void {
  // Only validate POST requests to the A2A endpoint
  if (req.method !== 'POST' || !req.path.endsWith('/')) {
    next();
    return;
  }

  const body = req.body;
  const requestId = body?.id ?? null;

  if (!body || typeof body !== 'object') {
    res.status(400).json({
      jsonrpc: '2.0',
      id: null,
      error: {
        code: -32600,
        message: 'Invalid request: body must be a JSON object.',
      },
    });
    return;
  }

  if (body.jsonrpc !== '2.0') {
    res.status(400).json({
      jsonrpc: '2.0',
      id: requestId,
      error: {
        code: -32600,
        message: 'Invalid request: jsonrpc must be "2.0".',
      },
    });
    return;
  }

  if (!body.method || typeof body.method !== 'string') {
    res.status(400).json({
      jsonrpc: '2.0',
      id: requestId,
      error: {
        code: -32600,
        message: 'Invalid request: method is required.',
      },
    });
    return;
  }

  next();
}
