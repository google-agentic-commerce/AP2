# Mock Bank Server - Payment Transactions

A simple mock bank server with payment transaction management capabilities
supporting multiple payment methods.

## Features

- In-memory transaction storage
- Support for multiple payment methods (UPI, CARD)
- RESTful API endpoints for payment transactions
- Web-based UI for transaction management
- Customer data tracking (optional)
- Card number masking for security
- Support for SUCCESS/FAILURE transaction actions

## Running the Server

```bash
cd samples/python/mock_bank
python __main__.py
```

The server will start on **<http://127.0.0.1:8004>**

## API Endpoints

### 1. Create Payment Transaction

**POST** `/payments`

Create a new payment transaction with client-provided transaction ID.

**Request Structure:**

```json
{
    "transaction_data": {
        "txn_id": "TXN123",
        "amount": 100.50,
        "currency": "INR",
        "description": "Payment description"
    },
    "customer_data": {  // OPTIONAL
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "phone": "+91-9876543210",
        "billing_address": "123 Main St"
    },
    "payment_data": {
        "UPI_COLLECT": {...} // OR "CARD": {...}
    }
}
```

#### Field Requirements

**transaction_data** (Required):

- `txn_id` ✓ Required - Unique transaction identifier
- `amount` ✓ Required - Transaction amount
- `currency` - Optional (defaults to "INR")
- `description` - Optional

**customer_data** (Optional Section):

- `first_name` ✓ Required if customer_data is provided
- `last_name` ✓ Required if customer_data is provided
- `email` - Optional
- `phone` - Optional
- `billing_address` - Optional

---

### UPI_COLLECT Payment Method

**payment_data.UPI_COLLECT** (Optional fields):

- `upi_id` - UPI ID (e.g., user@psp)

#### Example - UPI Request (Minimal)

```bash
curl -X POST http://127.0.0.1:8004/payments \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_data": {
        "txn_id": "TXN001",
        "amount": 150.50
    },
    "payment_data": {
        "UPI_COLLECT": {
            "upi_id": "user@psp"
        }
    }
}'
```

#### Example - UPI Request (Full with Customer Data)

```bash
curl -X POST http://127.0.0.1:8004/payments \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_data": {
        "txn_id": "TXN001",
        "amount": 150.50,
        "currency": "INR",
        "description": "Order payment"
    },
    "customer_data": {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com"
    },
    "payment_data": {
        "UPI_COLLECT": {
            "upi_id": "john.doe@upi"
        }
    }
}'
```

---

### CARD Payment Method

**payment_data.CARD** (Required fields):

- `card_number` ✓ Required - 16-digit card number
- `card_holder` ✓ Required - Name on card
- `expiry_month` ✓ Required - Month (01-12)
- `expiry_year` ✓ Required - Year (YYYY)
- `cvv` ✓ Required - CVV/CVC code (validated but NOT stored)
- `card_category` ✓ Required - CREDIT or DEBIT

**payment_data.CARD** (Optional fields):

- `card_type` - Card brand (VISA, MASTERCARD, AMEX, RUPAY)

#### Example - CARD Request

```bash
curl -X POST http://127.0.0.1:8004/payments \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_data": {
        "txn_id": "TXN002",
        "amount": 250.00,
        "currency": "INR",
        "description": "Online purchase"
    },
    "customer_data": {
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane@example.com",
        "phone": "+91-9876543210"
    },
    "payment_data": {
        "CARD": {
            "card_number": "4111111111111234",
            "card_holder": "Jane Smith",
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
    "txn_id": "TXN002"
}
```

**Security Notes:**

- Card numbers are automatically masked (only last 4 digits shown)
- CVV is validated but NOT stored
- Masked format: `XXXX XXXX XXXX 1234`

---

### 2. Get Transaction Status

**GET** `/payments?id=<txn_id>`

Retrieve the status and details of a specific transaction.

**Query Parameters:**

- `id` - Transaction ID

**Response Format:**

```json
{
  "success": true,
  "transaction_data": {
    "txn_id": "TXN123",
    "amount": 100.50,
    "currency": "INR",
    "description": "Payment description"
  },
  "customer_data": {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com"
  },
  "payment_data": {
    "UPI_COLLECT": {
      "upi_id": "john.doe@upi"
    }
    // OR for CARD
    "CARD": {
      "card_number": "XXXX XXXX XXXX 1234",
      "card_holder": "Jane Smith",
      "expiry_month": "12",
      "expiry_year": "2027",
      "card_category": "CREDIT",
      "card_type": "VISA"
    }
  },
  "status": "PENDING",
  "timestamp": "2026-01-09T20:30:00.123456"
}
```

