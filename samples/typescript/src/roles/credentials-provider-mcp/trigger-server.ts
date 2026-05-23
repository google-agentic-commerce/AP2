/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * HTTP server for receiving payment receipts. Runs on port 8082.
 * Mirrors the Python `credentials_provider_mcp/trigger_server.py`.
 */

import express, { type Request, type Response } from 'express';

const PORT = Number(process.env.CREDENTIALS_PROVIDER_TRIGGER_PORT ?? 8082);

const app = express();
app.use(express.json({ limit: '1mb' }));

app.post('/payment-receipt', (req: Request, res: Response) => {
  const paymentReceipt = req.body?.payment_receipt;
  if (!paymentReceipt) {
    return res.status(400).json({ error: 'payment_receipt required' });
  }
  // STUB: real impl calls into the MCP server's verify_payment_receipt.
  // Here we just log the receipt prefix.
  const prefix =
    typeof paymentReceipt === 'string' ? paymentReceipt.slice(0, 20) : 'opaque';
  console.log(`[trigger] Received payment receipt: ${prefix}...`);
  res.json({ status: 'ok' });
});

app.listen(PORT, '127.0.0.1', () => {
  console.log(
    `Credentials provider trigger server: http://localhost:${PORT}/payment-receipt`,
  );
});
