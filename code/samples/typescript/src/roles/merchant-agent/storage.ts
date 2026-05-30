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

/**
 * In-memory storage for CartMandates and risk data.
 *
 * A CartMandate may be updated multiple times during the course of a shopping
 * journey. This storage system is used to persist CartMandates between
 * interactions between the shopper and merchant agents.
 */

import type { CartMandate } from "../../common/types/cart-mandate.js";

// Separate stores for type safety — avoids union-type ambiguity
const cartMandateStore = new Map<string, CartMandate>();
const riskDataStore = new Map<string, string>();

/**
 * Get a cart mandate by cart ID.
 */
export function getCartMandate(cartId: string): CartMandate | undefined {
  return cartMandateStore.get(cartId);
}

/**
 * Set a cart mandate by cart ID.
 */
export function setCartMandate(cartId: string, cartMandate: CartMandate): void {
  cartMandateStore.set(cartId, cartMandate);
}

/**
 * Set risk data by context ID.
 */
export function setRiskData(contextId: string, riskData: string): void {
  riskDataStore.set(contextId, riskData);
}

/**
 * Get risk data by context ID.
 */
export function getRiskData(contextId: string): string | undefined {
  return riskDataStore.get(contextId);
}
