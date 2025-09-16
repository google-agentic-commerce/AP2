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
[Agent2Agent (A2A) protocol](https://a2a-protocol.org/), with more integrations
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

      <iframe width="560" height="315" src="https://www.youtube.com/embed/yLTp3ic2j5c?si=kfASyAVW8QpzUTho" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

- :material-file-document-outline:{ .lg .middle } **Read the docs**

    ---

    [:octicons-arrow-right-24: Google Cloud announcement of AP2](https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol)

    Explore the detailed technical definition of the AP2 protocol

    [:octicons-arrow-right-24: Agent Payments Protocol Specification](./specification.md)

    Review key topics

    [:octicons-arrow-right-24: Overview](topics/what-is-ap2.md)<br>
    [:octicons-arrow-right-24: Core Concepts](topics/core-concepts.md)<br>
    [:octicons-arrow-right-24: AP2, A2A and MCP](topics/ap2-a2a-and-mcp.md)<br>
    [:octicons-arrow-right-24: AP2 and x402](topics/ap2-and-x402.md)<br>
    [:octicons-arrow-right-24: Privacy and Security](topics/privacy-and-security.md)<br>

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
    accountable—the user, the agent's developer, the merchant, or the issuer?

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
    The roadmap includes "push" payments such as real-time bank transfers (e.g.,
    UPI and PIX) and digital currencies.

---

## Key Concept: Verifiable Credentials (VCs)

The Agent Payments Protocol engineers trust into the system using **Verifiable
Credentials (VCs)**. VCs are tamper-evident, cryptographically signed digital
objects that serve as the building blocks of a transaction. They are the data
payloads that agents create and exchange. There are three primary types:

- **The Intent Mandate:** This VC captures the conditions under which an AI
    Agent can make a purchase on behalf of the user, particularly in
    "human-not-present" scenarios. It provides the agent with authority to
    execute a transaction within defined constraints.
- **The Cart Mandate:** This VC captures the user's final, explicit
    authorization for a specific cart, including the exact items and price, in
    "human-present" scenarios. The user's cryptographic signature on this
    mandate provides non-repudiable proof of their intent.
- **The Payment Mandate:** A separate VC shared with the payment network and
    issuer, designed to signal AI agent involvement and user presence
    (human-present or not) to help assess transaction context.

These VCs operate within a defined role-based architecture and can handle both
"human-present" and "human-not-present" transaction types.

Learn more in [Core Concepts](topics/core-concepts.md).

## See it in action

<div class="grid cards" markdown>

- **Human Present Cards**

    ---

    A sample demonstrating a human-present transaction using traditional card
    payments.

    [:octicons-arrow-right-24: Go to sample](https://github.com/google-agentic-commerce/AP2/tree/main/samples/python/scenarios/a2a/human-present/cards/)

- **Human Present x402**

    ---

    A sample demonstrating a human-present transaction using the x402 protocol
    for payments.

    [:octicons-arrow-right-24: Go to sample](https://github.com/google-agentic-commerce/AP2/tree/main/samples/python/scenarios/a2a/human-present/x402/)

- **Digital Payment Credentials Android**

    ---

    A sample demonstrating the use of digital payment credentials on an Android
    device.

    [:octicons-arrow-right-24: Go to sample](https://github.com/google-agentic-commerce/AP2/tree/main/samples/android/scenarios/digital-payment-credentials/run.sh)

</div>

---

## Get Started and Build with Us

The Agent Payments Protocol provides a mechanism for secure payments, and it's
part of a larger picture to unlock the full potential of agent-enabled commerce.
We actively seek your feedback and contributions to help build the future of
commerce.

The complete technical specification, documentation, and reference
implementations are hosted in our public GitHub repository.

You can get started today by:

- Downloading and running our **code samples**.
- **Experimenting with the protocol** and its different agent roles.
- Contributing your feedback and **code** to the public repository.

[Visit the GitHub Repository](https://github.com/google-agentic-commerce/AP2)
