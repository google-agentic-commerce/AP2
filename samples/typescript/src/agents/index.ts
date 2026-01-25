export const AGENTS = {
  SHOPPING_AGENT: "http://localhost:8001/.well-known/agent-card.json",
  MERCHANT_AGENT: "http://localhost:8004/.well-known/agent-card.json",
  MERCHANT_PAYMENT_PROCESSOR:
    "http://localhost:8003/.well-known/agent-card.json",
  CREDENTIALS_PROVIDER: "http://localhost:8002/.well-known/agent-card.json",
} as const;
