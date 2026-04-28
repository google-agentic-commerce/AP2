# Executive Summary

AI agents will redefine the landscape of digital commerce, promising unprecedented convenience, personalization, and efficiency. However, this shift exposes a fundamental challenge: the world's existing payments infrastructure was not designed for a future where autonomous, non-human agents act on a user's behalf, or transact with each other. Current payment protocols, built on the assumption of direct human-initiated interaction with trusted interfaces, lack the mechanisms to securely validate an agent's authenticity and authority to transact. This creates ambiguity around transaction liability, and threatens adoption of agentic commerce.

Without a common, trusted protocol, the industry faces the prospect of a fragmented and insecure ecosystem, characterized by proprietary, siloed solutions that increase complexity for merchants, create friction for users, and prevent financial institutions from uniformly assessing risk. To address this gap, this protocol proposes an open, interoperable protocol for agent payments. This protocol, designed as an extension for emerging agent-to-agent (A2A), model-context protocols (MCP), and Universal Commerce Protocol (UCP), establishes a secure and reliable framework for AI-driven commerce.

## The New Frontier of Commerce: Why Agent Payments Require a Foundational

Protocol

### 1.1 The Rise of Agent Commerce

The evolution of digital interaction is entering a new phase, moving beyond direct manipulation of UIs to conversational and delegated task execution. AI agents are rapidly becoming primary actors, capable of understanding complex user requests and executing multi-step tasks autonomously. In commerce, this translates into a paradigm shift where agents will manage everything from routine purchases and subscription management to complex product research, price negotiation, and dynamic order bundling across multiple vendors. This new era of agent commerce promises to unlock immense value, offering users a hyper- personalized and frictionless shopping experience while providing merchants with new, intelligent channels to reach and serve customers.

### 1.2 The Foundational Gap: A Crisis of Trust and Liability

Despite its promise, the rise of agent commerce exposes a critical vulnerability in the existing digital payments infrastructure. Today's payment protocols are designed around the principle of a human user directly interacting with a trusted interface, such as a merchant's website or a payment provider's app. Authentication, authorization, and liability are all predicated on this direct human involvement.

Autonomous agents shatter this assumption. When an agent initiates a payment, fundamental questions arise that current systems are ill-equipped to answer:

- Authorization & Auditability: What verifiable proof demonstrates that the user granted the agent the specific authority to make this particular purchase?
- Authenticity of Intent: How can a merchant or payment processor be certain that the agent's request accurately reflects the human user's true intent?
- Agent Error and "Hallucination": How does the system protect against agent errors, such as misinterpreting a user's request or "hallucinating" product details, which could lead to incorrect purchases?
- Accountability: In the event of a fraudulent or erroneous transaction, who is accountable? The user who delegated the task? The developer of the shopping agent? The merchant who accepted the order? The payment network that processed it? Or the PSP/orchestration layer?

This ambiguity creates a crisis of trust. Without a robust framework to validate agent authority and assign liability clearly, financial institutions may be hesitant to approve agent-initiated transactions, merchants will be exposed to unacceptable levels of fraud risk, and users will be reluctant to delegate financial authority to agents.

### 1.3 The Risk of a Fragmented Ecosystem

In the absence of a universally adopted protocol, the industry will inevitably move toward a patchwork of proprietary, closed-loop solutions. Large retailers might develop bespoke integrations for their specific agents, and payment providers might create siloed ecosystems that do not interoperate. This fragmentation would have severe negative consequences:

- For Users: A confusing and inconsistent experience, where their preferred agent may only work with a limited set of merchants or payment methods.
- For Merchants: High development and maintenance costs to support multiple, non-standard agent payment integrations, creating a significant barrier to entry for small and medium-sized businesses.
- For the Payments Ecosystem: An inability to collect common signals across all agent transactions in order to consistently mitigate fraud, leading to higher costs and suppressed transaction approval rates.

