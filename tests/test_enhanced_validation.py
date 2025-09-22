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

"""Tests for enhanced validation and error handling."""

import pytest
from unittest.mock import Mock

from ap2.types.payment_request import (
    PaymentRequest, PaymentDetailsInit, PaymentItem, PaymentCurrencyAmount,
    PaymentMethodData, PaymentOptions
)
from ap2.types.mandate import PaymentMandate
from ap2.validation.enhanced_validation import (
    EnhancedValidator, AP2ValidationError, AP2ErrorCode, ValidationResult
)


class TestEnhancedValidator:
    """Test cases for the EnhancedValidator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = EnhancedValidator()
    
    def test_validate_currency_amount_valid(self):
        """Test validation of valid currency amount."""
        amount = PaymentCurrencyAmount(currency="USD", value=99.99)
        result = self.validator.validate_currency_amount(amount)
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
    
    def test_validate_currency_amount_invalid_currency(self):
        """Test validation with invalid currency code."""
        amount = PaymentCurrencyAmount(currency="INVALID", value=99.99)
        result = self.validator.validate_currency_amount(amount)
        
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0]['error_code'] == AP2ErrorCode.INVALID_CURRENCY_CODE.value
        assert "INVALID" in result.errors[0]['message']
        assert "suggestions" in result.errors[0]
    
    def test_validate_currency_amount_negative_value(self):
        """Test validation with negative amount."""
        amount = PaymentCurrencyAmount(currency="USD", value=-10.0)
        result = self.validator.validate_currency_amount(amount)
        
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0]['error_code'] == AP2ErrorCode.INVALID_AMOUNT.value
        assert "positive" in result.errors[0]['message']
    
    def test_validate_currency_amount_exceeds_limit(self):
        """Test validation with amount exceeding maximum limit."""
        amount = PaymentCurrencyAmount(currency="USD", value=2000000.0)
        result = self.validator.validate_currency_amount(amount)
        
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0]['error_code'] == AP2ErrorCode.AMOUNT_EXCEEDS_LIMIT.value
    
    def test_validate_currency_amount_many_decimals_warning(self):
        """Test validation warns about excessive decimal places."""
        amount = PaymentCurrencyAmount(currency="USD", value=99.99999)
        result = self.validator.validate_currency_amount(amount)
        
        assert result.is_valid  # Still valid, just a warning
        assert len(result.warnings) == 1
        assert "decimal places" in result.warnings[0]
    
    def test_validate_string_field_valid(self):
        """Test validation of valid string field."""
        result = self.validator.validate_string_field("Valid string", "test_field")
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_string_field_required_missing(self):
        """Test validation of missing required string field."""
        result = self.validator.validate_string_field(None, "test_field", required=True)
        
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0]['error_code'] == AP2ErrorCode.MISSING_REQUIRED_FIELD.value
    
    def test_validate_string_field_too_long(self):
        """Test validation of string field that's too long."""
        long_string = "x" * 1001  # Exceeds MAX_STRING_LENGTH
        result = self.validator.validate_string_field(long_string, "test_field")
        
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0]['error_code'] == AP2ErrorCode.INVALID_FIELD_FORMAT.value
        assert "maximum length" in result.errors[0]['message']
    
    def test_validate_string_field_invalid_characters(self):
        """Test validation of string field with invalid characters."""
        malicious_string = "<script>alert('xss')</script>"
        result = self.validator.validate_string_field(malicious_string, "test_field")
        
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0]['error_code'] == AP2ErrorCode.INVALID_FIELD_FORMAT.value
        assert "invalid characters" in result.errors[0]['message']
    
    def test_validate_payment_request_valid(self):
        """Test validation of valid payment request."""
        payment_request = PaymentRequest(
            method_data=[
                PaymentMethodData(supported_methods="basic-card", data={})
            ],
            details=PaymentDetailsInit(
                id="test-payment-123",
                display_items=[],
                total=PaymentItem(
                    label="Total",
                    amount=PaymentCurrencyAmount(currency="USD", value=99.99)
                )
            ),
            options=PaymentOptions()
        )
        
        result = self.validator.validate_payment_request(payment_request)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_payment_request_no_payment_methods(self):
        """Test validation of payment request with no payment methods."""
        payment_request = PaymentRequest(
            method_data=[],
            details=PaymentDetailsInit(
                id="test-payment-123",
                display_items=[],
                total=PaymentItem(
                    label="Total",
                    amount=PaymentCurrencyAmount(currency="USD", value=99.99)
                )
            )
        )
        
        result = self.validator.validate_payment_request(payment_request)
        
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0]['error_code'] == AP2ErrorCode.MISSING_REQUIRED_FIELD.value
        assert "payment method" in result.errors[0]['message']
    
    def test_validate_payment_request_too_many_items(self):
        """Test validation of payment request with too many display items."""
        display_items = [
            PaymentItem(
                label=f"Item {i}",
                amount=PaymentCurrencyAmount(currency="USD", value=1.0)
            )
            for i in range(1001)  # Exceeds MAX_ITEMS_COUNT
        ]
        
        payment_request = PaymentRequest(
            method_data=[
                PaymentMethodData(supported_methods="basic-card", data={})
            ],
            details=PaymentDetailsInit(
                id="test-payment-123",
                display_items=display_items,
                total=PaymentItem(
                    label="Total",
                    amount=PaymentCurrencyAmount(currency="USD", value=1001.0)
                )
            )
        )
        
        result = self.validator.validate_payment_request(payment_request)
        
        assert not result.is_valid
        assert any(error['error_code'] == AP2ErrorCode.INVALID_FIELD_FORMAT.value 
                  for error in result.errors)
    
    def test_validate_payment_mandate_signature_valid(self):
        """Test validation of valid payment mandate signature."""
        # Create a mock user authorization with required fields
        mock_auth = Mock()
        mock_auth.__dict__ = {
            'signature': 'valid_signature_123',
            'timestamp': '2025-09-22T10:00:00Z'
        }
        
        payment_mandate = PaymentMandate(user_authorization=mock_auth)
        result = self.validator.validate_payment_mandate_signature(payment_mandate)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_payment_mandate_signature_missing_auth(self):
        """Test validation of payment mandate with missing authorization."""
        payment_mandate = PaymentMandate(user_authorization=None)
        result = self.validator.validate_payment_mandate_signature(payment_mandate)
        
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0]['error_code'] == AP2ErrorCode.AUTHORIZATION_FAILED.value
        assert "authorization not found" in result.errors[0]['message']
    
    def test_validate_payment_mandate_signature_missing_signature(self):
        """Test validation of payment mandate with missing signature."""
        mock_auth = Mock()
        mock_auth.__dict__ = {'timestamp': '2025-09-22T10:00:00Z'}  # No signature
        
        payment_mandate = PaymentMandate(user_authorization=mock_auth)
        result = self.validator.validate_payment_mandate_signature(payment_mandate)
        
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0]['error_code'] == AP2ErrorCode.SIGNATURE_INVALID.value
    
    def test_validate_payment_mandate_signature_missing_timestamp_warning(self):
        """Test validation warns about missing timestamp."""
        mock_auth = Mock()
        mock_auth.__dict__ = {'signature': 'valid_signature_123'}  # No timestamp
        
        payment_mandate = PaymentMandate(user_authorization=mock_auth)
        result = self.validator.validate_payment_mandate_signature(payment_mandate)
        
        assert result.is_valid  # Valid but with warning
        assert len(result.warnings) == 1
        assert "timestamp" in result.warnings[0]