**Example:**

```bash
curl -X GET "http://127.0.0.1:8004/payments?id=TXN001"
```

---

### 3. View All Transactions (Web UI)

**GET** `/`

Opens a web-based interface showing all transactions grouped by payment method.

**Features:**

- Transactions grouped by payment method (UPI, CARD, etc.)
- Card tiles showing:
    - Customer name (if provided)
    - Payment method-specific details
    - Masked card number for CARD
    - Card type and category badges (CREDIT/DEBIT)
    - Expiry date for cards
- SUCCESS/FAILURE action buttons for pending transactions
- Real-time transaction statistics
- Auto-refresh capability

**Example:** Open in browser: <http://127.0.0.1:8004/>

---

### 4. Update Transaction Status

**PUT** `/action/<txn_id>`

Update the status of a transaction to SUCCESS or FAILURE.

**Request Body:**

```json
{
    "status": "SUCCESS"
}
```

**Valid values:** "SUCCESS" or "FAILURE"

**Response:**

```json
{
    "success": true,
    "txn_id": "TXN123",
    "new_status": "SUCCESS"
}
```

**Example:**

```bash
curl -X PUT http://127.0.0.1:8004/action/TXN001 \
  -H "Content-Type: application/json" \
  -d '{"status": "SUCCESS"}'
```

---

## Transaction States

- **PENDING**: Transaction is awaiting action
- **SUCCESS**: Transaction completed successfully
- **FAILURE**: Transaction failed

## Supported Payment Methods

### UPI_COLLECT

- Display: UPI ID with mobile icon 📱
- Optional: upi_id

### CARD

- Display: Masked card number, type badge, category badge (CREDIT/DEBIT), expiry
  date
- Required: card_number, card_holder, expiry_month, expiry_year, cvv,
  card_category
- Optional: card_type

## Project Structure

```text
mock_bank/
├── __main__.py          # Flask server with API endpoints
├── storage.py           # In-memory transaction storage
├── templates/
│   └── home.html        # Web UI for transaction management
└── README.md            # This file
```

## Complete Testing Workflow

### 1. Start the server

```bash
python __main__.py
```

### 2. Create a UPI transaction

```bash
curl -X POST http://127.0.0.1:8004/payments \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_data": {"txn_id": "UPI001", "amount": 100},
    "customer_data": {"first_name": "Alice", "last_name": "Wonder"},
    "payment_data": {"UPI_COLLECT": {"upi_id": "alice@upi"}}
}'
```

### 3. Create a CARD transaction

```bash
curl -X POST http://127.0.0.1:8004/payments \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_data": {"txn_id": "CARD001", "amount": 250, "currency": "INR"},
    "customer_data": {"first_name": "Bob", "last_name": "Builder"},
    "payment_data": {
        "CARD": {
            "card_number": "5555555555554444",
            "card_holder": "Bob Builder",
            "expiry_month": "06",
            "expiry_year": "2028",
            "cvv": "456",
            "card_category": "DEBIT",
            "card_type": "MASTERCARD"
        }
    }
}'
```

### 4. Check transaction status

```bash
curl -X GET "http://127.0.0.1:8004/payments?id=UPI001"
curl -X GET "http://127.0.0.1:8004/payments?id=CARD001"
```

### 5. Open web UI

- Navigate to <http://127.0.0.1:8004/> in your browser
- View transactions grouped by payment method
- See customer names, payment details, and badges
- Click APPROVE or DECLINE for pending transactions

### 6. Update transaction via API

```bash
curl -X PUT http://127.0.0.1:8004/action/UPI001 \
  -H "Content-Type: application/json" \
  -d '{"status": "SUCCESS"}'
```

## Notes

- All transactions are stored in memory and will be lost when the server
  restarts
- The server runs in debug mode by default
- CORS is enabled for local development
- Transaction IDs must be unique (duplicates will return a 409 error)
- Card numbers are automatically masked for security
- CVV is validated but never stored
- Customer data is optional but recommended for better tracking
