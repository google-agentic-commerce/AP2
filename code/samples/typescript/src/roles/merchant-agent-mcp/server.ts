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
import { randomUUID } from 'node:crypto';
import { z } from 'zod';

const TEMP_DB = process.env.TEMP_DB_DIR ?? '.temp-db';
const TRIGGER_STATE_PATH =
  process.env.MERCHANT_TRIGGER_STATE_PATH ??
  path.join(TEMP_DB, 'merchant_trigger_state.json');
const INVENTORY_PATH =
  process.env.MERCHANT_INVENTORY_PATH ??
  path.join(TEMP_DB, 'merchant_inventory.json');

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

const CART_STORE = new Map<string, unknown>();

const server = new McpServer({
  name: 'merchant-mcp',
  version: '0.2.0',
});

server.tool(
  'search_inventory',
  {
    product_description: z.string(),
    constraint_price_cap: z.number().nullable().optional(),
  },
  async ({ product_description, constraint_price_cap }) => {
    if (!product_description.trim()) {
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              error: 'invalid_description',
              message: 'product_description must be non-empty',
            }),
          },
        ],
      };
    }
    const entry = generateInventoryEntry(
      product_description,
      constraint_price_cap ?? null,
    );
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            matches: [entry],
            message:
              `Found 1 matching product: ${entry.item_id}. ` +
              'Stock is 0 until a drop is simulated via the trigger server.',
          }),
        },
      ],
    };
  },
);

server.tool(
  'check_product',
  {
    item_id: z.string(),
    constraint_price_cap: z.number().nullable().optional(),
  },
  async ({ item_id, constraint_price_cap }) => {
    const item = resolveItem(item_id, constraint_price_cap ?? null);
    if (!item) {
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: 'item_not_found' }) }],
      };
    }
    const price = effectivePrice(item_id, item.price);
    const { stock } = triggerOverrides(item_id);
    const available = stock !== undefined && stock > 0;
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            item_id,
            price,
            available,
            timestamp: Math.floor(Date.now() / 1000),
            payment_method: process.env.FLOW ?? 'card',
            payment_method_description: 'Card (stub)',
          }),
        },
      ],
    };
  },
);

server.tool(
  'assemble_cart',
  { item_id: z.string(), qty: z.number().int().positive() },
  async ({ item_id, qty }) => {
    const item = resolveItem(item_id);
    if (!item) {
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: 'item_not_found' }) }],
      };
    }
    const { stock } = triggerOverrides(item_id);
    if (!(stock !== undefined && stock > 0)) {
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              error: 'out_of_stock',
              message: 'Item is not available to purchase yet (e.g. drop not live).',
            }),
          },
        ],
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
    CART_STORE.set(cartId, cart);
    return { content: [{ type: 'text', text: JSON.stringify(cart) }] };
  },
);

server.tool(
  'create_checkout',
  {
    cart_id: z.string(),
    open_checkout_mandate_id: z.string(),
  },
  async ({ cart_id, open_checkout_mandate_id }) => {
    const cart = CART_STORE.get(cart_id);
    if (!cart) {
      return {
        content: [{ type: 'text', text: JSON.stringify({ error: 'cart_not_found' }) }],
      };
    }
    // STUB: real impl creates ES256-signed JWT. Here we just return a placeholder.
    const checkoutJwt = `stub.${Buffer.from(JSON.stringify(cart)).toString('base64url')}.sig`;
    const checkoutJwtHash = Buffer.from(checkoutJwt).toString('base64url').slice(0, 43);
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            checkout_jwt: checkoutJwt,
            checkout_jwt_hash: checkoutJwtHash,
            open_checkout_mandate_id,
            cart,
          }),
        },
      ],
    };
  },
);

server.tool(
  'complete_checkout',
  {
    checkout_jwt: z.string(),
    payment_credential: z.unknown().optional(),
  },
  async ({ checkout_jwt }) => {
    // STUB: real impl calls PSP initiate_payment, validates, returns signed receipt.
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            status: 'completed',
            checkout_receipt: {
              receipt_id: randomUUID(),
              timestamp: Math.floor(Date.now() / 1000),
              checkout_jwt_hash: checkout_jwt.slice(0, 43),
              signature: 'stub-signature',
            },
          }),
        },
      ],
    };
  },
);

const transport = new StdioServerTransport();
await server.connect(transport);
