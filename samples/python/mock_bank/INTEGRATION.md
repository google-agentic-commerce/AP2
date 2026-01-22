# Payment API Integration Guide

Quick reference for integrating with the Mock Bank Server payment APIs.

**Base URL:** `<http://127.0.0.1:8004>`

---

## API Endpoints

### 1. Create Payment Transaction

`POST /payments`

Creates a new payment transaction. Returns a transaction ID that can be used to
check status.

#### Request Structure

All requests follow a 3-section format:

```json
{
    "transaction_data": {
        /* Required */
    },
    "customer_data": {
        /* Optional */
    },
    "payment_data": {
        /* Required - UPI_COLLECT or CARD */
    }
}
```

#### Field Requirements

| Section                      | Field           | Required | Notes                                |
| ---------------------------- | --------------- | -------- | ------------------------------------ |
| **transaction_data**         | txn_id          | ✓        | Unique transaction identifier        |
|                              | amount          | ✓        | Transaction amount (number)          |
|                              | currency        | -        | Defaults to "INR"                    |
|                              | description     | -        | Transaction description              |
| **customer_data**            | first_name      | ✓\*      | \*Required if customer_data provided |
|                              | last_name       | ✓\*      | \*Required if customer_data provided |
|                              | email           | -        | Customer email                       |
|                              | phone           | -        | Customer phone                       |
|                              | billing_address | -        | Billing address                      |
| **payment_data.UPI_COLLECT** | upi_id          | -        | UPI ID (e.g., user@psp)              |
| **payment_data.CARD**        | card_number     | ✓        | 16-digit card number                 |
|                              | card_holder     | ✓        | Name on card                         |
|                              | expiry_month    | ✓        | 01-12                                |
|                              | expiry_year     | ✓        | YYYY format                          |
|                              | cvv             | ✓        | CVV (validated, not stored)          |
|                              | card_category   | ✓        | CREDIT or DEBIT                      |
|                              | card_type       | -        | VISA, MASTERCARD, AMEX, RUPAY        |

---

### Example: UPI Payment

**Request:**

```bash
curl -X POST http://127.0.0.1:8004/payments \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_data": {
        "txn_id": "ORDER_12345",
        "amount": 499.00,
        "currency": "INR",
        "description": "Product purchase"
    },
    "customer_data": {
        "first_name": "Bugs",
        "last_name": "Kumar",
        "email": "bugs@example.com",
        "phone": "+91-9876543210"
    },
    "payment_data": {
        "UPI_COLLECT": {
            "upi_id": "bugs@upi"
        }
    }
}'
```

**Response:**

```json
{
    "success": true,
    "txn_id": "ORDER_12345"
}
```

---

### Example: CARD Payment

**Request:**

```bash
curl -X POST http://127.0.0.1:8004/payments \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_data": {
        "txn_id": "ORDER_12346",
        "amount": 1250.50,
        "currency": "INR"
    },
    "customer_data": {
        "first_name": "Daffy",
        "last_name": "Duck"
    },
    "payment_data": {
        "CARD": {
            "card_number": "4111111111111111",
            "card_holder": "Daffy Duck",
            "expiry_month": "12",
            "expiry_year": "2027",
            "cvv": "123",
            "card_category": "CREDIT",
            "card_type": "VISA"
        }
    }
}'
```

**Response:**

```json
{
    "success": true,
    "txn_id": "ORDER_12346"
}
```

**Security Note:** Card numbers are automatically masked in storage (XXXX XXXX
XXXX 1111). CVV is validated but never stored.

---

## 2. Get Payment Status

`GET /payments?id={txn_id}`

Retrieves the current status and details of a payment transaction.

**Note:** This endpoint is also used by the merchant payment processor agent's
`sync_payment` function to check the status of UPI_COLLECT payments and complete
them when they transition to SUCCESS or FAILURE state.

### Request

```bash
curl -X GET "http://127.0.0.1:8004/payments?id=ORDER_12345"
```

### Response Format

```json
{
    "success": true,
    "transaction_data": {
        "txn_id": "ORDER_12345",
        "amount": 499.0,
        "currency": "INR",
        "description": "Product purchase"
    },
    "customer_data": {
        "first_name": "Bugs",
        "last_name": "Kumar",
        "email": "bugs@example.com",
        "phone": "+91-9876543210"
    },
    "payment_data": {
        "UPI_COLLECT": {
            "upi_id": "bugs@upi"
        }
    },
    "status": "PENDING",
    "timestamp": "2026-01-09T20:30:15.123456"
}
```

### Transaction Status Values

- `PENDING` - Transaction awaiting action
- `SUCCESS` - Transaction completed successfully
- `FAILURE` - Transaction failed

---

## Error Responses

All errors return a JSON response with `success: false` and an `error` message:

```json
{
    "success": false,
    "error": "Error description"
}
```

### Common Errors

| HTTP Code | Error                                                   | Cause                                         |
| --------- | ------------------------------------------------------- | --------------------------------------------- |
| 400       | "transaction_data is required"                          | Missing transaction_data section              |
| 400       | "txn_id is required in transaction_data"                | Missing txn_id field                          |
| 400       | "amount is required in transaction_data"                | Missing amount field                          |
| 400       | "first_name is required in customer_data when provided" | customer_data provided but missing first_name |
| 400       | "card_number is required for CARD"                      | Card payment missing card_number              |
| 400       | "card_category must be CREDIT or DEBIT"                 | Invalid card_category value                   |
| 404       | "Transaction {txn_id} not found"                        | Transaction ID doesn't exist                  |
| 409       | "Transaction with ID {txn_id} already exists"           | Duplicate transaction ID                      |

