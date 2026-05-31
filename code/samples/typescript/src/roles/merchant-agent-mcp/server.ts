/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Merchant MCP Server — inventory, cart, checkout tools.
 *
 * Exposes five MCP tools consumed by the shopping agent v2 over stdio:
 *   search_inventory, check_product, assemble_cart, create_checkout, complete_checkout
 *
 * NOTE: This is the minimum viable port of the v0.2 Python `merchant_agent_mcp/server.py`.
 * Mandate verification (SD-JWT, ES256 chain checks) is STUBBED. Real implementations
 * would call into a ported AP2 SDK. The tool contracts (names, args, response shapes)
 * faithfully mirror the Python so the shopping-agent-v2 client code can be a 1:1 port.
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID, createHash } from 'node:crypto';
import { z } from 'zod';
import {
  signJwtEs256,
  verifyJwtEs256,
  loadOrCreateKeyPair,
  loadPublicJwk,
} from '../../common/sdjwt/index.js';

/** Base64url SHA-256 — the checkout JWT hash binds the payment mandate. */
function sha256Base64Url(input: string): string {
  return createHash('sha256').update(input).digest('base64url');
}

/** PSP trigger endpoint used to settle and obtain a PSP-signed receipt. */
const PSP_TRIGGER_PORT = process.env.MERCHANT_PAYMENT_PROCESSOR_TRIGGER_PORT ?? '8083';
const PSP_INITIATE_URL = `http://localhost:${PSP_TRIGGER_PORT}/initiate-payment`;

const TEMP_DB = process.env.TEMP_DB_DIR ?? '.temp-db';
const TRIGGER_STATE_PATH =
  process.env.MERCHANT_TRIGGER_STATE_PATH ??
  path.join(TEMP_DB, 'merchant_trigger_state.json');
const INVENTORY_PATH =
  process.env.MERCHANT_INVENTORY_PATH ??
  path.join(TEMP_DB, 'merchant_inventory.json');
const CARTS_PATH =
  process.env.MERCHANT_CARTS_PATH ?? path.join(TEMP_DB, 'merchant_carts.json');

type InventoryEntry = { name: string; price: number; stock: number };
type TriggerEntry = { price?: number; stock?: number; _touch: number };

function loadJson<T>(p: string, fallback: T): T {
  try {
    return JSON.parse(fs.readFileSync(p, 'utf-8')) as T;
  } catch {
    return fallback;
  }
}

function saveJson(p: string, data: unknown): void {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(data, null, 2));
}

function loadInventory(): Record<string, InventoryEntry> {
  return loadJson(INVENTORY_PATH, {});
}

function saveInventory(inv: Record<string, InventoryEntry>): void {
  saveJson(INVENTORY_PATH, inv);
}

function triggerOverrides(itemId: string): { price?: number; stock?: number } {
  const state = loadJson<Record<string, TriggerEntry>>(TRIGGER_STATE_PATH, {});
  const entry = state[itemId];
  return { price: entry?.price, stock: entry?.stock };
}

function effectivePrice(itemId: string, basePrice: number): number {
  const { price } = triggerOverrides(itemId);
  return price ?? basePrice;
}

function generateInventoryEntry(
  productDescription: string,
  priceCap: number | null,
): { item_id: string; name: string; price: number; stock: number } {
  const slug = productDescription
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
    .slice(0, 40);
  const itemId = `${slug}_0`;
  const inv = loadInventory();
  if (inv[itemId]) {
    return { item_id: itemId, ...inv[itemId] };
  }
  const price = priceCap !== null ? Math.min(priceCap, 199.99) : 199.99;
  const entry: InventoryEntry = {
    name: productDescription.replace(/\b\w/g, (c) => c.toUpperCase()),
    price,
    stock: 0,
  };
  inv[itemId] = entry;
  saveInventory(inv);
  return { item_id: itemId, ...entry };
}

function resolveItem(itemId: string, priceCap: number | null = null): InventoryEntry | null {
  const inv = loadInventory();
  if (inv[itemId]) return inv[itemId];
  // Auto-create matching the Python pattern <slug>_0
  if (/^[a-z0-9_]+_0$/.test(itemId)) {
    const description = itemId.slice(0, -2).replace(/_/g, ' ');
    const entry = generateInventoryEntry(description, priceCap);
    return { name: entry.name, price: entry.price, stock: entry.stock };
  }
  return null;
}

