# Frequently Asked Questions

1. What can I do with this protocol today?

    - We built sample agents around the core AP2 python library that demonstrate a rich shopping experience. Launch the agents, and try shopping for your favorite products\! These samples mock actual payment service providers so you can explore with no dependencies. Specifically watch for the mandates as the agents do their thing. We will be publishing more samples and SDKs soon, and we'd love to see you're ideas\! You can also use the code samples to create your own implementation of a payment taking place between multiple AI Agents or extend the protocol to show new kinds of payment scenarios (_say, showing a payment made by a different payment method or using a different way of authentication_).

2. Can I build my own agent for any of these roles, taking one of these as a template?

    - Yes you can build your own Agent using any Agent tooling to stand up an Agent. One place to start is the [ADK](https://google.github.io/adk-docs/) and [Agent Builder](https://cloud.google.com/products/agent-builder), or anywhere else you can build your own agents.

3. Can I build my own agent to participate in this protocol??

    - Yes, you can build an agent for any of the defined roles. Any agent, on any framework (like LangGraph or CrewAI), or on any runtime, is capable of implementing AP2.

4. Can I try this out without actually making a payment?

    - You can consider setting this up in your internal environments where you may already have ways to invoke fake payment methods which do not require real money movement.

5. Is there a MCP server or a SDK which is ready for \<my framework of choice\>?

    - We are working on a SDK and a MCP servers right now, in collaboration with payment service providers. Check back soon.

6. Does this work with x402 standard for crypto payments?
    - We designed AP2 to be a payment-agnostic protocol, so that agentic commerce can securely take place across all types of payment systems. It provides a secure, auditable foundation whether an agent is using a credit card or transacting with stablecoins. This flexible design allows us to extend its core principles to new ecosystems, ensuring a consistent standard for trust everywhere.
As a first step, check out [this implementation](https://github.com/google-agentic-commerce/a2a-x402/) of A2A in conjunction with the x402 standard. We will be aligning this closely with AP2 over time to make it easy to compose solutions which include all payment methods, including stablecoins.

7. What are verifiable credentials?
    - These are standardized, cryptographically secure data objects (like the Cart Mandate and Intent Mandate) that serve as tamper-evident, non-disputable, and cryptographically signed building blocks for a transaction.

8. How does the protocol ensure user control and privacy?
    - The protocol is designed to ensure the user is always the ultimate authority and has granular control over their agents' activities. It protects sensitive user information, such as conversational prompts and personal payment details, by preventing shopping agents from accessing sensitive PCI or PII data through payload encryption and a role-based architecture.

9. How does AP2 address transaction accountability?
    - A primary objective is to provide supporting evidence that helps payment networks establish accountability and liability principles. In a dispute, the network adjudicator (e.g., Card Network) can receive the user-signed

10. What prevents an agent from "hallucinating" and making an incorrect purchase? 
    - The principle of Verifiable Intent, Not Inferred Action addresses this risk. Transactions must be anchored to deterministic, non-repudiable proof of intent from all parties, such as the user-signed Cart or Intent Mandate, rather than relying only on interpreting the probabilistic and ambiguous outputs of a language model.

