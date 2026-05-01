---
hide:
    - toc
---

<!-- markdownlint-disable MD041 -->
<div style="text-align: center;">
  <div class="centered-logo-text-group">
    <img src="assets/ap2-logo-black.svg" alt="Agent Payments Protocol Logo" width="100">
    <h1>Agent Payments Protocol (AP2)</h1>
  </div>
</div>

## What is AP2?

**Agent Payments Protocol (AP2) is an open protocol for the emerging Agent
Economy.** It's designed to enable secure, reliable, and interoperable agent
commerce for developers, merchants, and the payments industry. The protocol is
available as an extension for the open-source
[Agent2Agent (A2A) protocol](https://a2a-protocol.org/) and
[Universal Commerce Protocol](https://ucp.dev/documentation/ucp-and-ap2/) with more integrations
in progress.


<!-- prettier-ignore-start -->
!!! abstract ""

    Build agents with
    **[![ADK Logo](https://google.github.io/adk-docs/assets/agent-development-kit.png){class="twemoji lg middle"} ADK](https://google.github.io/adk-docs/)**
    _(or any framework)_, equip with
    **[![MCP Logo](https://modelcontextprotocol.io/mcp.png){class="twemoji lg middle"} MCP](https://modelcontextprotocol.io)**
    _(or any tool)_, collaborate via
    **[![A2A Logo](https://a2a-protocol.org/latest/assets/a2a-logo-black.svg){class="twemoji sm middle"} A2A](https://a2a-protocol.org)**, and use
    **![AP2 Logo](./assets/ap2-logo-black.svg){class="twemoji sm middle"} AP2** to secure payments with gen AI agents.
<!-- prettier-ignore-end -->

<div class="grid cards" markdown>

- :material-play-circle:{ .lg .middle } **Video** Intro in <7 min

    ---

      <iframe width="560" height="315" src="https://www.youtube.com/embed/jSHj0z9Gi24?si=jDx8luqpw35nbDKy" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

- :material-file-document-outline:{ .lg .middle } **Read the docs**

    ---

    [:octicons-arrow-right-24: AP2 v0.2 Release and FIDO Alliance Donation](https://blog.google/products-and-platforms/platforms/google-pay/agent-payments-protocol-fido-alliance/)

    [:octicons-arrow-right-24: FIDO Alliance to Develop Standards for Trusted AI Agent Interactions](https://fidoalliance.org/fido-alliance-to-develop-standards-for-trusted-ai-agent-interactions/)

    [:octicons-arrow-right-24: Agent Payments Protocol Announcement (9/16/2025)](https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol)

    &nbsp;

    **Explore the detailed technical definition of the AP2 protocol**

    [:octicons-arrow-right-24: Agent Payments Protocol Specification](ap2/specification.md)

    [:octicons-arrow-right-24: AP2 and UCP integration guide](https://ucp.dev/documentation/ucp-and-ap2/)

</div>

---

## Why an Agent Payments Protocol is Needed

Today’s payment systems assume a human is directly clicking "buy" on a trusted
website. When an autonomous agent initiates a payment, this core assumption is
broken, leading to critical questions that current systems cannot answer:

- **Authorization:** How can we verify that a user gave an agent specific
    authority for a particular purchase?
- **Authenticity:** How can a merchant be sure an agent's request accurately
    reflects the user's true intent, without errors or AI "hallucinations"?
- **Accountability:** If a fraudulent or incorrect transaction occurs, who is
    accountable—the user, the agent's developer, the merchant, the issuer, the
    PSP, or the orchestration layer?

This ambiguity creates a crisis of trust that could significantly limit
adoption. Without a common protocol, we risk a fragmented ecosystem of
proprietary payment solutions, which would be confusing for users, expensive for
merchants, and difficult for financial institutions to manage. AP2 aims to
create a common language for any compliant agent to transact securely with any
compliant merchant globally.

---

## Core Principles and Goals

The Agent Payments Protocol is built on fundamental principles designed to
create a secure and fair ecosystem:

- **Openness and Interoperability:** As a non-proprietary, open extension for
    A2A and MCP, AP2 fosters a competitive environment for innovation, broad
    merchant reach, and user choice.
- **User Control and Privacy:** The user must always be in control. The
    protocol is designed with privacy at its core, using a role-based
    architecture to protect sensitive payment details and personal information.
- **Verifiable Intent, Not Inferred Action:** Trust in payments is anchored to
    deterministic, non-repudiable proof of intent from the user, directly
    addressing the risk of agent error or hallucination.
- **Clear Transaction Accountability:** AP2 provides a non-repudiable,
    cryptographic audit trail for every transaction, aiding in dispute
    resolution and building confidence for all participants.
- **Global and Future-Proof:** Designed as a global foundation, the initial
    version supports common "pull" payment methods like credit and debit cards.
    The roadmap includes e-wallets, "push" payments such as real-time bank
    transfers (e.g., UPI and PIX), and digital currencies, recognizing that
    many countries do not have real-time banking systems.

---

## Key Concept: Verifiable Digital Credentials (VDCs)

The Agent Payments Protocol engineers trust into the system using **verifiable
digital credentials (VDCs)**. VDCs are tamper-evident, cryptographically signed
digital objects that serve as the building blocks of a transaction. There are
two primary types of mandates, each existing in two stages:

- **Checkout Mandate**: Captures the reference to the specific items and
  purchase details negotiated between the agent and the merchant, and is
  **shared with the merchant**.
    - **Open**: Captures the user's constraints and goals for the transaction
      before a specific cart is finalized for autonomous execution.
    - **Closed**: Captures the user's (or agent's) authorization for a specific,
      finalized checkout.
- **Payment Mandate**: Authorizes a payment against a specific payment
  instrument, and is **shared with the Credential Provider, Networks and the
  Merchant Payment Processor**.
    - **Open**: Captures the user's constraints on payment (e.g., budget,
      allowed instruments) for autonomous execution.
    - **Closed**: Captures the authorization for a specific transaction amount
      bound to a finalized checkout.

These VDCs operate within a defined role-based architecture and are chained
together to provide a complete, verifiable audit trail for both human-present
and human-not-present transactions.

See more in the sample [Flows](ap2/flows.md).

## See it in action

<div class="grid cards" markdown>

- **Human Not Present Cards**

    ---

    A sample demonstrating an autonomous transaction where the agent acts without human presence, using traditional card payments.

    [:octicons-arrow-right-24: Go to sample](https://github.com/google-agentic-commerce/AP2/tree/main/code/samples/python/scenarios/a2a/human-not-present/cards/)

- **Human Not Present x402**

    ---

    A sample demonstrating an autonomous transaction where the agent acts without human presence, using the x402 protocol for payments.

    [:octicons-arrow-right-24: Go to sample](https://github.com/google-agentic-commerce/AP2/tree/main/code/samples/python/scenarios/a2a/human-not-present/x402/)

- **Digital Payment Credentials Android**

    ---

    A sample demonstrating the use of digital payment credentials on an Android device.

    [:octicons-arrow-right-24: Go to sample](https://github.com/google-agentic-commerce/AP2/tree/main/code/samples/android/scenarios/digital-payment-credentials/)

- **Human Present Cards**

    ---

    A sample demonstrating a human-present transaction using traditional card payments.

    [:octicons-arrow-right-24: Go to sample](https://github.com/google-agentic-commerce/AP2/tree/main/code/samples/python/scenarios/a2a/human-present/cards/)

</div>

---

## Get Started and Build with Us

The Agent Payments Protocol provides a mechanism for secure payments, and it's
part of a larger picture to unlock the full potential of agent-enabled commerce.
We actively seek your feedback and contributions to help build the future of
commerce.

Our public GitHub repo hosts the lastest version of AP2 specification, documentation and SDK. Standardization of the specification will continue within the Agentic Authentication Technical and Payments Technical Working Groups in FIDO.

You can get started today by:

- Downloading and running our **code samples**.
- **Experimenting with the protocol** and its different agent roles.
- Contributing your feedback and **code** to the public repository.
- Joining our [**Discord community**](https://discord.gg/CtHD3GF8sF) to connect with other developers and the AP2 team.

[Visit the GitHub Repository](https://github.com/google-agentic-commerce/AP2)
