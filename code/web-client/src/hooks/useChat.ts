import {useCallback, useEffect, useMemo, useRef, useState} from 'react';

import {A2AClient} from '../a2aClient';
import {AGENT_URL, MERCHANT_TRIGGER_URL} from '../config';
import type {ChatMessage, InventoryMatch, InventoryOptionsArtifact, MandateApprovalData, MandateChainsFetched, MandateEntry, MandatesSigned, MonitoringStatus, OutgoingDataPayload, Part, ToolCallArtifact} from '../types';
import {isFunctionResponsePart, isToolCallArtifact} from '../types';
import {deriveMandateEntries} from '../utils/mandateEntries';
import {convertToStrictPart, extractErrorFromText, extractInventoryOptionsFromText, extractMandateFromText, extractMonitoringFromText, extractMonitoringJsonFromText, extractProductPreviewUnavailableFromText, extractPurchaseCompleteFromText, parseInvocationParts, parseMainArtifactData, parseToolAndInventoryArtifacts} from '../utils/parsing';

const a2aClient = new A2AClient(AGENT_URL);

/**
 * For short user replies (< 220 chars), prepend a thread recap with
 * instructions so the agent doesn't re-ask for product/budget.
 */
function augmentUserMessageForAgent(
    text: string,
    messages: ChatMessage[],
    ): string {
  if (text.length >= 220) return text;
  const lastUserMsgs = messages.filter((m) => m.role === 'user')
                           .slice(-8)
                           .map((m) => m.text ?? '')
                           .filter(Boolean);
  const lastAgentMsgs = messages.filter((m) => m.role === 'agent')
                            .slice(-4)
                            .map((m) => m.text ?? '')
                            .filter(Boolean);
  if (lastUserMsgs.length === 0 && lastAgentMsgs.length === 0) return text;
  const recap = [
    'Thread context (user last 8):',
    ...lastUserMsgs.map((m) => `  U: ${m.slice(0, 200)}`),
    'Agent last 4:',
    ...lastAgentMsgs.map((m) => `  A: ${m.slice(0, 300)}`),
    '',
    'Do not re-ask for product or budget. If user is confirming after product_preview_unavailable, build slug_0 item_id, call check_product with limited_drop=true, then emit mandate_request — do NOT call search_inventory.',
    '',
    `User says: ${text}`,
  ].join('\n');
  return recap;
}

/**
 * Update existing monitoring row in-place (by item_id, scanning backward)
 * or append a new one.
 */
function upsertMonitoringMessage(
    prev: ChatMessage[],
    monitoring: MonitoringStatus,
    text?: string,
    ): ChatMessage[] {
  const idx = [...prev].reverse().findIndex(
      (m) => m.artifactData &&
          (m.artifactData as {type?: string}).type === 'monitoring' &&
          (m.artifactData as MonitoringStatus).item_id === monitoring.item_id,
  );
  if (idx >= 0) {
    const realIdx = prev.length - 1 - idx;
    const updated = [...prev];
    updated[realIdx] = {
      ...updated[realIdx],
      artifactData: monitoring,
      text: text ?? updated[realIdx].text,
      timestamp: Date.now(),
    };
    return updated;
  }
  return [
    ...prev,
    {
      id: crypto.randomUUID(),
      role: 'agent' as const,
      artifactData: monitoring,
      text,
      timestamp: Date.now(),
    },
  ];
}

