# AP2 and x402

The Agent Payments Protocol (AP2) and [x402](https://www.x402.org/) are
complementary. **AP2 is designed to support emerging payment methods like
x402**, providing a secure and interoperable framework for AI agents to conduct
transactions that may involve such digital currencies.

<!-- prettier-ignore-start -->
!!! tip "Dedicated Repo"

    Check out
    [google-agentic-commerce/a2a-x402](https://github.com/google-agentic-commerce/a2a-x402/)
    which is an implementation of A2A in conjunction with the x402 standard. We
    will be aligning this closely with AP2 over time to make it easy to compose
    solutions which include all payment methods, including digital currencies.
<!-- prettier-ignore-end -->

## Payment Agnosticism and Future-Proof Design

AP2 is an open, interoperable protocol specifically engineered to enable AI
agents to securely interact and complete payments autonomously. A core principle
of AP2 is its payment-method-agnostic and future-proof design. The initial
version supports common "pull" payment methods like credit/debit cards, with a
roadmap to include "push" payments like real-time bank transfers and digital
currencies. This flexible approach ensures that AP2 can evolve to support
various ways people pay.

## Engineering Trust for Agentic Transactions

AP2 introduces key concepts like **Verifiable Credentials (VCs)**—including
Intent Mandates, Cart Mandates, and Payment Mandates—which are cryptographically
signed digital objects that capture user authorization and intent. These VCs
provide a non-repudiable audit trail for every transaction, establishing a clear
framework for accountability and addressing the "crisis of trust" inherent in
autonomous AI agent payments. This secure foundation is crucial for any payment
method where validating agent authority and user intent is paramount.

## Industry Collaboration and Implementation

AP2 is being developed in collaboration with prominent partners in the payments
and web3 ecosystems, including Coinbase, CrossMint, EigenLayer, Ethereum
Foundation, Mesh, Metamask, and Mysten. Shared samples are currently being built
to demonstrate AP2 and x402 working together in practical implementations.

---

In essence, **AP2 provides the overarching secure, interoperable protocol and
trust mechanisms necessary for AI agents to make payments**, while x402
represents a type of emerging payment method that AP2 is specifically designed
to accommodate and support securely within the agentic payments ecosystem.
