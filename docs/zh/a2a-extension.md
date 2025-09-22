# AP2 的 A2A 扩展

!!! info

    这是一个实现智能体支付协议 (AP2) 的 [智能体间通信协议 (A2A) 扩展](https://a2a-protocol.org/latest/topics/extensions/)。

    `v0.1-alpha` (参见 [路线图](roadmap.md))

## 扩展 URI

此扩展的 URI 是
`https://github.com/google-agentic-commerce/ap2/tree/v0.1`。

支持 AP2 扩展的智能体必须使用此 URI。

## 智能体 AP2 角色

每个支持 AP2 扩展的智能体必须执行 AP2 规范中的至少一个角色。此角色在 [AgentCard 扩展对象](#agentcard-extension-object) 中指定。

## AgentCard 扩展对象

支持 AP2 扩展的智能体必须使用 [扩展 URI](#extension-uri) 来宣传其对 AgentCard 扩展的支持。

`AgentExtension` 中使用的 `params` 必须符合以下 JSON schema：

```json
{
  "type": "object",
  "name": "AP2ExtensionParameters",
  "description": "The schema for parameters expressed in AgentExtension.params for the AP2 A2A extension.",
  "properties": {
    "roles": {
      "type": "array",
      "name": "AP2 Roles",
      "description": "The roles that this agent performs in the AP2 model.",
      "minItems": 1,
      "items": {
        "enum": ["merchant", "shopper", "credentials-provider", "payment-processor"]
      }
    }
  },
  "required": ["roles"]
}
```

此 schema 也可以用以下 Pydantic 类型定义表示：

```py
AP2Role = "merchant" | "shopper" | "credentials-provider" | "payment-processor"

class AP2ExtensionParameters(BaseModel):
  # 此智能体在 AP2 模型中执行的角色。至少需要一个值。
  roles: list[AP2Role] = Field(..., min_length=1)

```

执行 `"merchant"` 角色的智能体应该将 AP2 扩展设置为必需的。这表明客户端必须能够使用 AP2 扩展来为智能体提供的服务付费。

以下列表显示了声明 AP2 扩展支持的 AgentCard。

```json
{
  "name": "Travel Agent",
  "description": "This agent can book all necessary parts of a vacation",
  "capabilities": {
    "extensions": [
      {
        "uri": "https://github.com/google-agentic-commerce/ap2/tree/v0.1",
        "description": "This agent can pay for reservations on the user's behalf",
        "params": {
          "roles": ["shopper"]
        }
      }
    ]
  },
  "skills": [
    {
      "id": "plan_vacation",
      "name": "Plan Vacation",
      "description": "Plan a fun vacation, creating a full itinerary",
      "tags": []
    },
    {
      "id": "book_itinerary",
      "name": "Book Itinerary",
      "description": "Place reservations for all components of an itinerary (flights, hotels, rentals, restaurants, etc.)",
      "tags": []
    }
  ]
}
```

## AP2 数据类型容器

以下部分描述了如何将 AP2 数据类型封装到 A2A 数据类型中。

### IntentMandate 消息

要提供 `IntentMandate`，智能体必须创建一个 IntentMandate 消息。
IntentMandate 消息是具有以下要求的 A2A `Message` 配置文件。

消息必须包含一个 DataPart，该 DataPart 包含键 `ap2.mandates.IntentMandate` 和符合 `IntentMandate` schema 的值。

消息可以包含一个 DataPart，该 DataPart 包含键 `risk_data`，其值包含实现定义的风险信号。

以下列表显示了 IntentMandate 消息的 JSON 渲染。

```json
{
  "messageId": "e0b84c60-3f5f-4234-adc6-91f2b73b19e5",
  "contextId": "sample-payment-context",
  "taskId": "sample-payment-task",
  "role": "user",
  "parts": [
    {
      "kind": "data",
      "data": {
        "ap2.mandates.IntentMandate": {
          "user_cart_confirmation_required": false,
          "natural_language_description": "I'd like some cool red shoes in my size",
          "merchants": null,
          "skus": null,
          "required_refundability": true,
          "intent_expiry": "2025-09-16T15:00:00Z"
        }
      }
    }
  ]
}
```

### CartMandate 工件

要发起支付请求，商户智能体必须生成 CartMandate 工件。CartMandate 工件是 A2A 工件的配置文件。商户智能体在收集所有必需的影响支付的信息之前，不得生成 CartMandate。影响支付的信息是客户端提供的任何改变购物车内容因而改变应付价格的信息。例如，配送地址可能会改变包含在购物车内容中的配送价格。

CartMandate 工件必须有一个 DataPart，该 DataPart 包含键 `ap2.mandates.CartMandate` 和符合 CartMandate schema 的相应对象。

CartMandate 工件可以包含一个 DataPart，该 DataPart 包含键 `risk_data` 和包含实现定义的风险信号数据的值。

以下列表显示了 CartMandate 工件的 JSON 表示。

```json
{
  "name": "Fancy Cart Details",
  "artifactId": "artifact_001",
  "parts": [
    {
      "kind": "data",
      "data": {
        "ap2.mandates.CartMandate": {
          "contents": {
            "id": "cart_shoes_123",
            "user_signature_required": false,
            "payment_request": {
              "method_data": [
                {
                  "supported_methods": "CARD",
                  "data": {
                    "payment_processor_url": "http://example.com/pay"
                  }
                }
              ],
              "details": {
                "id": "order_shoes_123",
                "displayItems": [
                  {
                    "label": "Cool Shoes Max",
                    "amount": {
                      "currency": "USD",
                      "value": 120.0
                    },
                    "pending": null
                  }
                ],
                "shipping_options": null,
                "modifiers": null,
                "total": {
                  "label": "Total",
                  "amount": {
                    "currency": "USD",
                    "value": 120.0
                  },
                  "pending": null
                }
              },
              "options": {
                "requestPayerName": false,
                "requestPayerEmail": false,
                "requestPayerPhone": false,
                "requestShipping": true,
                "shippingType": null
              }
            }
          },
          "merchant_signature": "sig_merchant_shoes_abc1",
          "timestamp": "2025-08-26T19:36:36.377022Z"
        }
      }
    },
    {
      "kind": "data",
      "data": {
        "risk_data": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...fake_risk_data"
      }
    }
  ]
}
```

### PaymentMandate 消息

要向智能体提供 PaymentMandate，客户端必须构造一个 PaymentMandate 消息。PaymentMandate 消息是 A2A 消息的配置文件。

PaymentMandate 消息必须包含一个 DataPart，该 DataPart 具有键 `ap2.mandates.PaymentMandate`，且值必须是符合 `PaymentMandate` schema 的对象。

PaymentMandate 消息可以包含其他部分。

以下列表显示了 PaymentMandate 消息的 JSON 渲染。

```json
{
  "messageId": "b5951b1a-8d5b-4ad3-a06f-92bf74e76589",
  "contextId": "sample-payment-context",
  "taskId": "sample-payment-task",
  "role": "user",
  "parts": [
    {
      "kind": "data",
      "data": {
        "ap2.mandates.PaymentMandate": {
          "payment_details": {
            "cart_mandate": "<user-signed hash of the cart mandate>",
            "payment_request_id": "order_shoes_123",
            "merchant_agent_card": {
              "name": "MerchantAgent"
            },
            "payment_method": {
              "supported_methods": "CARD",
              "data": {
                "token": "xyz789"
              }
            },
            "amount": {
              "currency": "USD",
              "value": 120.0
            },
            "risk_info": {
              "device_imei": "abc123"
            },
            "display_info": "<image bytes>"
          },
          "creation_time": "2025-08-26T19:36:36.377022Z"
        }
      }
    }
  ]
}
```
