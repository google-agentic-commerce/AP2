"""Unit tests for AP2 payment request types."""

# import pytest
# from pydantic import ValidationError

from ap2.types.payment_request import (
    PaymentCurrencyAmount,
    PaymentItem,
    # PaymentShippingOption,
    PaymentOptions,
    PaymentMethodData,
    PaymentDetailsInit,
    PaymentRequest,
    # PaymentResponse
)
# from ap2.types.contact_picker import ContactAddress


class TestPaymentCurrencyAmount:
    """Test PaymentCurrencyAmount validation."""

    def test_valid_currency_amount(self):
        """Test creating a valid currency amount."""
        amount = PaymentCurrencyAmount(currency="USD", value=10.50)
        assert amount.currency == "USD"
        assert amount.value == 10.50

    def test_currency_amount_serialization(self):
        """Test JSON serialization."""
        amount = PaymentCurrencyAmount(currency="EUR", value=25.99)
        data = amount.model_dump()
        assert data == {"currency": "EUR", "value": 25.99}


class TestPaymentItem:
    """Test PaymentItem model."""

    def test_payment_item_creation(self):
        """Test basic payment item creation."""
        amount = PaymentCurrencyAmount(currency="USD", value=10.00)
        item = PaymentItem(
            label="Test Item",
            amount=amount,
            refund_period=30
        )
        assert item.label == "Test Item"
        assert item.amount.value == 10.00
        assert item.refund_period == 30
        assert item.pending is None

    def test_payment_item_with_pending(self):
        """Test payment item with pending flag."""
        amount = PaymentCurrencyAmount(currency="USD", value=15.00)
        item = PaymentItem(
            label="Pending Item",
            amount=amount,
            pending=True
        )
        assert item.pending is True


class TestPaymentRequest:
    """Test PaymentRequest model."""

    def test_payment_request_creation(self):
        """Test creating a complete payment request."""
        # Create required components
        amount = PaymentCurrencyAmount(currency="USD", value=100.00)
        total_item = PaymentItem(label="Total", amount=amount)
        display_item = PaymentItem(label="Product", amount=amount)

        method_data = PaymentMethodData(
            supported_methods="basic-card",
            data={"supportedNetworks": ["visa", "mastercard"]}
        )

        details = PaymentDetailsInit(
            id="payment-123",
            display_items=[display_item],
            total=total_item
        )

        payment_request = PaymentRequest(
            method_data=[method_data],
            details=details
        )

        assert payment_request.details.id == "payment-123"
        assert len(payment_request.method_data) == 1
        assert payment_request.method_data[0].supported_methods == "basic-card"

    def test_payment_request_with_options(self):
        """Test payment request with payment options."""
        amount = PaymentCurrencyAmount(currency="USD", value=50.00)
        total_item = PaymentItem(label="Total", amount=amount)

        method_data = PaymentMethodData(supported_methods="basic-card")
        details = PaymentDetailsInit(
            id="payment-456",
            display_items=[],
            total=total_item
        )

        options = PaymentOptions(
            request_payer_name=True,
            request_payer_email=True,
            request_shipping=True
        )

        payment_request = PaymentRequest(
            method_data=[method_data],
            details=details,
            options=options
        )

        assert payment_request.options.request_payer_name is True
        assert payment_request.options.request_payer_email is True
