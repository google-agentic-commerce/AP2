# AI Shopping Concierge - API Reference

Complete API documentation for the AI Shopping Concierge platform.

## Base URL

- **Development**: `http://localhost:8000`
- **Staging**: `https://staging.ai-shopping-concierge.com`
- **Production**: `https://api.ai-shopping-concierge.com`

## Authentication

Most endpoints require API key authentication:

```http
Authorization: Bearer YOUR_API_KEY
```

## Core Endpoints

### Health Check

Check application health and status.

**GET** `/health`

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-09-22T10:30:00Z",
  "services": {
    "database": "connected",
    "redis": "connected",
    "whatsapp": "active",
    "ai_engine": "ready"
  },
  "version": "1.0.0"
}
```

## WhatsApp Integration

### Webhook Verification

**GET** `/webhook/whatsapp`

Query Parameters:
- `hub.mode`: Subscription mode (subscribe)
- `hub.challenge`: Challenge string to echo back
- `hub.verify_token`: Verification token

### Message Processing

**POST** `/webhook/whatsapp`

Processes incoming WhatsApp messages.

**Request Body:**
```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
    "changes": [{
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {
          "display_phone_number": "PHONE_NUMBER",
          "phone_number_id": "PHONE_NUMBER_ID"
        },
        "messages": [{
          "from": "CUSTOMER_PHONE_NUMBER",
          "id": "MESSAGE_ID",
          "timestamp": "TIMESTAMP",
          "text": {
            "body": "MESSAGE_TEXT"
          },
          "type": "text"
        }]
      },
      "field": "messages"
    }]
  }]
}
```

## Shopping Agent API

### Start Chat Session

**POST** `/api/v1/chat/session`

Create a new shopping session.

**Request:**
```json
{
  "customer_id": "customer_123",
  "channel": "whatsapp",
  "phone_number": "+1234567890"
}
```

**Response:**
```json
{
  "session_id": "session_abc123",
  "status": "active",
  "created_at": "2025-09-22T10:30:00Z"
}
```

### Send Message

**POST** `/api/v1/chat/message`

Send a message to the AI shopping assistant.

**Request:**
```json
{
  "session_id": "session_abc123",
  "message": "I'm looking for a laptop under $1000",
  "message_type": "text"
}
```

**Response:**
```json
{
  "response": "I'd be happy to help you find a laptop under $1000! I found several great options...",
  "products": [
    {
      "id": "laptop_001",
      "name": "Dell Inspiron 15",
      "price": 899.99,
      "currency": "USD",
      "image_url": "https://...",
      "description": "15.6\" laptop with Intel i5 processor"
    }
  ],
  "actions": [
    {
      "type": "quick_reply",
      "title": "View Details",
      "payload": "view_product_laptop_001"
    },
    {
      "type": "quick_reply", 
      "title": "Compare Options",
      "payload": "compare_laptops"
    }
  ]
}
```

### Get Session History

**GET** `/api/v1/chat/session/{session_id}/history`

**Response:**
```json
{
  "session_id": "session_abc123",
  "messages": [
    {
      "timestamp": "2025-09-22T10:30:00Z",
      "sender": "customer",
      "message": "I'm looking for a laptop",
      "type": "text"
    },
    {
      "timestamp": "2025-09-22T10:30:05Z", 
      "sender": "ai",
      "message": "I'd be happy to help you find a laptop!",
      "type": "text",
      "products": [...]
    }
  ]
}
```

## Product Curation API

### Get Recommendations

**POST** `/api/v1/curation/recommend`

Get AI-powered product recommendations.

**Request:**
```json
{
  "customer_id": "customer_123",
  "query": "gaming laptop",
  "budget_min": 800,
  "budget_max": 1500,
  "preferences": {
    "brand": ["ASUS", "MSI"],
    "screen_size": "15-17 inches",
    "use_case": "gaming"
  },
  "limit": 10
}
```

**Response:**
```json
{
  "recommendations": [
    {
      "product_id": "laptop_gaming_001",
      "name": "ASUS ROG Strix G15",
      "price": 1299.99,
      "currency": "USD",
      "confidence_score": 0.95,
      "match_reasons": [
        "Perfect for gaming",
        "Within budget range",
        "Preferred brand"
      ],
      "specifications": {
        "processor": "AMD Ryzen 7",
        "graphics": "NVIDIA RTX 3060",
        "ram": "16GB",
        "storage": "512GB SSD"
      }
    }
  ],
  "total_results": 25,
  "search_metadata": {
    "query_understanding": "Customer looking for high-performance gaming laptop",
    "filters_applied": ["price_range", "brand_preference", "category"]
  }
}
```

### Create Product Bundle

**POST** `/api/v1/curation/bundle`

Create smart product bundles.

**Request:**
```json
{
  "primary_product_id": "laptop_gaming_001",
  "customer_profile": {
    "interests": ["gaming", "productivity"],
    "budget_total": 1800
  },
  "bundle_type": "complementary"
}
```

**Response:**
```json
{
  "bundle_id": "bundle_abc123",
  "name": "Gaming Setup Bundle",
  "products": [
    {
      "id": "laptop_gaming_001",
      "name": "ASUS ROG Strix G15",
      "price": 1299.99,
      "role": "primary"
    },
    {
      "id": "mouse_gaming_001", 
      "name": "Logitech G Pro X",
      "price": 149.99,
      "role": "accessory"
    },
    {
      "id": "headset_gaming_001",
      "name": "SteelSeries Arctis 7",
      "price": 179.99,
      "role": "accessory"
    }
  ],
  "total_price": 1629.97,
  "bundle_discount": 50.00,
  "final_price": 1579.97,
  "savings": 99.99
}
```

## Negotiation Engine API

### Initiate Negotiation

**POST** `/api/v1/negotiation/start`

Start price negotiation for a product or bundle.

**Request:**
```json
{
  "session_id": "session_abc123",
  "product_id": "laptop_gaming_001",
  "customer_signal": "price_concern",
  "context": "Customer hesitated at checkout due to price"
}
```

**Response:**
```json
{
  "negotiation_id": "neg_xyz789",
  "status": "active",
  "offers": [
    {
      "type": "discount",
      "description": "10% off for today only",
      "original_price": 1299.99,
      "discounted_price": 1169.99,
      "savings": 130.00,
      "expires_at": "2025-09-22T23:59:59Z"
    },
    {
      "type": "bundle_upgrade",
      "description": "Add gaming mouse for just $50 more",
      "additional_cost": 50.00,
      "additional_value": 149.99,
      "savings": 99.99
    }
  ]
}
```

### Respond to Offer

**POST** `/api/v1/negotiation/{negotiation_id}/respond`

Customer response to negotiation offer.

**Request:**
```json
{
  "response": "accept",
  "offer_id": "offer_discount_001"
}
```

**Response:**
```json
{
  "status": "accepted",
  "final_offer": {
    "product_id": "laptop_gaming_001",
    "final_price": 1169.99,
    "discount_applied": 130.00,
    "terms": "Valid until 2025-09-22T23:59:59Z"
  },
  "next_step": "proceed_to_checkout"
}
```

## Checkout & Payment API

### Start Checkout

**POST** `/api/v1/checkout/start`

Initialize checkout process with automatic payment handling.

**Request:**
```json
{
  "session_id": "session_abc123",
  "items": [
    {
      "product_id": "laptop_gaming_001",
      "quantity": 1,
      "price": 1169.99,
      "applied_discounts": ["negotiation_discount"]
    }
  ],
  "customer_details": {
    "email": "customer@example.com",
    "phone": "+1234567890"
  }
}
```

**Response:**
```json
{
  "checkout_id": "checkout_def456",
  "session_id": "session_abc123",
  "status": "initiated",
  "currency_detected": "USD",
  "customer_location": "US",
  "payment_options": [
    {
      "method": "ap2",
      "display_name": "AP2 Pay",
      "fees": "1.5%",
      "recommended": true
    },
    {
      "method": "stripe",
      "display_name": "Credit Card",
      "fees": "2.9%"
    }
  ],
  "totals": {
    "subtotal": 1169.99,
    "tax": 87.75,
    "total": 1257.74,
    "currency": "USD"
  }
}
```

### Process Payment

**POST** `/api/v1/checkout/{checkout_id}/payment`

Process payment with automatic currency conversion.

**Request:**
```json
{
  "payment_method": "ap2",
  "currency_preference": "EUR",
  "billing_address": {
    "country": "DE",
    "postal_code": "10115",
    "city": "Berlin"
  }
}
```

**Response:**
```json
{
  "payment_id": "pay_ghi789",
  "status": "processing",
  "currency_conversion": {
    "original_amount": 1257.74,
    "original_currency": "USD",
    "converted_amount": 1068.58,
    "target_currency": "EUR",
    "exchange_rate": 0.85,
    "conversion_fee": 5.34
  },
  "estimated_settlement": "2025-09-23T10:30:00Z"
}
```

### Check Payment Status

**GET** `/api/v1/payment/{payment_id}/status`

**Response:**
```json
{
  "payment_id": "pay_ghi789",
  "status": "completed",
  "authorization_id": "auth_123",
  "capture_id": "cap_456", 
  "settlement_id": "settle_789",
  "timeline": {
    "initiated_at": "2025-09-22T10:30:00Z",
    "authorized_at": "2025-09-22T10:30:02Z",
    "captured_at": "2025-09-22T10:30:05Z",
    "settled_at": "2025-09-23T10:30:00Z"
  },
  "fees": {
    "processing_fee": 18.89,
    "currency_conversion_fee": 5.34,
    "total_fees": 24.23
  }
}
```

## Analytics API

### Get Performance Metrics

**GET** `/api/v1/analytics/performance`

Query Parameters:
- `start_date`: Start date (ISO 8601)
- `end_date`: End date (ISO 8601)
- `granularity`: hour, day, week, month

**Response:**
```json
{
  "period": {
    "start": "2025-09-15T00:00:00Z",
    "end": "2025-09-22T00:00:00Z"
  },
  "metrics": {
    "total_conversations": 1250,
    "conversion_rate": 0.23,
    "average_order_value": 287.50,
    "total_revenue": 82512.50,
    "customer_satisfaction": 4.7,
    "response_time_avg": 1.2
  },
  "top_products": [
    {
      "product_id": "laptop_gaming_001",
      "name": "ASUS ROG Strix G15",
      "sales_count": 45,
      "revenue": 58499.55
    }
  ]
}
```

### Get Conversation Analytics

**GET** `/api/v1/analytics/conversations`

**Response:**
```json
{
  "conversation_metrics": {
    "total_messages": 12450,
    "avg_messages_per_session": 8.5,
    "most_common_intents": [
      {
        "intent": "product_search",
        "count": 3200,
        "percentage": 25.7
      },
      {
        "intent": "price_inquiry", 
        "count": 2100,
        "percentage": 16.9
      }
    ],
    "abandonment_points": [
      {
        "stage": "payment_method_selection",
        "rate": 0.15
      },
      {
        "stage": "shipping_details",
        "rate": 0.08
      }
    ]
  }
}
```

## Error Handling

All endpoints return consistent error responses:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "The request is missing required parameters",
    "details": {
      "missing_fields": ["customer_id", "message"]
    },
    "request_id": "req_abc123"
  }
}
```

