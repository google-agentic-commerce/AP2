# Privacy and Security

The Agent Payments Protocol (AP2) is designed with privacy and security as
foundational pillars. By re-imagining the flow of transactions for an AI-native
world, the protocol introduces new safeguards while adapting existing security
measures.

## Core Principles

- **User Control and Privacy by Design**: The user must always be the ultimate
    authority. The protocol is architected to give users granular control and
    transparent visibility over their agents' financial activities. Privacy is a
    core design tenet, not an afterthought. The protocol is designed to protect
    sensitive user information, including conversational prompts and personal
    payment details.

- **Role-Based Architecture**: A key security feature is the separation of
    concerns among the different actors (Shopping Agent, Credentials Provider,
    Merchant). This architecture ensures that agents involved in the shopping
    and discovery process are prevented from accessing sensitive payment card
    industry (PCI) data or other personally identifiable information (PII). This
    sensitive data is handled exclusively by specialized entities like the
    Credentials Provider and the secure elements of the existing payment
    infrastructure.

## A New Risk Landscape

The shift from direct human interaction to delegated agentic payments introduces
new risk factors that the protocol is designed to mitigate over time. All
participants in the ecosystem must re-evaluate how they establish trust and
manage risk. Key considerations include:

- **User Asynchronicity**: The user may not be present for the entire payment
    journey, requiring robust, verifiable mandates to stand in for their
    real-time approval.
- **Delegated Trust**: Actors must now trust an agent to initiate a payment on
    a user's behalf, making the verification of the agent's identity and
    authority critical.
- **Indirect Trust Establishment**: The Credentials Provider may not have a
    direct relationship with the merchant and must rely on the Shopping Agent to
    bridge that trust gap securely.
- **Agent Identity**: The Shopping Agent's identity becomes a new, critical
    signal for fraud and risk analysis, requiring new methods of verification.

The protocol provides a common language for sharing risk signals between
entities, allowing for a more holistic and secure assessment of each
transaction. Existing risk systems that merchants, networks, and issuers have in
place can be augmented with new data points from the agentic flow, such as the
`PaymentMandate`, ensuring backward compatibility and enhancing security.
