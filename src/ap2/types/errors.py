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

"""Standard error and failure response types for the Agent Payments Protocol.

These types define a consistent structure for communicating failure states
between agents, enabling predictable error handling and recovery flows.

Failure scenarios addressed:
- Mandate expiration during multi-step flows
- Price drift beyond mandate constraints
- Payment decline / PSP rejection
- Partial cart rejection (out of stock, unavailable items)
- Validation errors

Usage:
    from ap2.types.errors import FailureResponse, FailureCategory, RecoveryAction

    failure = FailureResponse(
        category=FailureCategory.PRICE_DRIFT,
        message="Final price exceeds original quote by 15%",
        recovery_action=RecoveryAction.USER_CONFIRMATION_REQUIRED,
        original_value={"amount": 100.00, "currency": "USD"},
        actual_value={"amount": 115.00, "currency": "USD"}
    )
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel
from pydantic import Field


FAILURE_RESPONSE_DATA_KEY = "ap2.errors.FailureResponse"


class FailureCategory(str, Enum):
    """Categories of failures that can occur in agent payment flows.

    These categories help agents quickly identify the type of failure and
    determine appropriate recovery strategies.
    """

    MANDATE_EXPIRED = "MANDATE_EXPIRED"
    """The intent or cart mandate has expired before transaction completion."""

    PRICE_DRIFT = "PRICE_DRIFT"
    """The final price exceeds the original quote or mandate price constraints."""

    PAYMENT_DECLINED = "PAYMENT_DECLINED"
    """The payment was declined by the PSP, issuer, or payment network."""

    CART_MODIFIED = "CART_MODIFIED"
    """The cart contents were modified (items unavailable, quantities changed)."""

    MERCHANT_REJECTION = "MERCHANT_REJECTION"
    """The merchant rejected the order (policy violation, risk, etc.)."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    """The request failed validation (missing fields, invalid format, etc.)."""

    CONSTRAINT_VIOLATED = "CONSTRAINT_VIOLATED"
    """A mandate constraint was violated (merchant not allowed, SKU not permitted, etc.)."""


class RecoveryAction(str, Enum):
    """Recommended recovery actions for failure scenarios.

    These actions guide the calling agent on how to proceed after a failure.
    """

    PROCEED_WITH_NOTICE = "PROCEED_WITH_NOTICE"
    """Change is within tolerance; proceed but inform the user."""

    RETRY_ALLOWED = "RETRY_ALLOWED"
    """The operation can be retried with the same parameters."""

    USER_CONFIRMATION_REQUIRED = "USER_CONFIRMATION_REQUIRED"
    """The user must confirm before proceeding (price change, cart modification)."""

    NEW_MANDATE_REQUIRED = "NEW_MANDATE_REQUIRED"
    """The current mandate is invalid; a new mandate must be obtained from the user."""

    ALTERNATIVE_PAYMENT_REQUIRED = "ALTERNATIVE_PAYMENT_REQUIRED"
    """The current payment method failed; an alternative method is needed."""

    ABORT_TRANSACTION = "ABORT_TRANSACTION"
    """The transaction cannot proceed and should be terminated."""


class PaymentDeclineCode(str, Enum):
    """Common payment decline reason codes from PSPs and issuers.

    These codes help agents understand why a payment was declined and
    determine appropriate user communication and recovery actions.
    """

    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    """The account has insufficient funds for the transaction."""

    CARD_EXPIRED = "CARD_EXPIRED"
    """The payment card has expired."""

    CARD_NOT_SUPPORTED = "CARD_NOT_SUPPORTED"
    """The card type is not supported by the merchant."""

    CVV_MISMATCH = "CVV_MISMATCH"
    """The security code (CVV/CVC) is incorrect."""

    RISK_REJECTED = "RISK_REJECTED"
    """The transaction was rejected due to fraud/risk rules."""

    SCA_REQUIRED = "SCA_REQUIRED"
    """Strong Customer Authentication (3DS, biometric) is required."""

    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    """The transaction exceeds the account's spending limit."""

    ISSUER_UNAVAILABLE = "ISSUER_UNAVAILABLE"
    """The card issuer is temporarily unavailable."""

    GENERIC_DECLINE = "GENERIC_DECLINE"
    """The payment was declined without a specific reason."""


class ItemRejectionReason(str, Enum):
    """Reasons why an item may be rejected from a cart.

    Used in partial cart rejection scenarios to explain why specific
    items cannot be fulfilled.
    """

    OUT_OF_STOCK = "OUT_OF_STOCK"
    """The item is currently out of stock."""

    DISCONTINUED = "DISCONTINUED"
    """The item has been discontinued and is no longer available."""

    REGION_RESTRICTED = "REGION_RESTRICTED"
    """The item cannot be shipped to the specified region."""

    QUANTITY_UNAVAILABLE = "QUANTITY_UNAVAILABLE"
    """The requested quantity is not available."""

    PRICE_CHANGED = "PRICE_CHANGED"
    """The item's price has changed since it was added to the cart."""


class RejectedItem(BaseModel):
    """Details about an item that was rejected from a cart."""

    sku: str = Field(
        ...,
        description="The SKU or product identifier of the rejected item."
    )
    reason: ItemRejectionReason = Field(
        ...,
        description="The reason why the item was rejected."
    )
    message: Optional[str] = Field(
        None,
        description="Additional details about the rejection."
    )
    alternative_sku: Optional[str] = Field(
        None,
        description="An alternative product SKU that may satisfy the user's intent."
    )


class FailureResponse(BaseModel):
    """Standard structure for communicating failures between agents.

    This type enables consistent error handling across the agent ecosystem.
    All agents SHOULD use this structure when communicating failure states
    to ensure predictable behavior and recovery flows.

    Example:
        ```python
        failure = FailureResponse(
            category=FailureCategory.PRICE_DRIFT,
            message="Price increased from $100 to $115 (15% drift)",
            recovery_action=RecoveryAction.USER_CONFIRMATION_REQUIRED,
            original_value={"amount": 100.00, "currency": "USD"},
            actual_value={"amount": 115.00, "currency": "USD"},
            details={"drift_percent": 15.0, "tolerance_percent": 5.0}
        )
        ```
    """

    category: FailureCategory = Field(
        ...,
        description="The category of failure that occurred."
    )
    message: str = Field(
        ...,
        description="Human-readable description of the failure suitable for logging or user display."
    )
    recovery_action: RecoveryAction = Field(
        ...,
        description=(
            "Recommended action for the calling agent to take. "
            "Use this as the single source of truth for determining next steps: "
            "RETRY_ALLOWED implies retry is possible, "
            "USER_CONFIRMATION_REQUIRED/NEW_MANDATE_REQUIRED/ALTERNATIVE_PAYMENT_REQUIRED "
            "imply user action is needed."
        )
    )
    details: Optional[dict[str, Any]] = Field(
        None,
        description="Additional context about the failure (e.g., decline codes, drift percentages)."
    )
    original_value: Optional[Any] = Field(
        None,
        description="The original/expected value (e.g., original price, original cart contents)."
    )
    actual_value: Optional[Any] = Field(
        None,
        description="The actual value that caused the failure (e.g., new price, modified cart)."
    )
    rejected_items: Optional[list[RejectedItem]] = Field(
        None,
        description="List of items that were rejected, for CART_MODIFIED failures."
    )
    decline_code: Optional[PaymentDeclineCode] = Field(
        None,
        description="The specific decline code, for PAYMENT_DECLINED failures."
    )

