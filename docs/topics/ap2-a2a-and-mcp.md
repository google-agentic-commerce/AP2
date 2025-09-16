# AP2, A2A, and MCP

The Agent Payments Protocol (AP2) is designed to be an extension of the
[Agent-to-Agent (A2A) protocol](https://a2a-protocol.org) and work in concert
with [Model-Context Protocol (MCP)](https://modelcontextprotocol.org).

<!-- prettier-ignore-start -->
!!! abstract "Communication disambiguation"

    -   MCP: Agents communicate with data (APIs)
    -   A2A: Agents communicate with other Agents (tasks and messages)
    -   AP2: Agents communicate about payments (mandates)
<!-- prettier-ignore-end -->

## AP2 + A2A for Inter-Agent Communication for Payments

The Agent Payments Protocol (AP2) is designed as an optional extension for
open-source protocols like A2A and MCP, allowing developers to build upon
existing work to create a secure and reliable framework for AI-driven payments.

-   AP2 is required to standardize the communication payments details like
    mandates.
-   A2A is required to standardize intra-agent communication, as soon as you
    have more than one agent you need A2A.

AP2 directly extends the Agent-to-Agent (A2A) protocol for multi-agent payments
transactions between actors like Shopping Agents, Merchants, and Credentials
Providers.

## AP2 + MCP for External Resource Interaction

MCP is a protocol that standardizes how AI models and agents connect to and
interact with external resources like tools, APIs, and data sources.

Developers can implement their own tools to integrate with providers.

We are working on MCP servers for AP2.

---

In essence, **A2A and MCP provide the foundational communication and interaction
layers for AI agents**, enabling them to connect and perform tasks. **AP2 builds
upon these layers by adding a specialized, secure payments extension**,
addressing the unique challenges of authorization, authenticity, and
accountability in AI-driven payments. This allows agents to confidently browse,
negotiate, buy, and sell on behalf of users by establishing verifiable proof of
intent and clear accountability within transactions.
