# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Mock Bank Server with payment endpoints."""

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from .storage import TransactionStorage

app = Flask(__name__)
CORS(app)

storage = TransactionStorage()


@app.route("/payments", methods=["POST"])
def create_payment():
    """Create a new payment transaction.

    Expected JSON body:
        {
            "transaction_data": {
                "txn_id": "TXN123",
                "amount": 100.50,
                "currency": "INR",
                "description": "Optional"
            },
            "customer_data": {  // Optional section
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "phone": "+91-1234567890",
                "billing_address": "123 Main St"
            },
            "payment_data": {
                "UPI_COLLECT": {"upi_id": "user@psp"}
                // OR
                "CARD": {
                    "card_number": "4111111111111234",
                    "card_holder": "John Doe",
                    "expiry_month": "12",
                    "expiry_year": "2027",
                    "cvv": "123",
                    "card_category": "CREDIT",
                    "card_type": "VISA"
                }
            }
        }

    Returns:
        JSON response with success status and txn_id
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        transaction_data = data.get("transaction_data")
        if not transaction_data:
            return jsonify({"success": False, "error": "transaction_data is required"}), 400

        txn_id = transaction_data.get("txn_id")
        amount = transaction_data.get("amount")
        currency = transaction_data.get("currency", "INR")
        description = transaction_data.get("description", "")

        if not txn_id:
            return jsonify({"success": False, "error": "txn_id is required in transaction_data"}), 400
        if amount is None:
            return jsonify({"success": False, "error": "amount is required in transaction_data"}), 400

        customer_data = data.get("customer_data", {})
        if customer_data:
            if not customer_data.get("first_name"):
                return jsonify({"success": False, "error": "first_name is required in customer_data when provided"}), 400
            if not customer_data.get("last_name"):
                return jsonify({"success": False, "error": "last_name is required in customer_data when provided"}), 400

        payment_data = data.get("payment_data")
        if not payment_data:
            return jsonify({"success": False, "error": "payment_data is required"}), 400

        payment_methods = list(payment_data.keys())
        if not payment_methods:
            return jsonify({"success": False, "error": "payment_data must contain a payment method"}), 400

        payment_method = payment_methods[0]
        method_data = payment_data[payment_method]

        payment_details = {}

        if payment_method == "UPI_COLLECT":
            # Ideally upi_id would be required, but making it optional for demo purposes
            upi_id = method_data.get("upi_id", "")
            payment_details["upi_id"] = upi_id

        elif payment_method == "CARD":
            card_number = method_data.get("card_number")
            card_holder = method_data.get("card_holder")
            expiry_month = method_data.get("expiry_month")
            expiry_year = method_data.get("expiry_year")
            cvv = method_data.get("cvv")
            card_category = method_data.get("card_category")

            if not card_number:
                return jsonify({"success": False, "error": "card_number is required for CARD"}), 400
            if not card_holder:
                return jsonify({"success": False, "error": "card_holder is required for CARD"}), 400
            if not expiry_month:
                return jsonify({"success": False, "error": "expiry_month is required for CARD"}), 400
            if not expiry_year:
                return jsonify({"success": False, "error": "expiry_year is required for CARD"}), 400
            if not cvv:
                return jsonify({"success": False, "error": "cvv is required for CARD"}), 400
            if not card_category:
                return jsonify({"success": False, "error": "card_category is required for CARD"}), 400

            if card_category not in ["CREDIT", "DEBIT"]:
                return jsonify({"success": False, "error": "card_category must be CREDIT or DEBIT"}), 400

            masked_card_number = "XXXX XXXX XXXX " + card_number[-4:]

            payment_details["card_number"] = masked_card_number
            payment_details["card_holder"] = card_holder
            payment_details["expiry_month"] = expiry_month
            payment_details["expiry_year"] = expiry_year
            payment_details["card_category"] = card_category

            if method_data.get("card_type"):
                payment_details["card_type"] = method_data["card_type"]

        else:
            return jsonify({
                "success": False,
                "error": f"Unsupported payment method: {payment_method}. Supported: UPI_COLLECT, CARD"
            }), 400

        transaction = storage.create_transaction(
            txn_id=txn_id,
            amount=amount,
            currency=currency,
            description=description,
            payment_method=payment_method,
            customer_data=customer_data,
            **payment_details
        )

        return jsonify({"success": True, "txn_id": transaction["txn_id"]}), 201

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/payments", methods=["GET"])
def get_payment():
    """Get transaction status by ID.

    Query parameter:
        id: Transaction ID

    Returns:
        JSON response with transaction details in new 3-section format
    """
    try:
        txn_id = request.args.get("id")

        if not txn_id:
            return jsonify({"success": False, "error": "id query parameter is required"}), 400

        transaction = storage.get_transaction(txn_id)

        if not transaction:
            return jsonify({"success": False, "error": f"Transaction {txn_id} not found"}), 404

        payment_method = transaction.get("payment_method", "UPI_COLLECT")

        transaction_data = {
            "txn_id": transaction["txn_id"],
            "amount": transaction["amount"],
            "currency": transaction["currency"],
            "description": transaction.get("description", "")
        }

        customer_data = transaction.get("customer_data", {})

        payment_specific = {}
        if payment_method == "UPI_COLLECT":
            payment_specific["upi_id"] = transaction.get("upi_id", "")
        elif payment_method == "CARD":
            payment_specific["card_number"] = transaction.get("card_number", "")
            payment_specific["card_holder"] = transaction.get("card_holder", "")
            payment_specific["expiry_month"] = transaction.get("expiry_month", "")
            payment_specific["expiry_year"] = transaction.get("expiry_year", "")
            payment_specific["card_category"] = transaction.get("card_category", "")
            if transaction.get("card_type"):
                payment_specific["card_type"] = transaction["card_type"]

        response = {
            "success": True,
            "transaction_data": transaction_data,
            "customer_data": customer_data,
            "payment_data": {
                payment_method: payment_specific
            },
            "status": transaction["status"],
            "timestamp": transaction["timestamp"]
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/", methods=["GET"])
def home():
    """Render the home page with all transactions grouped by payment method."""
    all_transactions = storage.get_all_transactions()

    grouped_transactions = {}
    for txn in all_transactions:
        payment_method = txn.get("payment_method", "UPI_COLLECT")
        if payment_method not in grouped_transactions:
            grouped_transactions[payment_method] = []
        grouped_transactions[payment_method].append(txn)

    return render_template("home.html", grouped_transactions=grouped_transactions)


@app.route("/action/<txn_id>", methods=["PUT"])
def update_transaction_status(txn_id):
    """Update transaction status.

    Path parameter:
        txn_id: Transaction ID

    Expected JSON body:
        {
            "status": "SUCCESS" or "FAILURE"
        }

    Returns:
        JSON response with updated transaction
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Request body is required"}), 400

        status = data.get("status")

        if not status:
            return jsonify({"success": False, "error": "status is required"}), 400

        transaction = storage.update_status(txn_id, status)

        if not transaction:
            return jsonify({"success": False, "error": f"Transaction {txn_id} not found"}), 404

        return jsonify({
            "success": True,
            "txn_id": transaction["txn_id"],
            "new_status": transaction["status"]
        }), 200

    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    print("Starting Mock Bank Server on http://127.0.0.1:8004")
    print("Endpoints:")
    print("  POST   /payments          - Create UPI collect transaction")
    print("  GET    /payments?id=X     - Get transaction status")
    print("  GET    /                  - View all transactions (web UI)")
    print("  PUT    /action/<txn_id>   - Update transaction status")
    print()
    app.run(host="127.0.0.1", port=8004, debug=True)
