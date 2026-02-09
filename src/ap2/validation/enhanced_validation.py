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

"""Enhanced validation and error handling for AP2 protocol.

This module provides comprehensive validation for payment requests, mandates,
and responses with standardized error codes and detailed error information.
"""

import logging
import re
import base64
import json
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from ap2.types.mandate import PaymentMandate
from ap2.types.payment_request import PaymentRequest, PaymentResponse, PaymentCurrencyAmount
from pydantic import BaseModel, Field


class AP2ErrorCode(Enum):
    """Standardized error codes for AP2 protocol operations."""
    
    # Validation errors (1000-1999)
    INVALID_PAYMENT_REQUEST = "AP2_1001"
    INVALID_CURRENCY_CODE = "AP2_1002"
    INVALID_AMOUNT = "AP2_1003"
    INVALID_PAYMENT_METHOD = "AP2_1004"
    INVALID_SHIPPING_ADDRESS = "AP2_1005"
    INVALID_MANDATE_SIGNATURE = "AP2_1006"
    MISSING_REQUIRED_FIELD = "AP2_1007"
    INVALID_FIELD_FORMAT = "AP2_1008"
    
    # Business logic errors (2000-2999)
    AMOUNT_EXCEEDS_LIMIT = "AP2_2001"
    CURRENCY_NOT_SUPPORTED = "AP2_2002"
    PAYMENT_METHOD_NOT_ACCEPTED = "AP2_2003"
    SHIPPING_NOT_AVAILABLE = "AP2_2004"
    DUPLICATE_TRANSACTION = "AP2_2005"
    EXPIRED_PAYMENT_REQUEST = "AP2_2006"
    
    # Security errors (3000-3999)
    AUTHORIZATION_FAILED = "AP2_3001"
    SIGNATURE_INVALID = "AP2_3002"
    RATE_LIMIT_EXCEEDED = "AP2_3003"
    SUSPICIOUS_ACTIVITY = "AP2_3004"
    
    # System errors (4000-4999)
    INTERNAL_ERROR = "AP2_4001"
    SERVICE_UNAVAILABLE = "AP2_4002"
    TIMEOUT = "AP2_4003"
    NETWORK_ERROR = "AP2_4004"


