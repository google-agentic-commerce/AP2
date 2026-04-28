// Use same origin in dev so Vite proxy forwards /a2a to agent server (localhost:8080)
export const AGENT_URL =
  (import.meta as { env?: { VITE_AGENT_URL?: string } }).env?.VITE_AGENT_URL ??
  "/a2a/shopping_agent";

// Merchant trigger for simulating price drop (curl-able)
export const MERCHANT_TRIGGER_URL =
  (import.meta as { env?: { VITE_MERCHANT_TRIGGER_URL?: string } }).env
    ?.VITE_MERCHANT_TRIGGER_URL ?? "http://localhost:8081";

/** Sent when the user presses Enter with an empty input (demo starter). */
export const DEFAULT_CHAT_STARTER_MESSAGE =
    'When is the SuperShoe limited edition Gold sneaker drop? I need size 9 women\'s.';