An open, interoperable protocol is the most viable path forward. It creates a common language for all participants. It allows for additional data points to be shared about the transaction in a way that wasn’t possible before and ensures that any compliant agent can securely transact with any compliant merchant, fostering a competitive and innovative marketplace.

## Section 2: Guiding Principles for a Trusted Agent Economy

The design of this proposed protocol is rooted in a set of core principles intended to build a sustainable, secure, and equitable ecosystem for all participants. These principles serve as the philosophical foundation for the technical architecture that follows.

### 2.1 Openness and Interoperability

This protocol is proposed as a non-proprietary, open extension for existing and future agent-to-agent (A2A), model-context protocol (MCP), and Universal Commerce Protocol (UCP). The goal is to provide a common, interoperable payments layer that can be adopted by any ecosystem player. This approach fosters a healthy, competitive environment where developers can innovate on agent capabilities, merchants can reach the broadest possible audience, and users can choose the combination of agents and services that best suits their needs.

### 2.2 User Control and Privacy by Design

The user must always be the ultimate authority. The protocol is designed to ensure users have granular control and transparent visibility over their agents' activities.

Privacy is a core design tenet. The protocol is designed to protect sensitive user information, including the content of their conversational prompts, the items they are buying and payment details. Through Selective Disclosure, agents involved in the shopping process are prevented from accessing sensitive payment card industry (PCI) data which is handled exclusively by the specialized entities and the secure elements of the payment infrastructure. This focus on privacy and data minimization also ensures that entities only see the data that is absolutely necessary for them to perform their roles.

### 2.3 Verifiable Intent, Not Inferred Action

Trust in an AI Agent system cannot be based only on interpreting the ambiguous, probabilistic outputs of a large language model. Transactions must be anchored to deterministic, non-repudiable proof of intent from all parties. This principle directly addresses the risk of agent "hallucination" and misinterpretation.

### 2.4 Clear Transaction Accountability

For the payments ecosystem to embrace agent commerce, there can be no ambiguity regarding transaction accountability. A primary objective of this protocol is to provide supporting evidence that helps payment networks establish accountability and liability principles. This clarity is table stakes for gaining the confidence and participation of merchants, issuers, and payment networks.

## Section 3: Architectural Overview: A Role-Based Ecosystem for Secure

Transactions

To achieve its goals of security, interoperability, and clear accountability, the proposed protocol defines a role-based architecture. Each actor in the ecosystem has a distinct and well-defined set of responsibilities, ensuring a separation of concerns that enhances security and simplifies integration.

The agent payments ecosystem consists of the following key roles:

- **Shopping Agent (SA):** The Shopping Agent is the primary agent performing product discovery, building the checkout and executing the purchase.
- **Credential Provider (CP):** The Credential Provider is the source of Payment Credentials for the purchase. They are responsible for verifying that this Agent is authorized to access this Payment Credential, and scoping the Payment Credential appropriately.
- **Merchant (M)**: The Merchant is the source of the Checkout. They are responsible for owning the catalog and fulfilling orders.
- **Merchant Payment Processor (MPP)**: The Merchant Payment Processor role is responsible for processing payments for purchases. They are responsible for verifying that the Payment Credential has been authorized to pay for this Checkout.
- **Trusted Surface (TS):** The Trusted Surface role is a UI surface that is trusted to get informed user consent for an Intent before creating a user-signed Mandate.
- **Network and Issuer**: The provider of the payment network and issuer of payment credentials to the human user. The Credentials Provider may need to interact with the network for issuance of specific tokens for AI agent transactions and the Merchant/PSP may submit these transactions for authorization to issuers via the networks.

Some non-normative examples of how the roles could be combined:

- The provider of the Shopping Agent could also provide a non-agentic Trusted Surface within their application.
- The Shopping Agent could also provide their own Credential Provider.
- The Merchant could provide their own Merchant Payment Processor
- The Merchant could be a Credential Provider.

## Section 4: Core User Journeys

### 4.1 Human Present Transaction