// Carts are persisted to TEMP_DB (not in-memory): the shopping agent v2 gives
// each sub-agent its own merchant MCP subprocess, so a cart assembled by one
// agent must be visible to another. File-backing keeps them consistent.
function loadCarts(): Record<string, unknown> {
  return loadJson(CARTS_PATH, {});
}
function saveCart(cartId: string, cart: unknown): void {
  const carts = loadCarts();
  carts[cartId] = cart;
  saveJson(CARTS_PATH, carts);
}
function getCart(cartId: string): unknown {
  return loadCarts()[cartId];
}

const server = new McpServer({
  name: 'merchant-mcp',
  version: '0.2.0',
});

server.registerTool(
  'search_inventory',
  {
    description:
      'Search merchant inventory for a product matching a free-text description, ' +
      'optionally constrained by a price cap. Returns matching catalog entries.',
    inputSchema: {
      product_description: z.string(),
      constraint_price_cap: z.number().nullable().optional(),
    },
  },
  async ({ product_description, constraint_price_cap }) => {
    if (!product_description.trim()) {
      const error = {
        error: 'invalid_description',
        message: 'product_description must be non-empty',
      };
      return {
        content: [{ type: 'text', text: JSON.stringify(error) }],
        structuredContent: error,
        isError: true,
      };
    }
    const entry = generateInventoryEntry(
      product_description,
      constraint_price_cap ?? null,
    );
    const result = {
      matches: [entry],
      message:
        `Found 1 matching product: ${entry.item_id}. ` +
        'Stock is 0 until a drop is simulated via the trigger server.',
    };
    return {
      content: [{ type: 'text', text: JSON.stringify(result) }],
      structuredContent: result,
    };
  },
);

server.registerTool(
  'check_product',
  {
    description:
      'Check the current price and availability of a specific catalog item by id, ' +
      'applying any active price/stock trigger overrides.',
    inputSchema: {
      item_id: z.string(),
      constraint_price_cap: z.number().nullable().optional(),
    },
  },
  async ({ item_id, constraint_price_cap }) => {
    const item = resolveItem(item_id, constraint_price_cap ?? null);
    if (!item) {
      const error = { error: 'item_not_found' };
      return {
        content: [{ type: 'text', text: JSON.stringify(error) }],
        structuredContent: error,
        isError: true,
      };
    }
    const price = effectivePrice(item_id, item.price);
    const { stock } = triggerOverrides(item_id);
    const available = stock !== undefined && stock > 0;
    const result = {
      item_id,
      price,
      available,
      timestamp: Math.floor(Date.now() / 1000),
      payment_method: process.env.FLOW ?? 'card',
      payment_method_description: 'Card (stub)',
    };
    return {
      content: [{ type: 'text', text: JSON.stringify(result) }],
      structuredContent: result,
    };
  },
);

server.registerTool(
  'assemble_cart',
  {
    description:
      'Assemble a cart for a given in-stock item and quantity, computing line ' +
      'items and totals in minor units, and persisting it for checkout.',
    inputSchema: { item_id: z.string(), qty: z.number().int().positive() },
  },
  async ({ item_id, qty }) => {
    const item = resolveItem(item_id);
    if (!item) {
      const error = { error: 'item_not_found' };
      return {
        content: [{ type: 'text', text: JSON.stringify(error) }],
        structuredContent: error,
        isError: true,
      };
    }
    const { stock } = triggerOverrides(item_id);
    if (!(stock !== undefined && stock > 0)) {
      const error = {
        error: 'out_of_stock',
        message: 'Item is not available to purchase yet (e.g. drop not live).',
      };
      return {
        content: [{ type: 'text', text: JSON.stringify(error) }],
        structuredContent: error,
        isError: true,
      };
    }
    const price = effectivePrice(item_id, item.price);
    const cartId = randomUUID();
    const priceMinor = Math.round(price * 100);
    const totalMinor = priceMinor * qty;
    const cart = {
      cart_id: cartId,
      total: totalMinor,
      line_items: [
        { item_id, qty, unit_price: priceMinor, item_name: item.name },
      ],
      currency: 'USD',
    };
    saveCart(cartId, cart);
    return {
      content: [{ type: 'text', text: JSON.stringify(cart) }],
      structuredContent: cart,
    };
  },
);

