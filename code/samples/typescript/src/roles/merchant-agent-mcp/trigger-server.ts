/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * HTTP server for simulating merchant-side events. Mirrors the Python
 * `merchant_agent_mcp/trigger_server.py` semantics.
 *
 * Example:
 *   curl -X POST "http://localhost:8081/trigger-price-drop?item_id=apple_0&price=5&stock=10"
 */

import express, { type Request, type Response } from 'express';
import fs from 'node:fs';
import path from 'node:path';

const TEMP_DB = process.env.TEMP_DB_DIR ?? '.temp-db';
const TRIGGER_STATE_PATH =
  process.env.MERCHANT_TRIGGER_STATE_PATH ??
  path.join(TEMP_DB, 'merchant_trigger_state.json');
const PORT = Number(process.env.MERCHANT_TRIGGER_PORT ?? 8081);

type TriggerEntry = { price?: number; stock?: number; _touch: number };
type TriggerState = Record<string, TriggerEntry>;

function loadState(): TriggerState {
  try {
    return JSON.parse(fs.readFileSync(TRIGGER_STATE_PATH, 'utf-8')) as TriggerState;
  } catch {
    return {};
  }
}

function mergeState(itemId: string, value: TriggerEntry): TriggerState {
  const state = loadState();
  state[itemId] = value;
  fs.mkdirSync(path.dirname(TRIGGER_STATE_PATH), { recursive: true });
  fs.writeFileSync(TRIGGER_STATE_PATH, JSON.stringify(state, null, 2));
  return state;
}

const app = express();

app.use((_req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  next();
});

app.options(/.*/, (_req, res) => {
  res.status(204).end();
});

app.post('/trigger-price-drop', (req: Request, res: Response) => {
  const itemId = String(req.query.item_id ?? '');
  if (!itemId) {
    return res.status(400).json({ error: 'item_id required' });
  }
  const price = Number(req.query.price ?? 5);
  const stockRaw = req.query.stock;
  const payload: TriggerEntry = { price, _touch: Date.now() / 1000 };
  if (stockRaw !== undefined) {
    payload.stock = Math.max(0, Number(stockRaw));
  }
  mergeState(itemId, payload);
  const stockMsg = payload.stock !== undefined ? `, stock ${payload.stock}` : '';
  res.json({
    ok: true,
    item_id: itemId,
    price,
    ...(payload.stock !== undefined ? { stock: payload.stock } : {}),
    message:
      `Price for ${itemId} set to $${price}${stockMsg}. ` +
      'Shopping agent sees it on next check_product (web UI may nudge immediately via /state poll).',
  });
});

app.get('/state', (req: Request, res: Response) => {
  const itemId = String(req.query.item_id ?? '');
  if (!itemId) return res.status(400).json({ error: 'item_id required' });
  const entry = loadState()[itemId] ?? null;
  res.json({ item_id: itemId, entry });
});

app.get(['/', '/health'], (_req: Request, res: Response) => {
  res.json({
    status: 'ok',
    endpoints: [
      `POST http://localhost:${PORT}/trigger-price-drop?item_id=<item_id>&price=<price>[&stock=<stock>]`,
      `GET http://localhost:${PORT}/state?item_id=<item_id>`,
    ],
  });
});

app.listen(PORT, '127.0.0.1', () => {
  console.log(`Merchant trigger server: http://localhost:${PORT}/`);
  console.log(`State file: ${TRIGGER_STATE_PATH}`);
});
