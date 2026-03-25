# Exploring Stablecoin Payments in AP2
This document is an exploratory contribution examining how the Agent Payments
Protocol (AP2) could apply to stablecoin-based payments. It does not represent
an official AP2 specification.
## Push vs Pull Payment Semantics
AP2 v0.1 focuses on "pull" payment methods (e.g., credit/debit cards), where
the merchant initiates a charge against the user's credentials. Stablecoin
payments operate on "push" semantics — the payer initiates a transfer directly
to the payee's address.
Despite this difference, AP2's core mandate architecture could be applicable
to push payments as well. The following table outlines a conceptual mapping
of how each AP2 component might function in a stablecoin context:
| AP2 Component | Pull Payments (Cards) | Push Payments (Stablecoins) |
|---------------|----------------------|---------------------------|
| Cart Mandate | Merchant signs cart, user confirms | Same — cart signing is payment-agnostic |
| Payment Mandate | Shared with card network/issuer | Could be shared with settlement network for trust |
| Credentials Provider | Returns card token | Could execute transfer and return proof of payment |
| MPP | Initiates charge | A verification layer could confirm on-chain receipt |
## Potential Use Cases
### Social Entertainment Payments
Social platforms process high volumes of micro-transactions across borders.
Possible AP2 applications include:
- **Creator Tipping (Human Present):** A user tips a live streamer in USDT.
  The Shopping Agent facilitates the flow, the Merchant Agent builds a cart
  for the tip amount, and the user confirms via a Cart Mandate. Settlement
  could occur on-chain.
- **Digital Gifting (Human Present):** A user purchases virtual gifts to send
  to a friend. The cart contains multiple virtual items with a total settled
  in stablecoins.
- **Subscriptions (Human Not Present — Future):** A user subscribes to premium
  content with monthly stablecoin payments. This would align with future AP2
  capabilities such as Intent Mandates planned for v1.x.
### Cross-Border B2B Settlement
Stablecoins are increasingly used for cross-border merchant settlement,
particularly in emerging markets where traditional banking rails are slow or
expensive. AP2 mandates could provide the accountability and audit trail
needed for these transactions.
## Possible PaymentMethodData Extension
One possible approach to supporting stablecoins is to define a payment method
identifier following the W3C Payment Method convention. For example:
```json
{
  "supported_methods": "https://example.com/stablecoin/v1",
  "data": {
    "supported_tokens": ["USDT", "USDC"],
    "supported_chains": ["ethereum", "tron", "polygon"],
    "preferred_chain": "tron",
    "settlement_currency": "USD"
  }
}
