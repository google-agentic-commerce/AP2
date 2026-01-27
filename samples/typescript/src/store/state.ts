import { AsyncLocalStorage } from "node:async_hooks";
import type { CartMandate } from "../types/cart-mandate.js";
import type { IntentMandate } from "../types/intent-mandate.js";
import type { PaymentMandate } from "../types/payment-mandate.js";

export type ShippingAddress = {
  recipient?: string;
  organization?: string;
  address_line?: string[];
  city?: string;
  region?: string;
  postal_code?: string;
  country?: string;
  phone_number?: string;
};

export type PaymentReceipt = {
  receiptId: string;
  transactionId: string;
  status: "success" | "failed";
  timestamp: string;
  amount?: { value: number; currency: string };
};

export type State = {
  shoppingContextId?: string;
  intentMandate?: IntentMandate;
  shippingAddress?: ShippingAddress;
  cartMandate?: CartMandate;
  cartMandates?: CartMandate[];
  chosenCartId?: string;
  initiatePaymentTaskId?: string;
  paymentCredentialToken?: string;
  paymentMandate?: PaymentMandate;
  signedPaymentMandate?: PaymentMandate;
  riskData?: string;
  userEmail?: string;
  subagentTaskIds?: Record<string, string>;
  paymentReceipt?: PaymentReceipt;
};

const asyncLocalStorage = new AsyncLocalStorage<string>();
const sessionStates = new Map<string, State>();

export function runWithContext<T>(contextId: string, callback: () => T): T {
  return asyncLocalStorage.run(contextId, callback);
}

export function setCurrentContext(contextId: string): void {
  if (!contextId) {
    throw new Error("contextId is required");
  }
  const current = asyncLocalStorage.getStore();
  if (!current) {
    asyncLocalStorage.enterWith(contextId);
  }
}

export function getCurrentContext(): string {
  const contextId = asyncLocalStorage.getStore();
  if (!contextId) {
    throw new Error(
      "No context set. Use runWithContext() or setCurrentContext() first"
    );
  }
  return contextId;
}

export function getState(): Readonly<State> {
  const contextId = getCurrentContext();
  if (!sessionStates.has(contextId)) {
    sessionStates.set(contextId, { subagentTaskIds: {} });
  }
  const state = sessionStates.get(contextId);
  return { ...state } as Readonly<State>;
}

export function setState(updates: Partial<State>): void {
  const contextId = getCurrentContext();
  if (!sessionStates.has(contextId)) {
    sessionStates.set(contextId, { subagentTaskIds: {} });
  }
  const current = sessionStates.get(contextId);
  if (current) {
    Object.assign(current, updates);
  }
}

export function clearState(): void {
  const contextId = getCurrentContext();
  sessionStates.delete(contextId);
}
