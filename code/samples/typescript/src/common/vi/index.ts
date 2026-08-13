/**
 * Copyright 2025 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Verifiable Intent integration barrel. Re-exports the `verifiable-intent-js`
 * primitives plus the AP2-sample glue (fixtures, key store, checkout JWT, and
 * the per-role flow facade) that replicate the Python reference integration.
 */

export * from 'verifiable-intent-js';
export * from './fixtures.js';
export * from './keys.js';
export * from './checkout-jwt.js';
export * from './flow.js';