---

## Payment Synchronization (for UPI_COLLECT)

The merchant payment processor agent includes a `sync_payment` function that
handles payment status synchronization, particularly useful for UPI_COLLECT
flows:

### How Payment Sync Works

1. **Already Completed:**
    - If a payment receipt already exists → Returns `{'status': 'success'}`

2. **Non-UPI_COLLECT Payments:**
    - If payment method is NOT `UPI_COLLECT` → Returns message: "Payment sync is
      not allowed for non-UPI_COLLECT payment methods."

3. **UPI_COLLECT Status Polling:**
    - For pending `UPI_COLLECT` payments, the function:
        - Extracts the `payment_mandate_id` (used as `txn_id` in mock bank)
        - Calls `GET /payments?id={txn_id}` to check current status
        - If status is `SUCCESS` or `FAILURE`:
            - Initiates the complete payment flow
            - Requests payment credentials from credentials provider
            - Creates and sends payment receipt
            - Returns `{'status': 'success'}`
        - If status is still `PENDING`:
            - Returns message: "Payment is still pending at the bank"

### Integration with UPI Flow

```text
1. User initiates UPI_COLLECT payment
   ↓
2. Payment processor creates transaction at mock bank (POST /payments)
   ↓
3. User approves payment in their UPI app (simulated via web UI)
   ↓
4. Mock bank updates transaction status to SUCCESS
   ↓
5. Merchant calls sync_payment to check status (GET /payments?id={txn_id})
   ↓
6. Sync detects SUCCESS status and completes payment processing
```

### Example: Sync Payment Flow

#### Step 1: Check status of pending UPI payment

```bash
# The payment processor agent will call:
curl -X GET "http://127.0.0.1:8004/payments?id=PAYMENT_MANDATE_123"
```

**Response (Still Pending):**

```json
{
    "success": true,
    "transaction_data": {
        "txn_id": "PAYMENT_MANDATE_123",
        "amount": 500.0,
        "currency": "INR"
    },
    "payment_data": {
        "UPI_COLLECT": {}
    },
    "status": "PENDING",
    "timestamp": "2026-01-10T07:30:00.000000"
}
```

**Response (After User Approval):**

```json
{
    "success": true,
    "transaction_data": {
        "txn_id": "PAYMENT_MANDATE_123",
        "amount": 500.0,
        "currency": "INR"
    },
    "payment_data": {
        "UPI_COLLECT": {}
    },
    "status": "SUCCESS",
    "timestamp": "2026-01-10T07:30:00.000000"
}
```

When the status is `SUCCESS`, the sync function automatically triggers payment
completion.

---

## Quick Integration Steps

### 1. **Create a Payment**

- Generate a unique `txn_id`
- Collect payment details from user
- Send POST request to `/payments`
- Store returned `txn_id` for status checks

### 2. **Check Payment Status**

- Use the `txn_id` from create response
- Poll GET `/payments?id={txn_id}` endpoint
- Check `status` field in response
- Handle SUCCESS/FAILURE accordingly

### 3. **Sync UPI_COLLECT Payments (Optional)**

- For UPI_COLLECT payments, use the merchant payment processor's `sync_payment`
  function
- The function automatically handles status checking and payment completion
- No manual polling needed - the agent manages the full lifecycle

### 4. **Handle Responses**

- Always check `success` field
- On error, display `error` message to user
- On success, proceed with order fulfillment

---

## Code Examples

### Python Example

```python
import requests

# Create Payment
payload = {
    "transaction_data": {
        "txn_id": "ORDER_001",
        "amount": 100.00
    },
    "payment_data": {
        "UPI_COLLECT": {
            "upi_id": "user@psp"
        }
    }
}

response = requests.post(
    "http://127.0.0.1:8004/payments",
    json=payload
)
data = response.json()

if data["success"]:
    txn_id = data["txn_id"]

    # Check Status
    status_response = requests.get(
        f"http://127.0.0.1:8004/payments?id={txn_id}"
    )
    status_data = status_response.json()
    print(f"Status: {status_data['status']}")
```

### JavaScript Example

```javascript
// Create Payment
const payload = {
    transaction_data: {
        txn_id: "ORDER_001",
        amount: 100.0,
    },
    payment_data: {
        UPI_COLLECT: {
            upi_id: "user@psp",
        },
    },
};

fetch("http://127.0.0.1:8004/payments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
})
    .then((res) => res.json())
    .then((data) => {
        if (data.success) {
            const txnId = data.txn_id;

            // Check Status
            fetch(`http://127.0.0.1:8004/payments?id=${txnId}`)
                .then((res) => res.json())
                .then((statusData) => {
                    console.log(`Status: ${statusData.status}`);
                });
        }
    });
```

---

## Testing Tips

1. **Use unique transaction IDs** - Duplicate IDs will return a 409 error
2. **Test both payment methods** - UPI and CARD have different required fields
3. **Test with/without customer data** - customer_data is optional
4. **Verify card masking** - Card numbers should be masked in GET responses
5. **Check error handling** - Send invalid requests to test error responses

---

## Support

For detailed documentation, see [README.md](./README.md)

For UI-based testing, visit: <http://127.0.0.1:8004/>
