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

/** Agent card URLs for server agents in the AP2 system. */
export const AGENT_URLS = {
  CREDENTIALS_PROVIDER: 'http://localhost:8002/.well-known/agent-card.json',
  PAYMENT_PROCESSOR: 'http://localhost:8003/.well-known/agent-card.json',
  MERCHANT: 'http://localhost:8004/.well-known/agent-card.json',
} as const;
