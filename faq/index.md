# Frequently Asked Questions

1. What can I do with this protocol today?

   - We built sample agents around the core AP2 python library that demonstrate a rich shopping experience. Launch the agents, and try shopping for your favorite products! These samples mock actual payment service providers so you can explore with no dependencies. Specifically, watch for the mandates as the agents do their thing. We will be publishing more samples and SDKs soon, and we'd love to see your ideas! You can use the code samples to create your own implementation of a payment taking place between multiple AI Agents or extend the protocol to show new kinds of payment scenarios *(e.g., showing a payment made by a different payment method or using a different way of authentication)*.

1. Can I build my own agent for any of these roles, taking one of these as a template?

   - Yes you can build your own agent using any of the [roles](../ap2/implementation_considerations/). Get started building with [ADK](https://google.github.io/adk-docs/) and [Agent Builder](https://cloud.google.com/products/agent-builder) from Google Cloud, or any other platform you choose to build agents.

1. Can I build my own agent to participate in this protocol?

   - Yes, you can build an agent for any of the defined [roles](../ap2/implementation_considerations/). Any agent, on any framework (like LangGraph, AG2 or CrewAI), or on any runtime, is capable of implementing AP2.

1. Can I try this out without actually making a payment?

   - You can consider setting this up in your internal environments where you may already have ways to invoke fake payment methods which do not require real money movement.

1. Is there a MCP server or a SDK which is ready for "my framework of choice"?

   - We are working on an SDK and a MCP server right now, in collaboration with payment service providers. Check back soon.

1. Does this work with x402 standard for crypto payments?

   - We designed AP2 to be a payment-agnostic protocol, so that agentic commerce can securely take place across all types of payment systems. It provides a secure, auditable foundation whether an agent is using a credit card or transacting with stablecoins. This flexible design allows us to extend its core principles to new ecosystems, ensuring a consistent standard for trust everywhere.

     As a first step, check out \[google-agentic-commerce/a2a-x402\](https://github.com/google-agentic- commerce/a2a-x402/) which is an implementation of A2A in conjunction with the x402 standard. We will be aligning this closely with AP2 over time to make it easy to compose solutions which include all payment methods, including stablecoins.

1. What are verifiable credentials?

   - These are standardized, cryptographically secure data objects (like the Checkout Mandate and Payment Mandate) that serve as tamper-evident, non-disputable, and cryptographically signed building blocks for a transaction.

1. How does the protocol ensure user control and privacy?

   - The protocol is designed to ensure the user is always the ultimate authority and has granular control over their agents' activities. It protects sensitive user information, such as conversational prompts and personal payment details, by preventing shopping agents from accessing sensitive PCI or PII data through payload encryption and selective disclosure to ensure data minimization.

1. How does AP2 address transaction accountability?

   - A primary objective is to provide supporting evidence that helps payment networks establish accountability and liability principles. In a dispute, the network adjudicator (e.g., Card Network) can use the user-signed Checkout Mandate and compare the details of what was agreed upon between the agent and the consumer against the details in the dispute to help determine transaction accountability.

1. What prevents an agent from "hallucinating" and making an incorrect purchase?

   - The principle of Verifiable Intent, Not Inferred Action addresses this risk. Transactions must be anchored to deterministic, non-repudiable proof of intent from all parties, such as the user-signed Checkout Mandate, rather than relying only on interpreting the probabilistic and ambiguous outputs of a language model.

1. Why was crypto and Web3 support included from day one?

   - Supporting a broad range of payment types, including digital payment methods ensures the protocol is future-proof. Collaboration with partners like Coinbase, Ethereum Foundation, and Metamask validates AP2's flexibility and bridges the gap between the traditional and Web3 economies, enabling novel use cases like micropayments.

1. How can I get involved?

   - AP2 is an open source project created by Google, similar to the A2A protocol. Contributions are welcome on Github as discussions, bugs, feature requests, and PRs. Collaboration is happening right now, with new samples, integrations and SDKs being developed – Github is the best way to communicate with the AP2 team.

1. How is UCP different from AP2? And how does it relate to your agentic checkout feature?

   - AP2: Agent Payments Protocol (AP2) is designed to provide a common language for agents to transact with security and accountability. While the Universal Commerce Protocol orchestrates the broader purchase lifecycle, AP2 is the specialized payment layer responsible for authorizing and signing transactions. AP2 becomes critical in the flow when, in the near future, the transactions become truly agentic and users delegate purchases to their AI Agents. This modular design fosters trust among buyers, merchants, and providers while retaining flexibility. Merchants will be able to integrate AP2 as an extension within the Universal Commerce Protocol for transactions which are driven by AI Agents.
   - Agentic checkout: Our agentic checkout feature buys things on your behalf directly on a store's website at your direction. The Universal Commerce Protocol is different in that it enables native buying on AI Mode and Gemini. Users are connected directly with the merchant when they natively buy on AI Mode and Gemini, which unlocks additional features such as important post-purchase signals, like order status updates. Soon-to-be available benefits include using loyalty points, and shopping from a previous cart.

1. How do I know when to use AP2?

   - If you are a merchant who would like to showcase products and allow users to complete inline checkout on Google’s AI surfaces like AI Mode and Gemini, then you should use Universal Commerce Protocol. You can enhance the protocol with the AP2 extension if you plan to build autonomous purchase scenarios where AI Agents can make purchases in the user’s absence.
   - Outside of Google’s discovery surfaces, if you would like to enable a payments flow between two AI Agents or you want to add verifiable credentials to payment flows between your discovery surface and an AI Agent then you can continue to leverage AP2.

1. What’s next for AP2?

   - The core specification work will continue in [FIDO](https://blog.google/products-and-platforms/platforms/google-pay/agent-payments-protocol-fido-alliance/), ensuring it continues as an open, interoperable protocol for all agentic payments.
   - The code samples and SDK will continue to be enhanced, remaining a state-of-the-art implementation of the AP2 specification.
