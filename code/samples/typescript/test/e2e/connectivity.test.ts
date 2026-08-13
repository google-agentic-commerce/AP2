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

import { describe, it, expect } from 'vitest';
import { A2AClient } from '@a2a-js/sdk/client';
import { v4 as uuidv4 } from 'uuid';

const SHOPPING_AGENT_URL = 'http://localhost:8001/.well-known/agent-card.json';

describe('Shopping Agent connectivity', () => {
  it('serves an agent card', async () => {
    const response = await fetch(SHOPPING_AGENT_URL);
    expect(response.ok).toBe(true);
    const card = await response.json();
    expect(card.name).toBeTruthy();
  });

  it('responds to a basic message via A2A', async () => {
    const client = await A2AClient.fromCardUrl(SHOPPING_AGENT_URL);

    const stream = client.sendMessageStream({
      message: {
        kind: 'message',
        messageId: uuidv4(),
        role: 'user',
        contextId: uuidv4(),
        parts: [{ kind: 'text', text: 'Hello, are you working?' }],
      },
    });

    const events: unknown[] = [];
    for await (const event of stream) {
      events.push(event);
      if (events.length >= 5) break;
    }
    expect(events.length).toBeGreaterThan(0);
  }, 15_000);
});