class AP2ValidationError(Exception):
    """Enhanced validation error with structured error information."""
    
    def __init__(
        self,
        message: str,
        error_code: AP2ErrorCode,
        field_path: Optional[str] = None,
        invalid_value: Optional[Any] = None,
        suggestions: Optional[List[str]] = None
    ):
        """Initialize AP2ValidationError.
        
        Args:
            message: Human-readable error message
            error_code: Standardized AP2 error code
            field_path: Dot-notation path to the invalid field (e.g., "details.total.amount")
            invalid_value: The actual invalid value that caused the error
            suggestions: List of suggestions to fix the error
        """
        super().__init__(message)
        self.error_code = error_code
        self.field_path = field_path
        self.invalid_value = invalid_value
        self.suggestions = suggestions or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary format for API responses."""
        return {
            "error_code": self.error_code.value,
            "message": str(self),
            "field_path": self.field_path,
            "invalid_value": str(self.invalid_value) if self.invalid_value is not None else None,
            "suggestions": self.suggestions
        }


class ValidationResult(BaseModel):
    """Result of a validation operation."""
    
    is_valid: bool = Field(..., description="Whether the validation passed")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="List of validation errors")
    warnings: List[str] = Field(default_factory=list, description="List of validation warnings")
    
    def add_error(self, error: AP2ValidationError) -> None:
        """Add a validation error to the result."""
        self.is_valid = False
        self.errors.append(error.to_dict())
    
    def add_warning(self, warning: str) -> None:
        """Add a validation warning to the result."""
        self.warnings.append(warning)


class EnhancedValidator:
    """Enhanced validator for AP2 protocol objects."""
    
    # ISO 4217 currency codes (subset for demonstration)
    VALID_CURRENCIES = {
        "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "SEK", "NZD",
        "MXN", "SGD", "HKD", "NOK", "TRY", "RUB", "INR", "BRL", "ZAR", "KRW"
    }
    
    # Maximum values for security
    MAX_PAYMENT_AMOUNT = 1000000.00  # $1M limit
    MAX_ITEMS_COUNT = 1000
    MAX_STRING_LENGTH = 1000
    
    def __init__(self):
        """Initialize the enhanced validator."""
        self.logger = logging.getLogger(__name__)
    
    def validate_currency_amount(self, amount: PaymentCurrencyAmount, field_path: str = "") -> ValidationResult:
        """Validate a PaymentCurrencyAmount object.
        
        Args:
            amount: The currency amount to validate
            field_path: The field path for error reporting
            
        Returns:
            ValidationResult with any errors found
        """
        result = ValidationResult(is_valid=True)
        
        # Validate currency code
        if not amount.currency:
            result.add_error(AP2ValidationError(
                "Currency code is required",
                AP2ErrorCode.MISSING_REQUIRED_FIELD,
                field_path=f"{field_path}.currency",
                suggestions=["Provide a valid ISO 4217 currency code"]
            ))
        elif amount.currency not in self.VALID_CURRENCIES:
            result.add_error(AP2ValidationError(
                f"Invalid currency code: {amount.currency}",
                AP2ErrorCode.INVALID_CURRENCY_CODE,
                field_path=f"{field_path}.currency",
                invalid_value=amount.currency,
                suggestions=[f"Use one of: {', '.join(sorted(self.VALID_CURRENCIES))}"]
            ))
        
        # Validate amount value
        if amount.value is None:
            result.add_error(AP2ValidationError(
                "Amount value is required",
                AP2ErrorCode.MISSING_REQUIRED_FIELD,
                field_path=f"{field_path}.value"
            ))
        elif not isinstance(amount.value, (int, float)):
            result.add_error(AP2ValidationError(
                "Amount value must be a number",
                AP2ErrorCode.INVALID_FIELD_FORMAT,
                field_path=f"{field_path}.value",
                invalid_value=amount.value,
                suggestions=["Provide a numeric value (int or float)"]
            ))
        elif amount.value <= 0:
            result.add_error(AP2ValidationError(
                "Amount value must be positive",
                AP2ErrorCode.INVALID_AMOUNT,
                field_path=f"{field_path}.value",
                invalid_value=amount.value,
                suggestions=["Provide a positive amount greater than 0"]
            ))
        elif amount.value > self.MAX_PAYMENT_AMOUNT:
            result.add_error(AP2ValidationError(
                f"Amount exceeds maximum limit of {self.MAX_PAYMENT_AMOUNT}",
                AP2ErrorCode.AMOUNT_EXCEEDS_LIMIT,
                field_path=f"{field_path}.value",
                invalid_value=amount.value,
                suggestions=[f"Reduce amount to {self.MAX_PAYMENT_AMOUNT} or less"]
            ))
        
        # Check for reasonable decimal places
        if isinstance(amount.value, float) and len(str(amount.value).split('.')[-1]) > 2:
            result.add_warning(f"Amount has more than 2 decimal places: {amount.value}")
        
        return result
    
    def validate_string_field(self, value: Optional[str], field_name: str, required: bool = True) -> ValidationResult:
        """Validate a string field with common checks.
        
        Args:
            value: The string value to validate
            field_name: Name of the field for error reporting
            required: Whether the field is required
            
        Returns:
            ValidationResult with any errors found
        """
        result = ValidationResult(is_valid=True)
        
        if required and (value is None or value == ""):
            result.add_error(AP2ValidationError(
                f"{field_name} is required",
                AP2ErrorCode.MISSING_REQUIRED_FIELD,
                field_path=field_name
            ))
        elif value is not None:
            if len(value) > self.MAX_STRING_LENGTH:
                result.add_error(AP2ValidationError(
                    f"{field_name} exceeds maximum length of {self.MAX_STRING_LENGTH}",
                    AP2ErrorCode.INVALID_FIELD_FORMAT,
                    field_path=field_name,
                    invalid_value=f"{value[:50]}..." if len(value) > 50 else value,
                    suggestions=[f"Reduce length to {self.MAX_STRING_LENGTH} characters or less"]
                ))
            
            # Check for potentially malicious content
            if re.search(r'[<>"\'\\\x00-\x1f]', value):
                result.add_error(AP2ValidationError(
                    f"{field_name} contains invalid characters",
                    AP2ErrorCode.INVALID_FIELD_FORMAT,
                    field_path=field_name,
                    suggestions=["Remove special characters, quotes, and control characters"]
                ))
        
        return result
    
    def validate_payment_request(self, payment_request: PaymentRequest) -> ValidationResult:
        """Validate a PaymentRequest object comprehensively.
        
        Args:
            payment_request: The payment request to validate
            
        Returns:
            ValidationResult with any errors found
        """
        result = ValidationResult(is_valid=True)
        
        # Validate payment methods
        if not payment_request.method_data:
            result.add_error(AP2ValidationError(
                "At least one payment method must be specified",
                AP2ErrorCode.MISSING_REQUIRED_FIELD,
                field_path="method_data",
                suggestions=["Add at least one supported payment method"]
            ))
        else:
            for i, method in enumerate(payment_request.method_data):
                method_result = self.validate_string_field(
                    method.supported_methods, 
                    f"method_data[{i}].supported_methods"
                )
                if not method_result.is_valid:
                    result.errors.extend(method_result.errors)
        
        # Validate payment details
        if payment_request.details:
            # Validate ID
            id_result = self.validate_string_field(payment_request.details.id, "details.id")
            if not id_result.is_valid:
                result.errors.extend(id_result.errors)
            
            # Validate total amount
            if payment_request.details.total:
                total_result = self.validate_currency_amount(
                    payment_request.details.total.amount, 
                    "details.total.amount"
                )
                if not total_result.is_valid:
                    result.errors.extend(total_result.errors)
                
                # Validate total label
                label_result = self.validate_string_field(
                    payment_request.details.total.label, 
                    "details.total.label"
                )
                if not label_result.is_valid:
                    result.errors.extend(label_result.errors)
            
            # Validate display items
            if len(payment_request.details.display_items) > self.MAX_ITEMS_COUNT:
                result.add_error(AP2ValidationError(
                    f"Too many display items: {len(payment_request.details.display_items)}",
                    AP2ErrorCode.INVALID_FIELD_FORMAT,
                    field_path="details.display_items",
                    suggestions=[f"Reduce to {self.MAX_ITEMS_COUNT} items or less"]
                ))
            
            for i, item in enumerate(payment_request.details.display_items):
                item_result = self.validate_currency_amount(
                    item.amount, 
                    f"details.display_items[{i}].amount"
                )
                if not item_result.is_valid:
                    result.errors.extend(item_result.errors)
        
        # Update overall validity
        result.is_valid = len(result.errors) == 0
        
        if result.is_valid:
            self.logger.info(f"PaymentRequest validation passed for ID: {payment_request.details.id}")
        else:
            self.logger.warning(f"PaymentRequest validation failed with {len(result.errors)} errors")
        
        return result
    
    def _validate_authorization_token(self, token: str) -> ValidationResult:
        """Validate a base64url-encoded authorization token (JWT or SD-JWT-VC).
        
        Args:
            token: The base64url-encoded authorization token
            
        Returns:
            ValidationResult with validation details
        """
        result = ValidationResult(is_valid=True)
        
        # Basic format validation
        if not token or not isinstance(token, str):
            result.add_error(AP2ValidationError(
                "Authorization token must be a non-empty string",
                AP2ErrorCode.INVALID_FIELD_FORMAT,
                field_path="user_authorization"
            ))
            return result
        
        # Check for valid base64url characters
        if not re.match(r'^[A-Za-z0-9_-]+$', token.replace('.', '')):
            result.add_error(AP2ValidationError(
                "Authorization token contains invalid characters for base64url encoding",
                AP2ErrorCode.INVALID_FIELD_FORMAT,
                field_path="user_authorization",
                suggestions=[
                    "Ensure token is properly base64url encoded",
                    "Valid characters: A-Z, a-z, 0-9, -, _, and . (for JWT separators)"
                ]
            ))
            return result
        
        # For JWT format, expect 3 parts separated by dots
        parts = token.split('.')
        if len(parts) == 3:
            # Standard JWT format
            return self._validate_jwt_structure(parts, result)
        elif len(parts) >= 4:
            # Potentially SD-JWT-VC format (issuer JWT + disclosures + key binding)
            result.add_warning("Detected potential SD-JWT-VC format with multiple parts")
            # Validate the first part as issuer JWT
            jwt_parts = parts[:3]
            return self._validate_jwt_structure(jwt_parts, result)
        else:
            result.add_error(AP2ValidationError(
                f"Invalid JWT format: expected 3 parts separated by '.', got {len(parts)}",
                AP2ErrorCode.INVALID_FIELD_FORMAT,
                field_path="user_authorization",
                suggestions=[
                    "Ensure JWT has header.payload.signature format",
                    "For SD-JWT-VC, ensure proper structure with issuer JWT"
                ]
            ))
        
        return result
    
    def _validate_jwt_structure(self, parts: List[str], result: ValidationResult) -> ValidationResult:
        """Validate the structure of JWT parts.
        
        Args:
            parts: List of JWT parts [header, payload, signature]
            result: ValidationResult to append errors to
            
        Returns:
            Updated ValidationResult
        """
        try:
            # Validate header
            header_data = self._decode_jwt_part(parts[0])
            if not isinstance(header_data, dict):
                result.add_error(AP2ValidationError(
                    "JWT header must be a JSON object",
                    AP2ErrorCode.INVALID_FIELD_FORMAT,
                    field_path="user_authorization.header"
                ))
            else:
                # Check required header fields
                if 'alg' not in header_data:
                    result.add_error(AP2ValidationError(
                        "JWT header missing required 'alg' field",
                        AP2ErrorCode.MISSING_REQUIRED_FIELD,
                        field_path="user_authorization.header.alg",
                        suggestions=["Include algorithm specification (e.g., 'ES256K', 'RS256')"]
                    ))
                
                # Validate algorithm
                if 'alg' in header_data and header_data['alg'] in ['none', 'None']:
                    result.add_error(AP2ValidationError(
                        "Insecure algorithm 'none' not allowed in authorization tokens",
                        AP2ErrorCode.SIGNATURE_INVALID,
                        field_path="user_authorization.header.alg",
                        suggestions=["Use a secure signing algorithm like ES256K or RS256"]
                    ))
            
            # Validate payload
            payload_data = self._decode_jwt_part(parts[1])
            if not isinstance(payload_data, dict):
                result.add_error(AP2ValidationError(
                    "JWT payload must be a JSON object",
                    AP2ErrorCode.INVALID_FIELD_FORMAT,
                    field_path="user_authorization.payload"
                ))
            else:
                # Check for required claims based on mandate documentation
                self._validate_mandate_claims(payload_data, result)
            
            # Validate signature exists and is not empty
            if not parts[2]:
                result.add_error(AP2ValidationError(
                    "JWT signature cannot be empty",
                    AP2ErrorCode.SIGNATURE_INVALID,
                    field_path="user_authorization.signature",
                    suggestions=["Ensure token is properly signed with a valid private key"]
                ))
            
        except Exception as e:
            result.add_error(AP2ValidationError(
                f"Failed to parse JWT structure: {str(e)}",
                AP2ErrorCode.INVALID_FIELD_FORMAT,
                field_path="user_authorization",
                suggestions=[
                    "Ensure token is properly base64url encoded",
                    "Verify JWT structure is valid"
                ]
            ))
        
        return result
    
    def _decode_jwt_part(self, part: str) -> Dict[str, Any]:
        """Decode a base64url-encoded JWT part.
        
        Args:
            part: The base64url-encoded part
            
        Returns:
            Decoded JSON object
            
        Raises:
            Exception: If decoding fails
        """
        # Add padding if needed for base64 decoding
        padding = 4 - (len(part) % 4)
        if padding != 4:
            part += '=' * padding
        
        # Convert base64url to standard base64
        part = part.replace('-', '+').replace('_', '/')
        
        # Decode and parse JSON
        decoded_bytes = base64.b64decode(part)
        return json.loads(decoded_bytes.decode('utf-8'))
    
    def _validate_mandate_claims(self, payload: Dict[str, Any], result: ValidationResult) -> None:
        """Validate claims specific to payment mandate authorization.
        
        Args:
            payload: The JWT payload
            result: ValidationResult to append errors to
        """
        # Check for transaction_data claim (required for mandate authorization)
        if 'transaction_data' not in payload:
            result.add_error(AP2ValidationError(
                "Missing required 'transaction_data' claim in authorization token",
                AP2ErrorCode.MISSING_REQUIRED_FIELD,
                field_path="user_authorization.payload.transaction_data",
                suggestions=[
                    "Include transaction_data with hashes of CartMandate and PaymentMandateContents",
                    "Refer to AP2 specification for proper mandate authorization format"
                ]
            ))
        elif not isinstance(payload['transaction_data'], list):
            result.add_error(AP2ValidationError(
                "transaction_data must be an array of secure hashes",
                AP2ErrorCode.INVALID_FIELD_FORMAT,
                field_path="user_authorization.payload.transaction_data",
                suggestions=["Provide an array containing hashes of mandate objects"]
            ))
        
        # Check for audience claim
        if 'aud' not in payload:
            result.add_warning("Missing 'aud' (audience) claim - recommended for security")
        
        # Check for nonce (important for replay protection)
        if 'nonce' not in payload:
            result.add_warning("Missing 'nonce' claim - recommended for replay protection")
        
        # Check for expiration
        if 'exp' not in payload:
            result.add_warning("Missing 'exp' (expiration) claim - recommended for time-bound authorization")
        
        # Validate SD-JWT specific claims if present
        if 'sd_hash' in payload:
            result.add_warning("Detected SD-JWT-VC format with selective disclosure")
            # Additional SD-JWT validation could be added here
    
    def validate_payment_mandate_signature(self, payment_mandate: PaymentMandate) -> ValidationResult:
        """Enhanced validation for PaymentMandate signature.
        
        Args:
            payment_mandate: The PaymentMandate to be validated.
            
        Returns:
            ValidationResult with detailed validation information
        """
        result = ValidationResult(is_valid=True)
        
        if payment_mandate.user_authorization is None:
            result.add_error(AP2ValidationError(
                "User authorization not found in PaymentMandate",
                AP2ErrorCode.AUTHORIZATION_FAILED,
                field_path="user_authorization",
                suggestions=[
                    "Ensure user has provided valid authorization",
                    "Check that authorization data is properly serialized"
                ]
            ))
        else:
            # Validate that user_authorization is a base64url-encoded string
            if not isinstance(payment_mandate.user_authorization, str):
                result.add_error(AP2ValidationError(
                    f"User authorization must be a base64url-encoded string, got {type(payment_mandate.user_authorization).__name__}",
                    AP2ErrorCode.INVALID_FIELD_FORMAT,
                    field_path="user_authorization",
                    invalid_value=str(type(payment_mandate.user_authorization)),
                    suggestions=[
                        "Provide user_authorization as a base64url-encoded JWT or SD-JWT-VC string",
                        "Ensure the authorization is properly encoded before validation"
                    ]
                ))
            else:
                # Validate base64url format and JWT structure
                auth_validation = self._validate_authorization_token(payment_mandate.user_authorization)
                if not auth_validation.is_valid:
                    result.errors.extend(auth_validation.errors)
                    result.warnings.extend(auth_validation.warnings)
        
        # Update overall validity
        result.is_valid = len(result.errors) == 0
        
        if result.is_valid:
            self.logger.info("Valid PaymentMandate signature found")
        else:
            self.logger.error(f"PaymentMandate validation failed: {result.errors}")
        
        return result


# Backward compatibility function
def validate_payment_mandate_signature(payment_mandate: PaymentMandate) -> None:
    """Legacy validation function for backward compatibility.
    
    Args:
        payment_mandate: The PaymentMandate to be validated.
        
    Raises:
        ValueError: If the PaymentMandate signature is not valid.
    """
    validator = EnhancedValidator()
    result = validator.validate_payment_mandate_signature(payment_mandate)
    
    if not result.is_valid:
        # Raise the first error for backward compatibility
        first_error = result.errors[0]
        raise ValueError(first_error['message'])