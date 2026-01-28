# Enhanced Error Handling and Validation for AP2 Protocol

## Overview

This protocol improvement introduces comprehensive error handling and validation capabilities to the AP2 protocol, providing standardized error codes, detailed error information, and enhanced validation for all protocol objects.

## Problem Statement

The current AP2 validation system has several limitations:

1. **Limited Error Information**: Simple exception messages without structured error codes
2. **No Field-Level Validation**: Errors don't specify which field caused the issue
3. **Missing Security Validation**: Insufficient checks for malicious input
4. **No Standardized Error Codes**: Different implementations may use inconsistent error handling
5. **Limited Debugging Information**: Hard to troubleshoot validation failures in production

## Solution

### 1. Standardized Error Codes

Introduced `AP2ErrorCode` enum with categorized error codes:

- **1000-1999**: Validation errors (format, required fields, etc.)
- **2000-2999**: Business logic errors (limits, restrictions, etc.)
- **3000-3999**: Security errors (authorization, signatures, etc.)
- **4000-4999**: System errors (timeouts, internal errors, etc.)

### 2. Enhanced Error Information

`AP2ValidationError` provides:
- Standardized error code
- Human-readable message
- Field path (dot notation)
- Invalid value that caused the error
- Suggestions for fixing the error

### 3. Comprehensive Validation

`EnhancedValidator` class provides:
- Currency code validation (ISO 4217)
- Amount validation (positive values, limits)
- String field validation (length, malicious content)
- Security validation (input sanitization)
- Business rule validation

### 4. Structured Validation Results

`ValidationResult` provides:
- Boolean validity status
- List of errors with detailed information
- List of warnings for non-critical issues

### 5. Critical Security Enhancement: PaymentMandate Authorization Validation

**SECURITY FIX**: A critical vulnerability was identified and fixed in PaymentMandate validation where `user_authorization` was incorrectly treated as a parsed object instead of a base64url-encoded string.

#### The Issue
The previous validation logic assumed `user_authorization` was an object with `__dict__` attributes, but according to the AP2 specification, it should be:
> "a base64_url-encoded verifiable presentation of a verifiable credential signing over the cart_mandate and payment_mandate_hashes"

#### The Fix
The enhanced validation now:
1. **Validates String Type**: Ensures `user_authorization` is a string, not an object
2. **Parses JWT Structure**: Properly decodes base64url and validates JWT format
3. **Enforces Required Claims**: Validates presence of `transaction_data` and other security claims
4. **Prevents Algorithm Attacks**: Rejects insecure algorithms like `none`
5. **Provides Security Guidance**: Clear error messages for proper token format

#### Required Token Format
```json
{
  "header": {
    "alg": "ES256K",
    "typ": "JWT"
  },
  "payload": {
    "aud": "payment-processor",
    "nonce": "secure-nonce-123", 
    "exp": 1727000000,
    "transaction_data": ["cart_hash", "mandate_hash"]
  }
}
```
Encoded as: `base64url(header).base64url(payload).base64url(signature)`
- Easy serialization for API responses

## Implementation Details

### Error Code Examples

```python
# Validation errors
AP2ErrorCode.INVALID_CURRENCY_CODE = "AP2_1002"
AP2ErrorCode.INVALID_AMOUNT = "AP2_1003"
AP2ErrorCode.MISSING_REQUIRED_FIELD = "AP2_1007"

# Business logic errors  
AP2ErrorCode.AMOUNT_EXCEEDS_LIMIT = "AP2_2001"
AP2ErrorCode.CURRENCY_NOT_SUPPORTED = "AP2_2002"

# Security errors
AP2ErrorCode.AUTHORIZATION_FAILED = "AP2_3001"
AP2ErrorCode.SIGNATURE_INVALID = "AP2_3002"
```

### Enhanced Error Information

```python
error = AP2ValidationError(
    message="Invalid currency code: XYZ",
    error_code=AP2ErrorCode.INVALID_CURRENCY_CODE,
    field_path="details.total.amount.currency",
    invalid_value="XYZ",
    suggestions=["Use ISO 4217 currency codes like USD, EUR, GBP"]
)

# Serializes to:
{
    "error_code": "AP2_1002",
    "message": "Invalid currency code: XYZ",
    "field_path": "details.total.amount.currency", 
    "invalid_value": "XYZ",
    "suggestions": ["Use ISO 4217 currency codes like USD, EUR, GBP"]
}
```

### Validation Usage

```python
validator = EnhancedValidator()

# Validate payment request
result = validator.validate_payment_request(payment_request)

if not result.is_valid:
    for error in result.errors:
        print(f"Error {error['error_code']}: {error['message']}")
        if error['field_path']:
            print(f"  Field: {error['field_path']}")
        if error['suggestions']:
            print(f"  Suggestions: {', '.join(error['suggestions'])}")

# Validate individual components
amount_result = validator.validate_currency_amount(amount, "payment.amount")
string_result = validator.validate_string_field(label, "item.label")
```

