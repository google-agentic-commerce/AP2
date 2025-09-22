---
hide:
    - toc
---

<!-- markdownlint-disable MD041 -->
<div style="text-align: center;">
  <div class="centered-logo-text-group">
    <img src="/assets/ap2-logo-black.svg" alt="Agent Payments Protocol Logo" width="100">
    <h1>智能体支付协议 (AP2)</h1>
  </div>
</div>

## 什么是 AP2？

**智能体支付协议 (Agent Payments Protocol, AP2) 是为新兴智能体经济设计的开放协议
。** 它旨在为开发者、商户和支付行业提供安全、可靠且可互操作的智能体商务解决方案
。该协议作为开源
[智能体间通信协议 (Agent2Agent, A2A)](https://a2a-protocol.org/) 的扩展提供，更
多集成正在开发中。

<!-- prettier-ignore-start -->
!!! abstract ""

    使用 **[![ADK Logo](https://google.github.io/adk-docs/assets/agent-development-kit.png){class="twemoji lg middle"} ADK](https://google.github.io/adk-docs/)** _(或任何框架)_ 构建智能体，配备 **[![MCP Logo](https://modelcontextprotocol.io/mcp.png){class="twemoji lg middle"} MCP](https://modelcontextprotocol.io)** _(或任何工具)_，通过 **[![A2A Logo](https://a2a-protocol.org/latest/assets/a2a-logo-black.svg){class="twemoji sm middle"} A2A](https://a2a-protocol.org)** 协作，并使用 **![AP2 Logo](/assets/ap2-logo-black.svg){class="twemoji sm middle"} AP2** 来保障生成式 AI 智能体的支付安全。
<!-- prettier-ignore-end -->

<div class="grid cards" markdown>

- :material-play-circle:{ .lg .middle } **视频** 7分钟介绍

    ---
    
      <iframe width="560" height="315" src="https://www.youtube.com/embed/yLTp3ic2j5c?si=kfASyAVW8QpzUTho" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

- :material-file-document-outline:{ .lg .middle } **阅读文档**

    ---

    [:octicons-arrow-right-24: Google Cloud 发布 AP2 公告](https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol)

    探索 AP2 协议的详细技术定义

    [:octicons-arrow-right-24: 智能体支付协议规范](./specification.md)

    查看关键主题

    [:octicons-arrow-right-24: 概述](topics/what-is-ap2.md)<br>
    [:octicons-arrow-right-24: 核心概念](topics/core-concepts.md)<br>
    [:octicons-arrow-right-24: AP2、A2A 和 MCP](topics/ap2-a2a-and-mcp.md)<br>
    [:octicons-arrow-right-24: AP2 和 x402](topics/ap2-and-x402.md)<br>
    [:octicons-arrow-right-24: 隐私与安全](topics/privacy-and-security.md)<br>

</div>

---

## 为什么需要智能体支付协议

当今的支付系统假设人类直接在可信网站上点击"购买"。当自主智能体发起支付时，这一核
心假设被打破，导致当前系统无法回答的关键问题：

-   **授权：** 我们如何验证用户确实授权智能体进行特定购买？
-   **真实性：** 商户如何确保智能体的请求准确反映用户的真实意图，没有错误或 AI"
    幻觉"？
-   **责任归属：** 如果发生欺诈或错误交易，谁应当承担责任——用户、智能体开发者、
    商户，还是发卡方？

这种模糊性造成了信任危机，可能严重限制智能体支付的采用。没有通用协议，我们面临专
有支付解决方案碎片化生态系统的风险，这会让用户困惑、商户成本高昂，金融机构也难以
管理。AP2 旨在创建一种通用语言，让任何符合标准的智能体都能与任何符合标准的商户安
全交易。

---

## 核心原则和目标

智能体支付协议建立在旨在创建安全、公平生态系统的基本原则之上：

-   **开放性和互操作性：** 作为 A2A 和 MCP 的非专有开放扩展，AP2 促进创新竞争环
    境，扩大商户覆盖面，为用户提供选择权。
-   **用户控制和隐私：** 用户必须始终掌握控制权。协议的核心设计考虑隐私保护，使
    用基于角色的架构来保护敏感的支付详情和个人信息。
-   **可验证意图，而非推断行为：** 支付中的信任基于用户确定性的、不可否认的意图
    证明，直接解决智能体错误或幻觉的风险。
-   **清晰的交易责任归属：** AP2 为每笔交易提供不可否认的加密审计跟踪，有助于争
    议解决并为所有参与者建立信心。
-   **全球化和面向未来：** 作为全球基础设施设计，初始版本支持信用卡和借记卡等常
    见"拉取式"支付方式。路线图包括实时银行转账（如 UPI 和 PIX）和数字货币等"推送
    式"支付。

---

## 核心概念：可验证数字凭证 (VDCs)

智能体支付协议使用**可验证数字凭证 (VDCs)** 将信任机制融入系统。VDCs 是防篡改的
、加密签名的数字对象，作为交易的构建块。它们是智能体创建和交换的数据载体。主要有
三种类型：

-   **意图委托书：** 这种 VDC 捕获 AI 智能体可以代表用户进行购买的条件，特别是在
    "用户不在场"场景中。它为智能体提供在定义约束内执行交易的权限。
-   **购物车委托书：** 这种 VDC 捕获用户对特定购物车的最终明确授权，包括确切商品
    和价格，用于"用户在场"场景。用户在此委托书上的加密签名提供其意图的不可否认证
    明。
-   **支付委托书：** 与支付网络和发卡方共享的独立 VDC，旨在向其发出 AI 智能体参
    与和用户是否在场的信号，以帮助评估交易上下文。

这些 VDCs 在定义的基于角色的架构内运行，可以处理"用户在场"和"用户不在场"两种交易
类型。

了解更多请参见 [核心概念](topics/core-concepts.md)。

## 实际应用演示

<div class="grid cards" markdown>

-   **用户在场信用卡支付**

    ***

    演示使用传统信用卡支付的用户在场交易示例。

    [:octicons-arrow-right-24: 查看示例](https://github.com/google-agentic-commerce/AP2/tree/main/samples/python/scenarios/a2a/human-present/cards/)

-   **用户在场 x402 支付**

    ***

    演示使用 x402 协议进行支付的用户在场交易示例。

    [:octicons-arrow-right-24: 查看示例](https://github.com/google-agentic-commerce/AP2/tree/main/samples/python/scenarios/a2a/human-present/x402/)

-   **Android 数字支付凭证**

    ***

    演示在 Android 设备上使用数字支付凭证的示例。

    [:octicons-arrow-right-24: 查看示例](https://github.com/google-agentic-commerce/AP2/tree/main/samples/android/scenarios/digital-payment-credentials/run.sh)

</div>

---

## 开始使用并与我们共建

智能体支付协议提供了安全支付机制，它是释放智能体商务全部潜力的重要组成部分。我们
积极寻求您的反馈和贡献，共同构建商务的未来。

完整的技术规范、文档和参考实现托管在我们的公共 GitHub 仓库中。

您可以从以下方式开始：

-   下载并运行我们的**代码示例**。
-   **试验协议**及其不同的智能体角色。
-   向公共仓库贡献您的反馈和**代码**。

[访问 GitHub 仓库](https://github.com/google-agentic-commerce/AP2)
