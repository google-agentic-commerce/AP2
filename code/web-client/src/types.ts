// ============================================================================
// A2A CORE & WIRE FORMAT
// Core messaging formats for Agent-to-Agent/Agent-to-App communication.
// ============================================================================

/**
 * A2A Message object containing a role and parts.
 */
export interface A2AMessage {
  role: 'user'|'agent';
  parts: A2APart[];
}

/**
 * A2A Part object representing text, data, or tool calls.
 */
export interface A2APart {
  text?: string;
  data?: Record<string, unknown>;
  mimeType?: string;
  kind?: string;
  /** A2A invocation/function call name */
  name?: string;
  /** Additional metadata provided by the agent framework */
  metadata?: { adk_type?: string; [key: string]: unknown };
}

/**
 * A2A Artifact representing stream chunks of a task.
 */
export interface A2AArtifact {
  index: number;
  parts: A2APart[];
  lastChunk?: boolean;
}

/**
 * A2A status updates for tasks.
 */
export interface A2ATaskStatus {
  state: 'submitted'|'working'|'completed'|'failed'|'canceled';
  message?: A2AMessage;
  timestamp?: string;
  metadata?: Record<string, unknown>;
}

/**
 * Strict internal domain representation of a message part.
 * Using a discriminated union ensures type safety in client-side processing
 * and rendering (unlike the loose A2APart wire-format).
 */
export type Part =|{
  kind: 'text';
  text: string
}
|{
  kind: 'tool_call';
  tool_call: {name: string; arguments: Record<string, unknown>}
}
|{
  kind: 'data';
  data: Record<string, unknown>
};

// ============================================================================
// INCOMING AGENT ARTIFACTS
// Specific event payloads received from the agent.
// ============================================================================

/**
 * A user request given to the agent to build a mandate.
 */
export interface MandateRequest {
  type: "mandate_request";
  item_id: string;
  item_name?: string;
  price_cap: number;
  qty?: number;
  constraint_focus?: 'availability'|'price';
  available?: boolean;
  constraints?: { price_lt?: number };
  instructions?: string;
  matches?: Array<{ item_id: string; name: string; price: number }>;
  current_price?: number;
  payment_method?: string;
  payment_method_description?: string;
}

/**
 * Event indicating a successful purchase matching the mandate.
 */
export interface PurchaseComplete {
  type: "purchase_complete";
  order_id: string;
  /** The closed payment mandate content (decoded JSON) used for the payment. */
  closed_payment_mandate_content?: Record<string, unknown>;
}

/**
 * Event communicating an error from an agent operation.
 */
export interface ErrorArtifact {
  type: "error";
  error: string;
  message: string;
  task_id?: string;
}

/**
 * Event providing the current active monitoring status of an item.
 */
export interface MonitoringStatus {
  type: "monitoring";
  item_id: string;
  price_cap: number;
  qty?: number;
  available?: boolean;
  constraint_focus?: 'availability'|'price';
  meets_constraints?: boolean;
  message?: string;
  task_id?: string;
  /** Current price from check_product (optional) */
  current_price?: number;
  /**
   * Open mandates (JSON strings) — pass back with check_product_now so agent
   * doesn't reassemble
   */
  open_checkout_mandate?: string;
  open_payment_mandate?: string;
}

/**
 * Event representing a tool call interception for display.
 */
export interface ToolCallArtifact {
  type: "tool_call";
  tool: string;
  server: string;
  message: string;
  /** Raw arguments passed to the tool invocation, when captured from the A2A stream. */
  args?: Record<string, unknown>;
}

/**
 * Event showing an item match during inventory search.
 */
export interface InventoryMatch {
  item_id: string;
  name: string;
  price: number;
  stock?: number;
}

/**
 * Options presented when resolving an inventory search query.
 */
export interface InventoryOptionsArtifact {
  type: "inventory_options";
  matches: InventoryMatch[];
  selected?: string;
  price_cap?: number;
  qty?: number;
}

/**
 * The unified set of message data types dispatched from agents.
 */
export interface ProductPreviewUnavailable {
  type: 'product_preview_unavailable';
  product_name: string;
  product_subtitle?: string;
  image_emoji?: string;
  typical_list_price?: number;
  drop_scheduled_hint?: string;
  sku_preview_id?: string;
}

/**
 * Event indicating that open mandates have been signed.
 */
export interface MandatesSigned {
  type: "mandates_signed";
  open_checkout_mandate: string;
  open_payment_mandate: string;
}

/**
 * Event indicating that closed mandates have been created and stored.
 */
export interface MandatesCreated {
  type: "mandates_created";
  checkout_mandate_chain_id: string;
  payment_mandate_chain_id: string;
}

/**
 * Event indicating that a mandate chain has been presented.
 */
export interface MandatePresented {
  type: "mandate_presented";
  presented_mandate: string;
  purpose?: string;
}

/**
 * Event indicating that mandate chains have been fetched from the backend.
 */
export interface MandateChainsFetched {
  type: "mandate_chains_fetched";
  payment_mandate_chain?: string;
  checkout_mandate_chain?: string;
}

