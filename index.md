# Agent Payments Protocol (AP2)

## What is AP2?

**Agent Payments Protocol (AP2) is an open protocol for the emerging Agent Economy.** It's designed to enable secure, reliable, and interoperable agent commerce for developers, merchants, and the payments industry. The protocol is available as an extension for the open-source [Agent2Agent (A2A) protocol](https://a2a-protocol.org/) and [Universal Commerce Protocol](https://ucp.dev/documentation/ucp-and-ap2/) with more integrations in progress.

Build agents with *(or any framework)*, equip with *(or any tool)*, collaborate via , and use **AP2** to secure payments with gen AI agents.

- **Video** Intro in \<7 min

  ______________________________________________________________________

- **Read the docs**

  ______________________________________________________________________

  [AP2 v0.2 Release and FIDO Alliance Donation](https://blog.google/products-and-platforms/platforms/google-pay/agent-payments-protocol-fido-alliance/)

  [FIDO Alliance to Develop Standards for Trusted AI Agent Interactions](https://fidoalliance.org/fido-alliance-to-develop-standards-for-trusted-ai-agent-interactions/)

  [Agent Payments Protocol Announcement (9/16/2025)](https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol)

  **Explore the detailed technical definition of the AP2 protocol**

  [Agent Payments Protocol Specification](ap2/specification/)

  [AP2 and UCP integration guide](https://ucp.dev/documentation/ucp-and-ap2/)

______________________________________________________________________

## Why an Agent Payments Protocol is Needed

Today’s payment systems assume a human is directly clicking "buy" on a trusted website. When an autonomous agent initiates a payment, this core assumption is broken, leading to critical questions that current systems cannot answer:

- **Authorization:** How can we verify that a user gave an agent specific authority for a particular purchase?
- **Authenticity:** How can a merchant be sure an agent's request accurately reflects the user's true intent, without errors or AI "hallucinations"?
- **Accountability:** If a fraudulent or incorrect transaction occurs, who is accountable—the user, the agent's developer, the merchant, the issuer, the PSP, or the orchestration layer?

This ambiguity creates a crisis of trust that could significantly limit adoption. Without a common protocol, we risk a fragmented ecosystem of proprietary payment solutions, which would be confusing for users, expensive for merchants, and difficult for financial institutions to manage. AP2 aims to create a common language for any compliant agent to transact securely with any compliant merchant globally.

______________________________________________________________________

## Core Principles and Goals

The Agent Payments Protocol is built on fundamental principles designed to create a secure and fair ecosystem:

- **Openness and Interoperability:** As a non-proprietary, open extension for A2A and MCP, AP2 fosters a competitive environment for innovation, broad merchant reach, and user choice.
- **User Control and Privacy:** The user must always be in control. The protocol is designed with privacy at its core, using a role-based architecture to protect sensitive payment details and personal information.
- **Verifiable Intent, Not Inferred Action:** Trust in payments is anchored to deterministic, non-repudiable proof of intent from the user, directly addressing the risk of agent error or hallucination.
- **Clear Transaction Accountability:** AP2 provides a non-repudiable, cryptographic audit trail for every transaction, aiding in dispute resolution and building confidence for all participants.
- **Global and Future-Proof:** Designed as a global foundation, the initial version supports common "pull" payment methods like credit and debit cards. The roadmap includes e-wallets, "push" payments such as real-time bank transfers (e.g., UPI and PIX), and digital currencies, recognizing that many countries do not have real-time banking systems.

______________________________________________________________________

## Key Concept: Verifiable Digital Credentials (VDCs)

The Agent Payments Protocol engineers trust into the system using **verifiable digital credentials (VDCs)**. VDCs are tamper-evident, cryptographically signed digital objects that serve as the building blocks of a transaction. There are two primary types of mandates, each existing in two stages:

- **Checkout Mandate**: Captures the reference to the specific items and purchase details negotiated between the agent and the merchant, and is **shared with the merchant**.
  - **Open**: Captures the user's constraints and goals for the transaction before a specific cart is finalized for autonomous execution.
  - **Closed**: Captures the user's (or agent's) authorization for a specific, finalized checkout.
- **Payment Mandate**: Authorizes a payment against a specific payment instrument, and is **shared with the Credential Provider, Networks and the Merchant Payment Processor**.
  - **Open**: Captures the user's constraints on payment (e.g., budget, allowed instruments) for autonomous execution.
  - **Closed**: Captures the authorization for a specific transaction amount bound to a finalized checkout.

These VDCs operate within a defined role-based architecture and are chained together to provide a complete, verifiable audit trail for both human-present and human-not-present transactions.

See more in the sample [Flows](ap2/flows/).

## See it in action

- **Human Not Present Cards**

  ______________________________________________________________________

  A sample demonstrating an autonomous transaction where the agent acts without human presence, using traditional card payments.

  [Go to sample](https://github.com/google-agentic-commerce/AP2/tree/main/code/samples/python/scenarios/a2a/human-not-present/cards/)

- **Human Not Present x402**

  ______________________________________________________________________

  A sample demonstrating an autonomous transaction where the agent acts without human presence, using the x402 protocol for payments.

  [Go to sample](https://github.com/google-agentic-commerce/AP2/tree/main/code/samples/python/scenarios/a2a/human-not-present/x402/)

- **Digital Payment Credentials Android**

  ______________________________________________________________________

  A sample demonstrating the use of digital payment credentials on an Android device.

  [Go to sample](https://github.com/google-agentic-commerce/AP2/tree/main/code/samples/android/scenarios/digital-payment-credentials/)

- **Human Present Cards**

  ______________________________________________________________________

  A sample demonstrating a human-present transaction using traditional card payments.

  [Go to sample](https://github.com/google-agentic-commerce/AP2/tree/main/code/samples/python/scenarios/a2a/human-present/cards/)

______________________________________________________________________

## Get Started and Build with Us

The Agent Payments Protocol provides a mechanism for secure payments, and it's part of a larger picture to unlock the full potential of agent-enabled commerce. We actively seek your feedback and contributions to help build the future of commerce.

Our public GitHub repo hosts the lastest version of AP2 specification, documentation and SDK. Standardization of the specification will continue within the Agentic Authentication Technical and Payments Technical Working Groups in FIDO.

You can get started today by:

- Downloading and running our **code samples**.
- **Experimenting with the protocol** and its different agent roles.
- Contributing your feedback and **code** to the public repository.

[Visit the GitHub Repository](https://github.com/google-agentic-commerce/AP2)