### Error Codes

- `INVALID_REQUEST` (400): Malformed request
- `UNAUTHORIZED` (401): Invalid API key
- `FORBIDDEN` (403): Insufficient permissions  
- `NOT_FOUND` (404): Resource not found
- `RATE_LIMITED` (429): Too many requests
- `INTERNAL_ERROR` (500): Server error
- `SERVICE_UNAVAILABLE` (503): Service temporarily down

## Rate Limits

- **Development**: 100 requests/minute
- **Production**: 1000 requests/minute
- **Webhook**: No limit (verified requests only)

Rate limit headers:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1632312000
```

## SDKs

### JavaScript/TypeScript

```bash
npm install ai-shopping-concierge-sdk
```

```javascript
import { AIShoppingConcierge } from 'ai-shopping-concierge-sdk';

const client = new AIShoppingConcierge({
  apiKey: 'your-api-key',
  baseUrl: 'https://api.ai-shopping-concierge.com'
});

const session = await client.chat.createSession({
  customerId: 'customer_123',
  channel: 'web'
});

const response = await client.chat.sendMessage({
  sessionId: session.session_id,
  message: 'I need a laptop for work'
});
```

### Python

```bash
pip install ai-shopping-concierge-sdk
```

```python
from ai_shopping_concierge import Client

client = Client(
    api_key='your-api-key',
    base_url='https://api.ai-shopping-concierge.com'
)

session = client.chat.create_session(
    customer_id='customer_123',
    channel='web'
)

response = client.chat.send_message(
    session_id=session.session_id,
    message='I need a laptop for work'
)
```

## Webhooks

### Conversation Events

Register webhooks to receive real-time conversation events:

**POST** `/api/v1/webhooks/register`

```json
{
  "url": "https://your-app.com/webhook/conversations",
  "events": ["message.sent", "session.started", "purchase.completed"],
  "secret": "your-webhook-secret"
}
```

**Webhook Payload:**
```json
{
  "event": "purchase.completed",
  "timestamp": "2025-09-22T10:30:00Z",
  "data": {
    "session_id": "session_abc123",
    "customer_id": "customer_123",
    "order_id": "order_def456",
    "total_amount": 1257.74,
    "currency": "USD"
  },
  "signature": "sha256=..."
}
```

For complete integration examples and advanced use cases, see our [GitHub repository](https://github.com/your-username/ai-shopping-concierge-ap2).