export type AgentArtifactData =|MandateRequest|PurchaseComplete|ErrorArtifact|
    MonitoringStatus|ToolCallArtifact|InventoryOptionsArtifact|
    ProductPreviewUnavailable|MandatesSigned|MandatesCreated|MandatePresented|MandateChainsFetched|Record<string, unknown>;

// ============================================================================
// OUTGOING PAYLOADS (CLIENT TO AGENT)
// Payloads sent from the client UI back to the agent.
// ============================================================================

/**
 * Payload sent when selecting an item from inventory search.
 */
export interface ItemSelectedPayload {
  type: 'item_selected';
  item_id: string;
  price_cap: number;
  qty: number;
}

/**
 * Payload sent by polling or manual request to check price.
 */
export interface CheckProductNowPayload {
  type: 'check_product_now';
  item_id: string;
  price_cap: number;
  qty: number;
  open_checkout_mandate?: string;
  open_payment_mandate?: string;
  message?: string;
  source?: 'auto_poll'|'manual'|'trigger_state_watch';
}

/**
 * Payload sent when approving a mandate request.
 */
export interface MandateApprovalData {
  item_id: string;
  item_name?: string;
  price_cap: number;
  qty: number;
  constraints: {price_lt: number};
  matches?: Array<{item_id: string; name: string}>;
}

export interface MandateApprovedPayload {
  type: 'mandate_approved';
  mandate_request: MandateApprovalData;
}

/**
 * The unified set of outgoing data payloads sent from client to agent.
 */
export type OutgoingDataPayload =
    |ItemSelectedPayload|CheckProductNowPayload|MandateApprovedPayload;

// ============================================================================
// UI / PRESENTATION MODELS
// Models strictly used for rendering in the front-end.
// ============================================================================

/**
 * UI representation of an agent or user message thread item.
 */
export interface ChatMessage {
  id: string;
  role: "user" | "agent" | "system" | "user_action";
  text?: string;
  artifactData?: AgentArtifactData;
  /** For user_action: display label */
  userActionLabel?: string;
  userActionSublabel?: string;
  timestamp: number;
}

// ============================================================================
// MANDATE VIEWER
// Typed summary of mandate/SD-JWT artifacts surfaced in the Mandates tab.
// ============================================================================

export type MandateEntryKind =
  | 'mandate_request'
  | 'open_checkout_mandate'
  | 'open_payment_mandate'
  | 'checkout_jwt'
  | 'closed_checkout_mandate'
  | 'closed_payment_mandate'
  | 'presentation'
  | 'mandate_chain';

/**
 * A single mandate-related artifact captured during a chat session.
 * - `rawToken` is the encoded SD-JWT (or JWT) string when available.
 * - `rawPayload` is the decoded JSON object form (for artifacts delivered as
 *   JSON rather than SD-JWT strings, e.g. mandate_request, closed_payment
 *   content).
 */
export interface MandateEntry {
  id: string;
  kind: MandateEntryKind;
  /** Human-facing short label ("Open Checkout Mandate", "Presentation → Merchant"). */
  title: string;
  /** Optional subtitle (e.g. audience, item name). */
  subtitle?: string;
  timestamp: number;
  /** The encoded SD-JWT / JWT token string, when this entry represents one. */
  rawToken?: string;
  /** The decoded JSON payload, when this entry represents a plain JSON object. */
  rawPayload?: Record<string, unknown>;
}

// ============================================================================
// UTILITIES & TYPE GUARDS
// ============================================================================

/**
 * Asserts an object matches ToolCallArtifact signature.
 */
export function isToolCallArtifact(data: unknown): data is ToolCallArtifact {
  return (
      typeof data === 'object' && data !== null && 'type' in data &&
      (data as Record<string, unknown>).type === 'tool_call');
}

/**
 * Asserts an object matches InventoryOptionsArtifact signature.
 */
export function isInventoryOptionsArtifact(data: unknown):
    data is InventoryOptionsArtifact {
  return (
      typeof data === 'object' && data !== null && 'type' in data &&
      (data as Record<string, unknown>).type === 'inventory_options');
}

/**
 * Payload of a function response.
 */
export interface FunctionResponseData {
  name: string;
  response: Record<string, unknown>;
  [key: string]: unknown;
}

/**
 * A data part in the A2A stream.
 */
export interface A2ADataPart extends A2APart {
  kind: 'data';
  data: Record<string, unknown>;
}

/**
 * A data part representing a function response.
 */
export interface A2AFunctionResponsePart extends A2ADataPart {
  data: FunctionResponseData;
  metadata: { adk_type: 'function_response'; [key: string]: unknown };
}

/**
 * Type guard for function response parts.
 */
export function isFunctionResponsePart(part: A2APart): part is A2AFunctionResponsePart {
  return (
    part.kind === 'data' &&
    part.metadata?.adk_type === 'function_response' &&
    part.data !== undefined &&
    typeof part.data.name === 'string' &&
    typeof part.data.response === 'object'
  );
}
