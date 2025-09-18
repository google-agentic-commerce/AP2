"""Unit tests for AP2 mandate types."""

import pytest

from ap2.types.mandate import (
    IntentMandate,
    CartContents,
    PaymentMandateContents,
)
from ap2.types.payment_request import (
    PaymentCurrencyAmount,
    PaymentItem,
    PaymentMethodData,
    PaymentDetailsInit,
    PaymentRequest,
    PaymentResponse
)


class TestIntentMandate:
    """Test IntentMandate model."""

    def test_intent_mandate_creation(self):
        """Test creating a basic intent mandate."""
        mandate = IntentMandate(
            natural_language_description="Red basketball shoes",
            intent_expiry="2025-01-01T00:00:00Z"
        )

        assert mandate.user_cart_confirmation_required is True
        assert mandate.natural_language_description == "Red basketball shoes"
        assert mandate.intent_expiry == "2025-01-01T00:00:00Z"
        assert mandate.merchants is None
        assert mandate.skus is None
        assert mandate.requires_refundability is False

    def test_intent_mandate_with_merchants(self):
        """Test intent mandate with specific merchants."""
        mandate = IntentMandate(
            natural_language_description="Blue running shoes",
            intent_expiry="2025-01-01T00:00:00Z",
            merchants=["nike.com", "adidas.com"],
            user_cart_confirmation_required=False
        )

        assert mandate.merchants == ["nike.com", "adidas.com"]
        assert mandate.user_cart_confirmation_required is False


class TestCartContents:
    """Test CartContents model."""

    def test_cart_contents_creation(self):
        """Test creating cart contents with payment request."""
        # Create payment request components
        amount = PaymentCurrencyAmount(currency="USD", value=99.99)
        total_item = PaymentItem(label="Total", amount=amount)

        method_data = PaymentMethodData(supported_methods="basic-card")
        details = PaymentDetailsInit(
            id="cart-123",
            display_items=[],
            total=total_item
        )

        payment_request = PaymentRequest(
            method_data=[method_data],
            details=details
        )

        cart_contents = CartContents(
            id="cart-abc-123",
            user_cart_confirmation_required=True,
            payment_request=payment_request,
            cart_expiry="2025-01-01T12:00:00Z",
            merchant_name="Test Merchant"
        )

        assert cart_contents.id == "cart-abc-123"
        assert cart_contents.user_cart_confirmation_required is True
        assert cart_contents.merchant_name == "Test Merchant"
        assert cart_contents.payment_request.details.id == "cart-123"


class TestPaymentMandateContents:
    """Test PaymentMandateContents model."""

    def test_payment_mandate_contents_creation(self):
        """Test creating payment mandate contents."""
        # Create required components
        amount = PaymentCurrencyAmount(currency="USD", value=50.00)
        total_item = PaymentItem(label="Total", amount=amount)

        payment_response = PaymentResponse(
            request_id="req-123",
            method_name="basic-card",
            details={"cardNumber": "****1234"}
        )

        contents = PaymentMandateContents(
            payment_mandate_id="mandate-123",
            payment_details_id="details-456",
            payment_details_total=total_item,
            payment_response=payment_response,
            merchant_agent="merchant.example.com"
        )

        assert contents.payment_mandate_id == "mandate-123"
        assert contents.payment_details_id == "details-456"
        assert contents.merchant_agent == "merchant.example.com"
        assert contents.payment_response.request_id == "req-123"
        # Timestamp should be auto-generated
        assert contents.timestamp is not None

    def test_payment_mandate_contents_with_custom_timestamp(self):
        """Test payment mandate contents with custom timestamp."""
        amount = PaymentCurrencyAmount(currency="USD", value=25.00)
        total_item = PaymentItem(label="Total", amount=amount)

        payment_response = PaymentResponse(
            request_id="req-456",
            method_name="basic-card"
        )

        custom_timestamp = "2025-01-01T10:00:00Z"

        contents = PaymentMandateContents(
            payment_mandate_id="mandate-456",
            payment_details_id="details-789",
            payment_details_total=total_item,
            payment_response=payment_response,
            merchant_agent="merchant2.example.com",
            timestamp=custom_timestamp
        )

        assert contents.timestamp == custom_timestamp
