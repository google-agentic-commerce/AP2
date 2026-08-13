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
 *
 * End-to-end smoke test for the AP2 payment flow:
 *   user request → cart → shipping → payment method → mandate → receipt.
 *
 * Assumes the four agents are already running locally (see scenario README).
 */

import { describe, it, expect } from 'vitest';
import { A2AClient } from '@a2a-js/sdk/client';
import type { Task } from '@a2a-js/sdk';
import { v4 as uuidv4 } from 'uuid';

const SHOPPING_AGENT_URL = 'http://localhost:8001/.well-known/agent-card.json';

describe('AP2 payment flow (e2e)', () => {
  it('initiates a shopping flow and reaches a working, completed, or input-required state', async () => {
    const client = await A2AClient.fromCardUrl(SHOPPING_AGENT_URL);

    const stream = client.sendMessageStream({
      message: {
        kind: 'message',
        messageId: uuidv4(),
        role: 'user',
        contextId: uuidv4(),
        parts: [{ kind: 'text', text: 'I want to buy running shoes' }],
      },
    });

    let lastTask: Task | null = null;
    for await (const event of stream) {
      if (event.kind === 'task') lastTask = event;
    }

    expect(lastTask).not.toBeNull();
    expect(['working', 'completed', 'input-required']).toContain(
      lastTask!.status.state,
    );
  }, 60_000);
});
