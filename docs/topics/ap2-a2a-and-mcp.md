# AP2, A2A, and MCP

The Agent Payments Protocol (AP2) is designed to be an extension of the [Agent-to-Agent (A2A) protocol](https://a2a-protocol.org), and agents which implement AP2 are likely to use the [Model-Context Protocol (MCP)](https://modelcontextprotocol.org) to connect tools to their agents.

- AP2: Agents creating payment mandates and conducting commerce
- A2A: Agents communicating with other agents
- MCP: Agents using APIs as tools

## AP2 + A2A for Inter-Agent Communication for Commerce

The Agent Payments Protocol (AP2) is designed as an optional extension for open-source protocols like A2A and MCP, allowing developers to build upon existing work to create a secure and reliable framework for AI-driven commerce.

- AP2 is required to standardize the communication commerce details like mandates.
- A2A is required to standardize intra-agent communication, as soon as you have more than one agent you need A2A.

AP2 directly extends the Agent-to-Agent (A2A) protocol for multi-agent commerce transactions between actors like Shopping Agents, Merchants, and Credentials Providers.

## AP2 + MCP for External Resource Interaction

MCP is a protocol that standardizes how AI models and agents connect to and interact with external resources like tools, APIs, and data sources.

AP2 is designed to work with MCP servers, but as of Sept 2025, there is no MCP extension or plugin capability. Thus it is up to Agent builders to integrate MCP servers into their agents in accordance with AP2 specifications.

---

In essence, **A2A and MCP provide the foundational communication and interaction layers for AI agents**, enabling them to connect and perform tasks. **AP2 builds upon these layers by adding a specialized, secure payments extension**, addressing the unique challenges of authorization, authenticity, and accountability in AI-driven commerce. This allows agents to confidently browse, negotiate, buy, and sell on behalf of users by establishing verifiable proof of intent and clear accountability within transactions.
