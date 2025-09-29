# A2A Extension for AP2

!!! info

    This is an [Agent2Agent (A2A) extension](https://a2a-protocol.org/latest/topics/extensions/)
    implementing the Agent Payments Protocol (AP2).

    `v0.1-alpha` (see [roadmap](roadmap.md))

## Extension URI

The URI for this extension is
`https://github.com/google-agentic-commerce/ap2/tree/v0.1`.

Agents that support the AP2 extension MUST use this URI.

## Agent AP2 Role

Every Agent that supports the AP2 extension MUST perform at least one Role from
the AP2 specification. This role is specified in the
[AgentCard](#agentcard-extension-object).

## AgentCard Extension Object

Agents that support the AP2 extension MUST advertise their support for an
AgentCard extension, using the [Extension URI](#extension-uri).

The `params` used in the `AgentExtension` MUST adhere to the following JSON
schema:

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
        "enum": ["merchant", "shopper", "credentials-provider", "payment-processor", "micropayment-provider", "streaming-payment-consumer"]
      }
    }
  },
  "required": ["roles"]
}
```

This schema is also expressed by the following Pydantic type definition:

```py
AP2Role = "merchant" | "shopper" | "credentials-provider" | "payment-processor" | "micropayment-provider" | "streaming-payment-consumer"

class AP2ExtensionParameters(BaseModel):
  # The roles this agent performs in the AP2 model. At least one value is required.
  roles: list[AP2Role] = Field(..., min_length=1)

```

Agents that perform the `"merchant"` role SHOULD set the AP2 extension to
required. This indicates that clients must be able to use the AP2 extension to
pay for services offered by the agent.

The following listing shows an AgentCard declaring AP2 extension support.

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

## Micropayment Channel Capabilities

Agents that support micropayment channels can advertise their capabilities through additional parameters in the AgentCard extension. This enables high-frequency, sub-cent transactions for AI inference, data streaming, and other pay-per-use services.

### Micropayment Provider Example

```json
{
  "name": "AI Inference Service",
  "description": "High-performance AI model with pay-per-token pricing",
  "capabilities": {
    "extensions": [
      {
        "uri": "https://github.com/google-agentic-commerce/ap2/tree/v0.1",
        "description": "Micropayment channels for AI inference",
        "params": {
          "roles": ["merchant", "micropayment-provider"],
          "payment_channels": {
            "supported": true,
            "min_deposit": "1.0",
            "rate_per_call": "0.001",
            "rate_per_token": "0.0001",
            "supported_currencies": ["USDC", "PYUSD", "ETH"],
            "blockchain_networks": ["ethereum", "polygon", "kite"],
            "max_channel_duration": "86400",
            "checkpoint_frequency": "30",
            "streaming_payments": true
          }
        }
      }
    ]
  }
}
```

### Streaming Payment Consumer Example

```json
{
  "name": "Data Analytics Agent",
  "description": "Consumes real-time data feeds with streaming payments",
  "capabilities": {
    "extensions": [
      {
        "uri": "https://github.com/google-agentic-commerce/ap2/tree/v0.1",
        "description": "Streaming payments for data consumption",
        "params": {
          "roles": ["shopper", "streaming-payment-consumer"],
          "payment_streams": {
            "max_concurrent_streams": 5,
            "supported_rate_types": ["per_second", "per_byte", "per_request"],
            "auto_pause_threshold": "10.0",
            "preferred_currencies": ["USDC", "DAI"],
            "quality_requirements": {
              "max_latency_ms": 100,
              "min_throughput_mbps": 10
            }
          }
        }
      }
    ]
  }
}
```

### Payment Channel Parameters Schema

The `payment_channels` object in the extension params supports the following schema:

```json
{
  "type": "object",
  "name": "PaymentChannelCapabilities",
  "properties": {
    "supported": {
      "type": "boolean",
      "description": "Whether payment channels are supported"
    },
    "min_deposit": {
      "type": "string",
      "description": "Minimum deposit required to open a channel"
    },
    "rate_per_call": {
      "type": "string",
      "description": "Cost per API call or request"
    },
    "rate_per_token": {
      "type": "string",
      "description": "Cost per AI token for inference services"
    },
    "supported_currencies": {
      "type": "array",
      "items": {"type": "string"},
      "description": "List of supported payment currencies"
    },
    "blockchain_networks": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Supported blockchain networks"
    },
    "max_channel_duration": {
      "type": "string",
      "description": "Maximum channel duration in seconds"
    },
    "checkpoint_frequency": {
      "type": "string",
      "description": "How often to create payment checkpoints (seconds)"
    },
    "streaming_payments": {
      "type": "boolean",
      "description": "Whether streaming payments are supported"
    }
  }
}
```

## AP2 Data Type Containers

The following sections describe how AP2 data types are encapsulated into A2A
data types.

### IntentMandate Message

To provide an `IntentMandate`, the agent MUST create an IntentMandate Message.
An IntentMandate Message is an A2A `Message` profile with the following
requirements.

The Message MUST contain a DataPart that contains a key of
`ap2.mandates.IntentMandate` and a value that adheres to the `IntentMandate`
schema.

The Message MAY contain a DataPart that contains a key of `risk_data`, where the
value contains implementation-defined risk signals.

The following listing shows the JSON rendering of an IntentMandate Message.

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

### CartMandate Artifact

To initiate a request for payment, a Merchant Agent MUST produce a CartMandate
Artifact. The CartMandate Artifact is a profile of an A2A Artifact. A Merchant
Agent MUST NOT produce a CartMandate until all required payment-impacting
information has been collected. Payment-impacting information is any information
provided by a client that changes the CartContents, and therefore the price to
be paid. For example, a shipping address may change the price for shipping that
is included in the CartContents.

The CartMandate Artifact MUST have a DataPart that contains a key of
`ap2.mandates.CartMandate` with a corresponding object that adheres to the
CartMandate schema.

The CartMandate Artifact MAY include a DataPart that contains a key of
`risk_data` and a value that contains implementation-defined risk signal data.

The following listing shows the JSON representation of a CartMandate Artifact.

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

### PaymentMandate Message

To provide a PaymentMandate to an agent, the client MUST construct a
PaymentMandate Message. A PaymentMandate Message is a profile of an A2A Message.

A PaymentMandate Message MUST contain a DataPart that has a key of
`ap2.mandates.PaymentMandate` and the value MUST be an object that adheres to
the `PaymentMandate` schema.

A PaymentMandate Message MAY contain other Parts.

The following listing shows a JSON rendering of a PaymentMandate Message.

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