Human delegates a task to an AI Agent which requires a payment to be made (e.g., for shopping) and human is available when the payment has to be authorized. A typical (but not only) way this may happen is as below:

- Setup: The User may set up a connection between their preferred Shopping Agent & any of the supported Credential Providers. This may require the User to authenticate themselves on a surface owned by the Credential Provider.
- Discovery & Negotiation: The User provides a shopping task to their chosen AI Agent (*which may activate a specialized Shopping Agent to complete the task*). The Shopping Agent interacts with one or more Merchants to assemble a cart that satisfies the User's request. This may include the ability for the merchant to provide loyalty, offers, cross-sell and up-sell information (*via the integration between the Shopping Agent & Merchant*) which the Shopping Agent should represent to the user .
- Merchant Validates Cart: A SKU or set of SKUs are authorized by the User for purchase. This is communicated by the Shopping Agent to the Merchant to initiate order creation. The Merchant must sign the Cart that they create for a user, signaling that they will fulfill this cart.
- Provide Payment Methods: The Shopping Agent may provide the payment context to the Credentials Provider and request an applicable payment method (shared as a reference or in encrypted form), along with any loyalty/discount information which may be relevant for the payment method selection (*say, card points which can be redeemed towards the txn*).
- Show Cart: The Shopping Agent presents the final cart and applicable payment method to the user in a trusted surface and the user can approve it via an authentication process.
- Sign & Pay: The user’s signed approval must create a cryptographically signed “Checkout Mandate”. This mandate contains the explicit goods being purchased & their confirmation of purchase. It is shared with the Merchant so they can use this as evidence in case of disputes. Separately, the Payment Mandate may be shared with the network & issuer for transaction authorization.
- Payment Execution: The Payment Mandate must be conveyed to the Credential provider and Merchant to complete the transaction. There may be multiple ways this might happen. For example,
- The Shopping Agent (SA) may request Credentials Provider to complete a payment with the Merchant OR,
- the SA may submit an order with the merchant, triggering a payment authorization flow where the merchant/PSP requests payment method from the Credentials Provider.
- Send Transaction to Issuer: The Merchant or PSP routes the transaction to the issuer or the network within which the payment method operates. The transaction packet may be appended with AI agent presence signals ensuring network/issuer get visibility into agentic transactions.
- Challenge: Any party (issuer, credential provider, merchant etc.) may choose to challenge the transaction through existing mechanisms like 3DS2. This challenge needs to be presented to the user by the Trusted Surface (*an example of this would be a hosted 3DS*) and may require a redirect to a trusted surface to complete.
- Resolve Challenge: The user should have a way to resolve the challenge on a trusted surface (say, banking app, website etc.)
- Authorize Transaction: The issuer approves the payment and confirms success back. This is communicated to the User and the Merchant so that the order can be fulfilled. A payment receipt is shared with the Credential Provider confirming the transaction result. In case of a decline, that can also be appropriately communicated.

### 4.2 Human Not Present Transaction

Human delegates a task to an AI Agent which requires a payment to be made (e.g., for shopping) and human wants the AI Agent to proceed with the payment in their absence. Some canonical scenarios here could be “*buy these shoes for me when the price drops below $100*” or “*buy 2 tickets to this concert as soon as they become available, make sure we’re close to the main stage but don’t spend more than $1000*”.

Key changes from the Human Present modality are noted below:

- The Agent must repeat back to the User what they think they are expected to purchase. The User must approve this and confirm that they would like the agent to proceed with the purchase in their absence. This is done by the User going through in-session authentication (biometric etc.) to confirm their intent.
- The “Checkout Mandate” signed by the user now contains the list of conditions under which the SA can fulfill the user’s order. This mandate is in an “Open” state while the Agent tries to meet the user’s requirements. Once the SA determines that the requirements can be met, the mandate is “Closed”.
- Merchant can force user confirmation: If the Merchant is unsure about their ability to fulfill the user’s needs (e.g. the request is not for a specific SKU), they can force the user to come back into session to confirm the purchase conditions or provide additional information.
