/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Shopping Agent v2 A2A server (Human-Not-Present).
 * Mirrors the Python `shopping_agent_v2/run_server.py`.
 */

import { Runner } from '@google/adk';
import type { AgentCard } from '@a2a-js/sdk';

import { shoppingAgentV2 } from './agent.js';
import { sessionService } from '../../common/config/session.js';
import { BaseAgentExecutor } from '../../common/server/base-executor.js';
import { bootstrapServer } from '../../common/server/bootstrap.js';

const PORT = Number(process.env.AGENT_PORT ?? 8080);

const runner = new Runner({
  appName: 'ap2-shopping-v2',
  agent: shoppingAgentV2,
  sessionService,
});

const agentExecutor = new BaseAgentExecutor({
  agentName: 'shopping_agent',
  appName: 'ap2-shopping-v2',
  runner,
  maxLlmCalls: 20,
  workingMessage: 'The shopping agent is monitoring your drop...',
});

const agentCard: AgentCard = {
  name: 'Shopping Agent v2',
  description:
    'Human-Not-Present shopping agent. Holds signed open mandates and ' +
    'autonomously executes purchases when price/availability constraints are met.',
  url: `http://localhost:${PORT}/a2a/shopping_agent`,
  provider: { organization: 'AP2 TypeScript samples', url: 'https://github.com/google-agentic-commerce/AP2' },
  skills: [
    {
      id: 'monitor_and_purchase',
      name: 'Monitor and Purchase',
      description:
        'Captures user intent, signs open mandates, monitors the merchant for ' +
        'price/availability changes, and executes purchase autonomously.',
      parameters: {
        type: 'object',
        properties: {
          user_intent: {
            type: 'string',
            description: 'Natural-language description of what to buy and the constraints.',
          },
        },
        required: ['user_intent'],
      },
      tags: ['shopping', 'hnp', 'autonomous'],
    } as AgentCard['skills'][number],
  ],
  capabilities: {
    streaming: true,
    pushNotifications: false,
    stateTransitionHistory: true,
    extensions: [
      {
        uri: 'https://github.com/google-agentic-commerce/ap2/v1',
        description: 'Supports the Agent Payments Protocol.',
        required: true,
      },
    ],
  },
  defaultInputModes: ['application/json'],
  defaultOutputModes: ['application/json'],
  protocolVersion: '0.3.0',
  version: '0.2.0',
};

bootstrapServer({ agentCard, agentExecutor, port: PORT, label: 'Shopping Agent v2' });
