# Agent Payments Protocol Sample: Human Present Purchases with x402

This sample demonstrates the A2A ap2-extension for a human present transaction
using payment methods compatible with the x402 as the payment method.

**Note:** The AP2 compatible x402 extension is coming soon. The current x402
extension will be enhanced to ensure the creation of all key mandates outlined
in AP2. See the current A2A x402 extension
[here](https://github.com/google-agentic-commerce/a2a-x402/).

## Scenario

Human-Present flows refer to all commerce flows where the user is present to
confirm the details of what is being purchased, and what payment method is to be
used. The user attesting to the details of the purchase allows all parties to
have high confidence of the transaction.

The IntentMandate is still leveraged to share the appropriate information with
Merchant Agents. This is to maintain consistency across Human-Present and
Human-Not-Present flows.

All Human-Present purchases will have a user-signed PaymentMandate authorizing
the purchase.

## Key Actors

This sample consists of:

*   **Shopping Agent:** The main orchestrator that handles user's requests to
    shop and delegates tasks to specialized agents.
*   **Merchant Agent:** An agent that handles product queries from the shopping
    agent.
*   **Merchant Payment Processor Agent:** An agent that takes payments on behalf
    of the merchant.
*   **Credentials Provider Agent:** The credentials provider is the holder of a
    user's payment credentials. As such, it serves two primary roles:
    *   It provides the shopping agent the list of payment methods available in
        a user's wallet.
    *   It facilitates payment between the shopping agent and a merchant's
        payment processor.

## Key Features

**1. x402 purchase**

*   The Merchant Agent will advertise support for x402 purchases through its
    agent card and through the CartMandate once shopping is complete.
*   The preferred payment method in the user's wallet will be an x402 compatible
    payment method.