## Backward Compatibility

The enhancement maintains full backward compatibility:

```python
# Legacy usage still works
try:
    validate_payment_mandate_signature(mandate)
except ValueError as e:
    print(f"Validation failed: {e}")

# New enhanced usage
result = validate_payment_mandate_signature(mandate, return_detailed_result=True)
if not result.is_valid:
    for error in result.errors:
        handle_detailed_error(error)
```

## Security Improvements

### Input Sanitization

- **String Validation**: Checks for malicious characters (`<>\"'\x00-\x1f`)
- **Length Limits**: Prevents excessive memory usage
- **Format Validation**: Ensures proper data types and formats

### Rate Limiting Support

- Error codes for rate limiting (`AP2_3003`)
- Structured error information for security monitoring

### Audit Trail

- Detailed error logging with field paths
- Invalid values logged for security analysis
- Standardized error codes for SIEM integration

## Performance Considerations

### Validation Caching

```python
class EnhancedValidator:
    def __init__(self):
        self._currency_cache = set(self.VALID_CURRENCIES)
        self._regex_cache = {}
```

### Batch Validation

```python
# Validate multiple items efficiently
def validate_payment_items(self, items: List[PaymentItem]) -> ValidationResult:
    result = ValidationResult(is_valid=True)
    for i, item in enumerate(items):
        item_result = self.validate_payment_item(item, f"items[{i}]")
        if not item_result.is_valid:
            result.errors.extend(item_result.errors)
    return result
```

## Testing

Comprehensive test suite includes:

- **Unit Tests**: Each validation function tested independently
- **Integration Tests**: End-to-end validation scenarios  
- **Edge Cases**: Boundary conditions, malicious input
- **Performance Tests**: Large payment requests, many items
- **Backward Compatibility**: Legacy function behavior preserved

### Test Coverage

- ✅ Currency validation (valid/invalid codes, amounts)
- ✅ String validation (length, content, required fields)
- ✅ Payment request validation (methods, details, items)
- ✅ Mandate signature validation (authorization, signatures)
- ✅ Error serialization and deserialization
- ✅ Backward compatibility with existing code

## Migration Guide

### For Existing AP2 Implementations

1. **No immediate changes required** - backward compatibility maintained
2. **Gradual adoption** - start using enhanced validation where beneficial
3. **Error handling improvement** - leverage detailed error information

### For New Implementations

```python
# Use enhanced validation from the start
from ap2.validation import EnhancedValidator, ValidationResult

validator = EnhancedValidator()

def process_payment_request(request):
    # Validate request
    result = validator.validate_payment_request(request)
    
    if not result.is_valid:
        # Return structured error response
        return {
            "success": False,
            "errors": result.errors,
            "warnings": result.warnings
        }
    
    # Process valid request
    return process_valid_request(request)
```

## API Changes

### New Classes

- `AP2ErrorCode`: Enumeration of standardized error codes
- `AP2ValidationError`: Enhanced exception with structured information
- `ValidationResult`: Container for validation results and errors
- `EnhancedValidator`: Comprehensive validation class

### Modified Functions

- `validate_payment_mandate_signature()`: Added optional detailed result parameter

### No Breaking Changes

All existing function signatures and behavior preserved.

## Benefits

### For Developers

- **Better Debugging**: Detailed error information with field paths
- **Consistent Error Handling**: Standardized error codes across implementations
- **Security Assurance**: Built-in validation for common attack vectors
- **Documentation**: Error suggestions help fix issues quickly

### For Operations

- **Monitoring**: Standardized error codes for alerting and metrics
- **Troubleshooting**: Field-level error information speeds resolution
- **Security**: Structured logging for security analysis
- **Compliance**: Detailed audit trail for validation failures

### For End Users

- **Better Error Messages**: Clear explanations of what went wrong
- **Helpful Suggestions**: Guidance on how to fix issues
- **Faster Resolution**: Less back-and-forth with support

## Future Enhancements

### Planned Features

- **Async Validation**: Support for async validation of external dependencies
- **Custom Validators**: Plugin system for domain-specific validation rules
- **Validation Caching**: Cache validation results for repeated requests
- **Metrics Collection**: Built-in metrics for validation performance

### Extension Points

```python
class CustomValidator(EnhancedValidator):
    def validate_custom_payment_method(self, method_data):
        # Custom validation logic
        pass
    
    def validate_business_rules(self, request):
        # Business-specific validation
        pass
```

---

**This enhancement maintains full backward compatibility while providing comprehensive error handling and validation capabilities that benefit the entire AP2 ecosystem.**