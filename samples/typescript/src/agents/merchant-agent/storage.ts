/**
 * In-memory storage for CartMandates and risk data.
 *
 * A CartMandate may be updated multiple times during the course of a shopping
 * journey. This storage system is used to persist CartMandates between
 * interactions between the shopper and merchant agents.
 */

import type { CartMandate } from "../../types/cart-mandate.js";

// In-memory store
const store = new Map<string, CartMandate | string>();

/**
 * Get a cart mandate by cart ID.
 */
export function getCartMandate(cartId: string): CartMandate | undefined {
  const value = store.get(cartId);
  return value && typeof value !== "string" ? value : undefined;
}

/**
 * Set a cart mandate by cart ID.
 */
export function setCartMandate(cartId: string, cartMandate: CartMandate): void {
  store.set(cartId, cartMandate);
}

/**
 * Set risk data by context ID.
 */
export function setRiskData(contextId: string, riskData: string): void {
  store.set(contextId, riskData);
}

/**
 * Get risk data by context ID.
 */
export function getRiskData(contextId: string): string | undefined {
  const value = store.get(contextId);
  return typeof value === "string" ? value : undefined;
}
