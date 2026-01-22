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

"""In-memory storage for transactions."""

from datetime import datetime
from typing import Dict, Optional
from threading import Lock


class TransactionStorage:
    """Thread-safe in-memory storage for transactions."""

    def __init__(self):
        self._transactions: Dict[str, dict] = {}
        self._lock = Lock()

    def create_transaction(
        self,
        txn_id: str,
        amount: float,
        currency: str = "INR",
        description: Optional[str] = None,
        payment_method: str = "UPI_COLLECT",
        customer_data: Optional[dict] = None,
        **payment_details
    ) -> dict:
        """Create a new transaction.

        Args:
            txn_id: Unique transaction identifier provided by client
            amount: Transaction amount
            currency: Currency code (default: INR)
            description: Optional transaction description
            payment_method: Payment method type (UPI_COLLECT, CARD, etc.)
            customer_data: Optional customer information
            **payment_details: Additional payment method specific details

        Returns:
            The created transaction dict

        Raises:
            ValueError: If transaction with txn_id already exists
        """
        with self._lock:
            if txn_id in self._transactions:
                raise ValueError(f"Transaction with ID {txn_id} already exists")

            transaction = {
                "txn_id": txn_id,
                "amount": amount,
                "currency": currency,
                "description": description or "",
                "status": "PENDING",
                "timestamp": datetime.now().isoformat(),
                "payment_method": payment_method,
                "customer_data": customer_data or {},
                **payment_details
            }
            self._transactions[txn_id] = transaction
            return transaction.copy()

    def get_transaction(self, txn_id: str) -> Optional[dict]:
        """Get transaction by ID.

        Args:
            txn_id: Transaction ID to retrieve

        Returns:
            Transaction dict or None if not found
        """
        with self._lock:
            transaction = self._transactions.get(txn_id)
            return transaction.copy() if transaction else None

    def update_status(self, txn_id: str, status: str) -> Optional[dict]:
        """Update transaction status.

        Args:
            txn_id: Transaction ID to update
            status: New status ("SUCCESS" or "FAILURE")

        Returns:
            Updated transaction dict or None if not found

        Raises:
            ValueError: If status is invalid
        """
        if status not in ["SUCCESS", "FAILURE"]:
            raise ValueError(f"Invalid status: {status}. Must be SUCCESS or FAILURE")

        with self._lock:
            if txn_id not in self._transactions:
                return None

            self._transactions[txn_id]["status"] = status
            return self._transactions[txn_id].copy()

    def get_all_transactions(self) -> list:
        """Get all transactions.

        Returns:
            List of all transaction dicts
        """
        with self._lock:
            return [txn.copy() for txn in self._transactions.values()]