/**
 * Custom hook to manage chat state and operations with the A2A Agent.
 *
 * It handles message history, sending messages to the agent, streaming
 * responses, and managing UI states for tool calls, inventory lists, and
 * mandates.
 *
 * @returns An object containing:
 *   - messages: Array of ChatMessage objects.
 *   - input: String for the current chat input.
 *   - setInput: Function to update the chat input.
 *   - loading: Boolean indicating if the agent is responding.
 *   - pendingTaskId: String or undefined for active task tracing.
 *   - lastSelectedItemName: Name of the last item selected in inventory.
 *   - lastInventoryMatches: List of matches from the last inventory lookup.
 *   - lastInventoryOptions: Options for the last inventory lookup (e.g. qty,
 * cap).
 *   - usedServers: Set of backend tools/servers used by the agent.
 *   - isMonitoring: Boolean indicating if a monitoring task is active.
 *   - handleSend: Function to submit the current input text.
 *   - handleMandateApprove: Handler for approving a payment mandate.
 *   - handleMandateReject: Handler for rejecting a mandate.
 *   - sendToAgent: Function to send a raw string or structured object to the
 * agent.
 */
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const fetchMandate = useCallback(async(id: string): Promise<string> => {
    const resp = await fetch(`${AGENT_URL}/mandates/${id}`);
    if (!resp.ok) throw new Error(`Failed to fetch mandate ${id}`);
    return resp.text();
  }, []);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [pendingTaskId, setPendingTaskId] = useState<string|undefined>();
  const [lastSelectedItemName, setLastSelectedItemName] =
      useState<string|undefined>();
  const [lastInventoryMatches, setLastInventoryMatches] =
      useState<InventoryMatch[]|undefined>();
  const [lastInventoryOptions, setLastInventoryOptions] =
      useState<InventoryOptionsArtifact|undefined>();

  const loadingRef = useRef(loading);
  useEffect(() => {
    loadingRef.current = loading;
  }, [loading]);

  const pendingTriggerNudgeRef = useRef(false);

  const usedServers = useMemo(() => {
    const set = new Set<string>();
    for (const msg of messages) {
      if (msg.artifactData &&
          (msg.artifactData as {type?: string}).type === 'tool_call') {
        set.add((msg.artifactData as ToolCallArtifact).server);
      }
    }
    return set;
  }, [messages]);

  // Derive monitoring state from full thread scan (not just last message)
  const monitoringData = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.artifactData &&
          (m.artifactData as {type?: string}).type === 'monitoring') {
        return m.artifactData as MonitoringStatus;
      }
      if (m.text && m.role === 'agent') {
        const parsed = extractMonitoringFromText(m.text);
        if (parsed) return parsed;
      }
    }
    return undefined;
  }, [messages]);

  const hasPurchaseComplete = messages.some(
      (m) => m.artifactData &&
          (m.artifactData as {type?: string}).type === 'purchase_complete',
  );

  // Derive mandate entries for the Mandates tab by scanning messages.
  const mandates: MandateEntry[] = useMemo(
      () => deriveMandateEntries(messages),
      [messages],
  );

  const isMonitoring =
      monitoringData != null && !hasPurchaseComplete && !loading;

  const addMessage = useCallback((msg: Omit<ChatMessage, 'id'|'timestamp'>) => {
    setMessages(
        (prev) =>
            [...prev,
             {...msg, id: crypto.randomUUID(), timestamp: Date.now()},
    ]);
  }, []);

  const sendToAgent = useCallback(
      async (
          text: string|OutgoingDataPayload,
          taskId?: string,
          ) => {
        setLoading(true);
        const tid = taskId ?? crypto.randomUUID();
        setPendingTaskId(tid);
        let agentTextBuffer = '';
        const addedToolCallsInThisRun = new Set<string>();

        // Build a dedup key that distinguishes multiple invocations of the same
        // tool with different arguments (e.g. present_mandate_chain called
        // once per audience).
        const toolCallKey = (tc: ToolCallArtifact): string =>
            tc.args ? `${tc.tool}:${JSON.stringify(tc.args)}` : tc.tool;

        try {
          for await (const event of a2aClient.sendMessage(text, tid)) {
            if (event.type === 'status') {
              console.log(
                  '[useChat.ts] Received status event:',
                  JSON.stringify(event, null, 2));
              if (event.status.state === 'failed') {
                addMessage({
                  role: 'system',
                  text: 'Agent error: ' + JSON.stringify(event.status.message),
                });
              }
              const statusParts = event.status.message?.parts ?? [];

              // Intercept tool responses to inject mandates and trigger fetches
              for (const rawPart of statusParts) {
                if (isFunctionResponsePart(rawPart)) {
                  const toolName = rawPart.data.name;
                  const resp = rawPart.data.response as Record<string, unknown>;

                  if (toolName === 'assemble_and_sign_mandates_tool') {
                    if (typeof resp.open_checkout_mandate === 'string' &&
                        typeof resp.open_payment_mandate === 'string') {
                      console.log(
                          '[useChat.ts] Intercepted assemble_and_sign_mandates_tool response, fetching full mandates');
                      Promise
                          .all([
                            fetchMandate(resp.open_checkout_mandate),
                            fetchMandate(resp.open_payment_mandate)
                          ])
                          .then(([openChkToken, openPayToken]) => {
                            addMessage({
                              role: 'agent',
                              artifactData: {
                                type: 'mandates_signed',
                                open_checkout_mandate: openChkToken,
                                open_payment_mandate: openPayToken,
                              } as MandatesSigned,
                            });
                          })
                          .catch(
                              e => console.error(
                                  'Failed to fetch open mandates:', e));
                    }
                  } else if (
                      toolName === 'create_checkout_presentation' &&
                      typeof resp.checkout_mandate_chain_id === 'string') {
                    console.log(
                        '[useChat.ts] Intercepted create_checkout_presentation response, fetching full chain');
                    fetchMandate(resp.checkout_mandate_chain_id)
                        .then(token => {
                          addMessage({
                            role: 'agent',
                            artifactData: {
                              type: 'mandate_chains_fetched',
                              checkout_mandate_chain: token,
                            } as MandateChainsFetched,
                          });
                        })
                        .catch(
                            e => console.error(
                                'Failed to fetch checkout mandate:', e));
                  } else if (
                      toolName === 'create_payment_presentation' &&
                      typeof resp.payment_mandate_chain_id === 'string') {
                    console.log(
                        '[useChat.ts] Intercepted create_payment_presentation response, fetching full chain');
                    fetchMandate(resp.payment_mandate_chain_id)
                        .then(token => {
                          addMessage({
                            role: 'agent',
                            artifactData: {
                              type: 'mandate_chains_fetched',
                              payment_mandate_chain: token,
                            } as MandateChainsFetched,
                          });
                        })
                        .catch(
                            e => console.error(
                                'Failed to fetch payment mandate:', e));
                  }
                }
              }

              if (statusParts.length > 0) {
                const strictStatusParts =
                    statusParts.map((p) => convertToStrictPart(p))
                        .filter((p): p is Part => p !== undefined);
                const explicit =
                    parseToolAndInventoryArtifacts(strictStatusParts);
                const invocations = parseInvocationParts(strictStatusParts);
                const toolCalls: ToolCallArtifact[] = [
                  ...explicit.filter(isToolCallArtifact),
                  ...invocations,
                ];
                for (const tc of toolCalls) {
                  const key = toolCallKey(tc);
                  if (!addedToolCallsInThisRun.has(key)) {
                    addMessage({role: 'agent', artifactData: tc});
                    addedToolCallsInThisRun.add(key);
                  }
                }
              }
            } else if (event.type === 'artifact') {
              console.log(
                  '[useChat.ts] Received artifact event:',
                  JSON.stringify(event, null, 2));
              const parts = event.artifact.parts;
              for (const p of parts) {
                if (p.text) agentTextBuffer += p.text;
              }

              const explicit = parseToolAndInventoryArtifacts(
                  parts.map((p) => convertToStrictPart(p))
                      .filter((p): p is Part => p !== undefined));
              const invocations = parseInvocationParts(
                  parts.map((p) => convertToStrictPart(p))
                      .filter((p): p is Part => p !== undefined));
              const toolCalls: ToolCallArtifact[] = [
                ...explicit.filter(isToolCallArtifact),
                ...invocations,
              ];
              const inventoryOpts = explicit.filter(
                  (a): a is InventoryOptionsArtifact =>
                      (a as {type?: string}).type === 'inventory_options',
              );

              for (const tc of toolCalls) {
                const key = toolCallKey(tc);
                if (!addedToolCallsInThisRun.has(key)) {
                  addMessage({role: 'agent', artifactData: tc});
                  addedToolCallsInThisRun.add(key);
                }
              }
              for (const inv of inventoryOpts) {
                addMessage({role: 'agent', artifactData: inv});
                const sel = inv.matches.find((m) => m.item_id === inv.selected);
                if (sel) setLastSelectedItemName(sel.name);
                setLastInventoryMatches(inv.matches);
                setLastInventoryOptions(inv);
              }

              // Early monitoring extraction during streaming
              if (!event.artifact.lastChunk && agentTextBuffer) {
                const earlyMon = extractMonitoringJsonFromText(agentTextBuffer);
                if (earlyMon) {
                  setMessages(
                      (prev) => upsertMonitoringMessage(
                          prev, earlyMon, agentTextBuffer));
                }
              }

              let showedInventoryFromText = false;
              if (event.artifact.lastChunk && agentTextBuffer) {
                if (inventoryOpts.length === 0) {
                  const inv = extractInventoryOptionsFromText(agentTextBuffer);
                  if (inv) {
                    addMessage({role: 'agent', artifactData: inv});
                    showedInventoryFromText = true;
                    const sel =
                        inv.matches.find((m) => m.item_id === inv.selected);
                    if (sel) setLastSelectedItemName(sel.name);
                    setLastInventoryMatches(inv.matches);
                    setLastInventoryOptions(inv);
                  }
                }
              }

              if (event.artifact.lastChunk) {
                const strictParts =
                    parts.map((p) => convertToStrictPart(p))
                        .filter((p): p is Part => p !== undefined);
                const mainData = parseMainArtifactData(strictParts) ??
                    (agentTextBuffer ?
                         (extractMandateFromText(agentTextBuffer) ??
                          extractProductPreviewUnavailableFromText(
                              agentTextBuffer) ??
                          extractPurchaseCompleteFromText(agentTextBuffer) ??
                          extractErrorFromText(agentTextBuffer) ??
                          extractMonitoringFromText(agentTextBuffer)) :
                         undefined);

                // For monitoring artifacts, upsert instead of append
                if (mainData &&
                    (mainData as {type?: string}).type === 'monitoring') {
                  setMessages(
                      (prev) => upsertMonitoringMessage(
                          prev,
                          mainData as MonitoringStatus,
                          agentTextBuffer || undefined,
                          ),
                  );
                } else if (mainData) {
                  addMessage({
                    role: 'agent',
                    artifactData: mainData,
                    text: agentTextBuffer || undefined,
                  });
                } else if (
                    agentTextBuffer && inventoryOpts.length === 0 &&
                    !showedInventoryFromText) {
                  addMessage({role: 'agent', text: agentTextBuffer});
                }
                agentTextBuffer = '';
              }
            }
          }
        } catch (e) {
          addMessage({role: 'system', text: 'Connection error: ' + String(e)});
        } finally {
          setLoading(false);
        }
      },
      [addMessage]);

  // Trigger-state polling: 500ms interval while monitoring
  const lastTriggerStateRef = useRef<string>('');
  useEffect(
      () => {
        if (!isMonitoring || !monitoringData?.item_id) return;
        const interval = setInterval(async () => {
          try {
            const resp = await fetch(
                `${MERCHANT_TRIGGER_URL}/state?item_id=${
                    encodeURIComponent(monitoringData.item_id)}`,
            );
            if (!resp.ok) return;
            const json = await resp.json();
            const str = JSON.stringify(json);
            if (str !== lastTriggerStateRef.current &&
                lastTriggerStateRef.current !== '') {
              pendingTriggerNudgeRef.current = true;
            }
            lastTriggerStateRef.current = str;
          } catch {
            // ignore fetch errors
          }
        }, 500);
        return () => clearInterval(interval);
      },
      [isMonitoring, monitoringData?.item_id],
  );

  // When loading clears and a trigger nudge is pending, send check_product_now
  useEffect(
      () => {
        if (!loading && pendingTriggerNudgeRef.current &&
            monitoringData?.item_id && monitoringData?.price_cap != null &&
            !hasPurchaseComplete) {
          pendingTriggerNudgeRef.current = false;
          sendToAgent(
              {
                type: 'check_product_now',
                item_id: monitoringData.item_id,
                price_cap: monitoringData.price_cap,
                qty: monitoringData.qty ?? 1,
                open_checkout_mandate: monitoringData.open_checkout_mandate,
                open_payment_mandate: monitoringData.open_payment_mandate,
                message: 'Check product now',
                source: 'trigger_state_watch',
              },
              pendingTaskId,
          );
        }
      },
      [
        loading, monitoringData, hasPurchaseComplete, sendToAgent, pendingTaskId
      ]);

  // Auto-poll fallback (15s)
  useEffect(
      () => {
        if (!isMonitoring || hasPurchaseComplete || !pendingTaskId) return;
        const interval = setInterval(() => {
          if (!loadingRef.current) {
            const msg = monitoringData?.item_id != null &&
                    monitoringData?.price_cap != null ?
                {
                  type: 'check_product_now' as const,
                  item_id: monitoringData.item_id,
                  price_cap: monitoringData.price_cap,
                  qty: monitoringData.qty ?? 1,
                  open_checkout_mandate: monitoringData.open_checkout_mandate,
                  open_payment_mandate: monitoringData.open_payment_mandate,
                  message: 'Check product now',
                  source: 'auto_poll' as const,
                } :
                'Check price now';
            sendToAgent(msg, pendingTaskId);
          }
        }, 15000);
        return () => clearInterval(interval);
      },
      [
        isMonitoring,
        hasPurchaseComplete,
        pendingTaskId,
        monitoringData?.item_id,
        monitoringData?.price_cap,
        monitoringData?.open_checkout_mandate,
        monitoringData?.open_payment_mandate,
        sendToAgent,
      ]);

  async function handleSend(opts?: {fallbackIfEmpty?: string}) {
    const raw = input.trim();
    const text = raw || opts?.fallbackIfEmpty;
    if (!text) return;
    setInput('');
    const augmented = augmentUserMessageForAgent(text, messages);
    addMessage({role: 'user', text});
    await sendToAgent(augmented);
  }

  async function handleMandateApprove(mandateRequest: MandateApprovalData) {
    addMessage({
      role: 'user_action',
      userActionLabel: 'Approved mandate',
      userActionSublabel: 'User signed over the TS surface with agent provider key',
    });
    await sendToAgent(
        {type: 'mandate_approved', mandate_request: mandateRequest},
        pendingTaskId,
    );
  }

  function handleMandateReject() {
    addMessage({role: 'system', text: 'Mandate rejected. Purchase cancelled.'});
  }

  return {
    messages,
    input,
    setInput,
    loading,
    pendingTaskId,
    lastSelectedItemName,
    setLastSelectedItemName,
    lastInventoryMatches,
    lastInventoryOptions,
    usedServers,
    isMonitoring,
    mandates,
    handleSend,
    handleMandateApprove,
    handleMandateReject,
    sendToAgent,
  };
}

/**
 * Return shape of {@link useChat}; use this for props instead of duplicating
 * fields.
 */
export type ChatState = ReturnType<typeof useChat>;
