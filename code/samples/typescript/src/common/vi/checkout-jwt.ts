/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Merchant-signed checkout JWT — a plain ES256 compact JWS committing the cart.
 * Port of python/examples/helpers.py `create_checkout_jwt` / `checkout_hash_from_jwt`.
 * The checkout hash binds the Payment Mandate to the checkout (transaction_id)
 * and the Layer 3 fulfillment to the merchant cart.
 */

import { hashBytes, jwtEncode, makeSigner, utf8 } from '@verifiable-intent/core';
import { findProduct } from './fixtures.js';
import type { ViKeyPair } from './keys.js';

export interface CartLineItem {
  sku: string;
  quantity?: number;
}

/** Build and sign a merchant checkout JWT from line items (ES256, merchant key). */
export async function createCheckoutJwt(items: CartLineItem[], merchant: ViKeyPair): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const cartItems: Record<string, unknown>[] = [];
  let totalCents = 0;

  for (const item of items) {
    const product = findProduct(item.sku);
    if (!product) {
      throw new Error(`Product ${item.sku} not found`);
    }
    const qty = item.quantity ?? 1;
    totalCents += product.price * qty;
    cartItems.push({
      sku: product.sku,
      name: product.name,
      size: product.size,
      size_label: product.sizeLabel,
      color: product.color,
      quantity: qty,
      unitPrice: product.price / 100, // display price in dollars
    });
  }

  const payload = {
    iss: 'https://tennis-warehouse.com',
    sub: 'cart_checkout',
    iat: now,
    exp: now + 3600,
    cart: {
      items: cartItems,
      subTotal: { amount: totalCents / 100, currencyCode: 'USD' },
    },
  };
  const header = { alg: 'ES256', typ: 'JWT', kid: merchant.kid };
  const signer = await makeSigner(merchant.privateKey);
  return jwtEncode(header, payload, signer);
}

/** SHA-256(base64url) of a checkout JWT string — the checkout hash / transaction id. */
export function checkoutHashFromJwt(checkoutJwt: string): string {
  return hashBytes(utf8(checkoutJwt));
}
