/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * HTTP server for initiating payment processing. Runs on port 8083.
 * Mirrors the Python `merchant_payment_processor_mcp/trigger_server.py`.
 */

import express, { type Request, type Response } from 'express';
import { randomUUID } from 'node:crypto';

const PORT = Number(process.env.MERCHANT_PAYMENT_PROCESSOR_TRIGGER_PORT ?? 8083);

const app = express();
app.use(express.json({ limit: '1mb' }));

app.post('/initiate-payment', (req: Request, res: Response) => {
  const { payment_token, checkout_jwt_hash, open_checkout_hash } = req.body ?? {};
  for (const [field, value] of [
    ['payment_token', payment_token],
    ['checkout_jwt_hash', checkout_jwt_hash],
    ['open_checkout_hash', open_checkout_hash],
  ] as const) {
    if (!value) return res.status(400).json({ error: `${field} required` });
  }
  // STUB: real impl calls into MCP server's initiate_payment for token verification + settlement.
  res.json({
    status: 'settled',
    payment_receipt: `psp_receipt.${randomUUID()}.stub_sig`,
    timestamp: Math.floor(Date.now() / 1000),
  });
});

app.listen(PORT, '127.0.0.1', () => {
  console.log(
    `Merchant payment processor trigger server: http://localhost:${PORT}/initiate-payment`,
  );
});