server.registerTool(
  'create_checkout',
  {
    description:
      'Create a checkout for a previously assembled cart, binding it to an ' +
      'open checkout mandate and returning a (stubbed) signed checkout JWT and its hash.',
    inputSchema: {
      cart_id: z.string(),
      open_checkout_mandate_id: z.string(),
    },
  },
  async ({ cart_id, open_checkout_mandate_id }) => {
    const cart = getCart(cart_id);
    if (!cart) {
      const error = { error: 'cart_not_found' };
      return {
        content: [{ type: 'text', text: JSON.stringify(error) }],
        structuredContent: error,
        isError: true,
      };
    }
    // Hash the referenced open checkout mandate so the checkout JWT commits to
    // it (downstream binding). The agent persisted it under TEMP_DB.
    let openCheckoutHash: string | null = null;
    try {
      const openMandate = fs.readFileSync(path.join(TEMP_DB, `${open_checkout_mandate_id}.sdjwt`), 'utf-8');
      openCheckoutHash = sha256Base64Url(openMandate);
    } catch {
      const error = { error: 'open_mandate_not_found', message: open_checkout_mandate_id };
      return { content: [{ type: 'text', text: JSON.stringify(error) }], structuredContent: error, isError: true };
    }
    // Sign a real ES256 checkout JWT with the merchant key. A random `jti`
    // gives the JWT entropy (the AP2 spec warns deterministic signatures over
    // low-entropy checkout content are rainbow-table-able). The JWT commits to
    // the open checkout mandate via open_checkout_hash.
    const merchant = await loadOrCreateKeyPair(TEMP_DB, 'merchant');
    const checkoutJwt = await signJwtEs256(
      {
        iss: 'merchant-agent',
        iat: Math.floor(Date.now() / 1000),
        jti: randomUUID(),
        open_checkout_mandate_id,
        open_checkout_hash: openCheckoutHash,
        cart,
      },
      merchant.privateKey,
    );
    const checkoutJwtHash = sha256Base64Url(checkoutJwt);
    const result = {
      checkout_jwt: checkoutJwt,
      checkout_jwt_hash: checkoutJwtHash,
      open_checkout_hash: openCheckoutHash,
      open_checkout_mandate_id,
      cart,
    };
    return {
      content: [{ type: 'text', text: JSON.stringify(result) }],
      structuredContent: result,
    };
  },
);

server.registerTool(
  'complete_checkout',
  {
    description:
      'Complete a checkout using a checkout JWT and optional payment credential, ' +
      'returning a (stubbed) signed checkout receipt.',
    inputSchema: {
      checkout_jwt: z.string(),
      payment_credential: z.unknown().optional(),
    },
  },
  async ({ checkout_jwt, payment_credential }) => {
    // Verify the merchant's own checkout JWT signature before finalizing.
    const merchantPub = loadPublicJwk(TEMP_DB, 'merchant');
    if (!merchantPub) {
      const error = { error: 'merchant_key_unavailable', message: 'merchant key not found in TEMP_DB' };
      return { content: [{ type: 'text', text: JSON.stringify(error) }], structuredContent: error, isError: true };
    }
    let checkoutJwtHash: string;
    try {
      await verifyJwtEs256(checkout_jwt, merchantPub);
      checkoutJwtHash = sha256Base64Url(checkout_jwt);
    } catch (e) {
      const error = { error: 'invalid_checkout_jwt', message: String(e) };
      return { content: [{ type: 'text', text: JSON.stringify(error) }], structuredContent: error, isError: true };
    }

    // Settle with the PSP (server-to-server) and obtain a PSP-signed payment
    // receipt — mirrors Python merchant_agent_mcp._initiate_payment_with_payment_processor.
    let paymentReceipt: string | null = null;
    try {
      const res = await fetch(PSP_INITIATE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          payment_token: (payment_credential as { payment_token?: string })?.payment_token ?? 'tok_unknown',
          checkout_jwt_hash: checkoutJwtHash,
          open_checkout_hash: checkoutJwtHash,
        }),
      });
      const body = (await res.json()) as { payment_receipt?: string };
      paymentReceipt = body.payment_receipt ?? null;
    } catch (e) {
      const error = { error: 'psp_settlement_failed', message: String(e) };
      return { content: [{ type: 'text', text: JSON.stringify(error) }], structuredContent: error, isError: true };
    }

    // Sign the merchant's checkout receipt (ES256) over the verified checkout.
    const merchant = await loadOrCreateKeyPair(TEMP_DB, 'merchant');
    const checkoutReceipt = await signJwtEs256(
      {
        iss: 'merchant-agent',
        receipt_id: randomUUID(),
        iat: Math.floor(Date.now() / 1000),
        checkout_jwt_hash: checkoutJwtHash,
      },
      merchant.privateKey,
    );
    const result = {
      status: 'completed',
      checkout_receipt: checkoutReceipt, // merchant-signed ES256 JWT
      payment_receipt: paymentReceipt, // PSP-signed ES256 JWT
    };
    return {
      content: [{ type: 'text', text: JSON.stringify(result) }],
      structuredContent: result,
    };
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
