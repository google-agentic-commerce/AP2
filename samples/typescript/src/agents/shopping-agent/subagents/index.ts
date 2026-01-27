export const SUBAGENTS = {
  SHOPPER: "http://localhost:8005/.well-known/agent-card.json",
  SHIPPING_ADDRESS_COLLECTOR:
    "http://localhost:8007/.well-known/agent-card.json",
  PAYMENT_METHOD_COLLECTOR: "http://localhost:8006/.well-known/agent-card.json",
} as const;
