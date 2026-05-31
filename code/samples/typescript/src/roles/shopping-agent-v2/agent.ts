/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Shopping Agent v2 — Human-Not-Present.
 *
 * Mirrors the Python `shopping_agent_v2` sub-agent hierarchy:
 *   consent_agent (root) -> monitoring_agent -> purchase_agent (leaf).
 *
 * - consent_agent: drop/budget dialogue + open-mandate signing, then transfers
 *   to monitoring.
 * - monitoring_agent: watches price/availability, transfers to purchase when the
 *   open-mandate constraints are satisfied and the item is available.
 * - purchase_agent: runs the autonomous purchase pipeline (assemble cart ->
 *   create checkout -> closed-mandate presentations -> issue payment credential
 *   -> complete checkout -> verify receipts).
 *
 * Each agent owns its OWN set of MCPToolset instances (separate stdio
 * connections) per ADK best practice — sharing a single toolset across agents
 * causes stdio connection conflicts (see google/adk-python#712). Each MCP
 * toolset launches the corresponding `*-mcp/server.ts` as a stdio subprocess.
 */

import { LlmAgent, MCPToolset } from '@google/adk';
import type { BaseTool } from '@google/adk';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  assembleAndSignMandatesTool,
  checkConstraintsAgainstMandateTool,
  createCheckoutPresentationTool,
  createPaymentPresentationTool,
  verifyCheckoutReceiptTool,
  resetTempDbTool,
} from './mandate-tools.js';
import { CONSENT_INSTRUCTION } from './prompts/consent.js';
import { MONITORING_INSTRUCTION } from './prompts/monitoring.js';
import { PURCHASE_INSTRUCTION } from './prompts/purchase.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROLES_DIR = path.resolve(__dirname, '..');

const MERCHANT_SERVER = path.join(ROLES_DIR, 'merchant-agent-mcp/server.ts');
const CREDENTIAL_SERVER = path.join(ROLES_DIR, 'credentials-provider-mcp/server.ts');
const PSP_SERVER = path.join(ROLES_DIR, 'merchant-payment-processor-mcp/server.ts');

const MCP_ENV = {
  ...process.env,
  LOGS_DIR: process.env.LOGS_DIR ?? path.resolve(ROLES_DIR, '../../.logs'),
  TEMP_DB_DIR: process.env.TEMP_DB_DIR ?? path.resolve(ROLES_DIR, '../../.temp-db'),
} as Record<string, string>;

/**
 * Build a fresh MCPToolset that launches an `*-mcp/server.ts` over stdio.
 *
 * A new instance is created per call (and per agent) on purpose: sharing one
 * toolset across agents reuses the same stdio session and conflicts.
 *
 * @param serverEntry Absolute path to the MCP server entrypoint.
 * @param toolFilter Optional allowlist of tool names or a predicate.
 * @returns A configured MCPToolset.
 */
function makeMcpToolset(
  serverEntry: string,
  toolFilter?: string[] | ((tool: BaseTool) => boolean),
): MCPToolset {
  return new MCPToolset(
    {
      type: 'StdioConnectionParams',
      serverParams: {
        command: 'npx',
        args: ['tsx', serverEntry],
        env: MCP_ENV,
      },
      timeout: 60_000,
    },
    toolFilter,
  );
}

const MODEL = process.env.AGENT_MODEL ?? 'gemini-2.5-flash';

/**
 * Reformat any MCP/mandate tool error into a structured artifact and escalate
 * so the LLM reliably stops and emits exactly {type:'error', error, message}.
 *
 * Returning a replacement object becomes the tool result the model sees, and
 * setting `context.actions.escalate` halts further sub-agent processing.
 */
const errorEscalationCallback = ({
  tool,
  response,
  context,
}: {
  tool: BaseTool;
  args: Record<string, unknown>;
  response: Record<string, unknown>;
  context: { actions: { escalate?: boolean } };
}): Record<string, unknown> | undefined => {
  if (response && typeof response === 'object' && 'error' in response) {
    const error = (response as { error: unknown }).error;
    const message = 'message' in response ? (response as { message: unknown }).message : String(response);
    context.actions.escalate = true;
    const errorJson = JSON.stringify({ type: 'error', error, message });
    return {
      error,
      message,
      action_required:
        `STOP all processing for tool "${tool.name}". Emit EXACTLY this JSON ` +
        `as your complete response, nothing else: ${errorJson}`,
    };
  }
  return undefined;
};

export const purchaseAgent = new LlmAgent({
  name: 'purchase_agent',
  model: MODEL,
  description:
    'Executes the autonomous purchase flow once price and availability satisfy ' +
    'the open mandates: assemble_cart, create_checkout, closed mandates, ' +
    'issue_payment_credential, complete_checkout, and receipt verification.',
  instruction: PURCHASE_INSTRUCTION,
  outputKey: 'purchase_result',
  tools: [
    checkConstraintsAgainstMandateTool,
    createCheckoutPresentationTool,
    createPaymentPresentationTool,
    verifyCheckoutReceiptTool,
    makeMcpToolset(MERCHANT_SERVER),
    makeMcpToolset(CREDENTIAL_SERVER),
    // The purchase agent must NOT settle directly via the PSP; filter out
    // initiate_payment (mirrors the Python tool_filter lambda).
    makeMcpToolset(PSP_SERVER, (tool) => tool.name !== 'initiate_payment'),
  ],
  afterToolCallback: errorEscalationCallback,
});

export const monitoringAgent = new LlmAgent({
  name: 'monitoring_agent',
  model: MODEL,
  description:
    'Holds the open mandates and monitors item price and availability via ' +
    'check_product. Transfers to purchase_agent when the price is within the ' +
    'mandate and the merchant reports the item as available.',
  instruction: MONITORING_INSTRUCTION,
  outputKey: 'monitoring_result',
  tools: [checkConstraintsAgainstMandateTool, makeMcpToolset(MERCHANT_SERVER)],
  subAgents: [purchaseAgent],
  afterToolCallback: errorEscalationCallback,
});

export const consentAgent = new LlmAgent({
  name: 'consent_agent',
  model: MODEL,
  description:
    'Handles drop/budget dialogue, item selection, and open-mandate signing. ' +
    'Transfers to monitoring_agent after the mandates are approved or on ' +
    '"Check price now".',
  instruction: CONSENT_INSTRUCTION,
  outputKey: 'consent_result',
  tools: [
    resetTempDbTool,
    assembleAndSignMandatesTool,
    checkConstraintsAgainstMandateTool,
    makeMcpToolset(MERCHANT_SERVER),
  ],
  subAgents: [monitoringAgent],
  afterToolCallback: errorEscalationCallback,
});

export const shoppingAgentV2 = consentAgent;

export { shoppingAgentV2 as rootAgent };