class TestAP2ValidationError:
    """Test cases for AP2ValidationError class."""
    
    def test_error_initialization(self):
        """Test error initialization with all parameters."""
        error = AP2ValidationError(
            message="Test error message",
            error_code=AP2ErrorCode.INVALID_AMOUNT,
            field_path="payment.amount",
            invalid_value=-10.0,
            suggestions=["Use positive amount", "Check input validation"]
        )
        
        assert str(error) == "Test error message"
        assert error.error_code == AP2ErrorCode.INVALID_AMOUNT
        assert error.field_path == "payment.amount"
        assert error.invalid_value == -10.0
        assert len(error.suggestions) == 2
    
    def test_error_to_dict(self):
        """Test error serialization to dictionary."""
        error = AP2ValidationError(
            message="Test error",
            error_code=AP2ErrorCode.INVALID_CURRENCY_CODE,
            field_path="currency",
            invalid_value="INVALID",
            suggestions=["Use ISO 4217 code"]
        )
        
        error_dict = error.to_dict()
        
        assert error_dict['error_code'] == "AP2_1002"
        assert error_dict['message'] == "Test error"
        assert error_dict['field_path'] == "currency"
        assert error_dict['invalid_value'] == "INVALID"
        assert error_dict['suggestions'] == ["Use ISO 4217 code"]


class TestValidationResult:
    """Test cases for ValidationResult class."""
    
    def test_add_error(self):
        """Test adding error to validation result."""
        result = ValidationResult(is_valid=True)
        error = AP2ValidationError(
            message="Test error",
            error_code=AP2ErrorCode.INVALID_AMOUNT
        )
        
        result.add_error(error)
        
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0]['error_code'] == "AP2_1003"
    
    def test_add_warning(self):
        """Test adding warning to validation result."""
        result = ValidationResult(is_valid=True)
        
        result.add_warning("This is a test warning")
        
        assert result.is_valid  # Warnings don't affect validity
        assert len(result.warnings) == 1
        assert result.warnings[0] == "This is a test warning"


# Integration tests
class TestBackwardCompatibility:
    """Test backward compatibility with existing validation functions."""
    
    def test_legacy_validate_payment_mandate_signature_valid(self):
        """Test legacy function with valid mandate."""
        from ap2.validation.enhanced_validation import validate_payment_mandate_signature
        
        mock_auth = Mock()
        mock_auth.__dict__ = {'signature': 'valid_signature'}
        payment_mandate = PaymentMandate(user_authorization=mock_auth)
        
        # Should not raise an exception
        validate_payment_mandate_signature(payment_mandate)
    
    def test_legacy_validate_payment_mandate_signature_invalid(self):
        """Test legacy function with invalid mandate."""
        from ap2.validation.enhanced_validation import validate_payment_mandate_signature
        
        payment_mandate = PaymentMandate(user_authorization=None)
        
        with pytest.raises(ValueError) as exc_info:
            validate_payment_mandate_signature(payment_mandate)
        
        assert "authorization not found" in str(exc_info.value)