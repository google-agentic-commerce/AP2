# Security Advisory: PaymentMandate Authorization Validation

## Summary

A critical security vulnerability was identified and fixed in the AP2 protocol validation logic for `PaymentMandate.user_authorization` fields.

## Vulnerability Description

**CVE-2025-XXXX** (Placeholder - would be assigned by security team)

### Issue
The validation logic in `validate_payment_mandate_signature()` was incorrectly treating the `user_authorization` field as a parsed object with attributes like `signature` and `timestamp`, when according to the AP2 specification, this field should be:

> "a base64_url-encoded verifiable presentation of a verifiable credential signing over the cart_mandate and payment_mandate_hashes"

This means `user_authorization` should be a **base64url-encoded string** (like a JWT or SD-JWT-VC) that needs to be:
1. Decoded from base64url format
2. Parsed as a JWT structure  
3. Validated for proper claims and signatures

### Security Impact

**HIGH SEVERITY** - The incorrect validation could:
- ❌ **Bypass security validation**: Accept invalid authorization tokens
- ❌ **Allow object injection**: Accept arbitrary objects instead of signed tokens  
- ❌ **Skip cryptographic verification**: Never validate actual JWT signatures
- ❌ **Miss required claims**: Not enforce mandate-specific claims like `transaction_data`

### Affected Code

**Before (Vulnerable)**:
```python
# INCORRECT - treats user_authorization as object
if hasattr(payment_mandate.user_authorization, '__dict__'):
    auth_dict = payment_mandate.user_authorization.__dict__
    if 'signature' not in auth_dict:
        # This validation is meaningless for a string token!
```

**After (Fixed)**:
```python
# CORRECT - validates user_authorization as base64url-encoded string
if not isinstance(payment_mandate.user_authorization, str):
    raise ValueError("user_authorization must be base64url-encoded string")
    
# Parse and validate JWT structure
result = self._validate_authorization_token(payment_mandate.user_authorization)
```

## Fix Details

### Changes Made

1. **Type Validation**: Ensure `user_authorization` is a string, not an object
2. **JWT Parsing**: Properly decode base64url and parse JWT structure  
3. **Claim Validation**: Enforce required claims like `transaction_data`
4. **Algorithm Security**: Reject insecure algorithms like `none`
5. **Error Reporting**: Provide clear security-focused error messages

### New Validation Features

- ✅ **Base64url format validation**
- ✅ **JWT structure parsing** (header.payload.signature)
- ✅ **Required claim enforcement** (`transaction_data`, etc.)
- ✅ **Algorithm security checks** (reject `none` algorithm)
- ✅ **SD-JWT-VC format detection** for advanced use cases
- ✅ **Comprehensive error reporting** with security guidance

## Migration Guide

### For Developers

If you were previously passing object-like authorization:

```python
# OLD (INSECURE) - DO NOT USE
mandate = PaymentMandate(
    user_authorization={
        "signature": "some_sig",
        "timestamp": "2025-09-22T10:00:00Z"
    }
)
```

You must now provide a proper JWT string:

```python
# NEW (SECURE) - REQUIRED FORMAT
jwt_token = create_signed_jwt({
    "aud": "payment-processor",
    "nonce": "secure-random-nonce",
    "exp": 1727000000,
    "transaction_data": ["cart_hash", "mandate_hash"]
})

mandate = PaymentMandate(
    user_authorization=jwt_token  # base64url-encoded JWT string
)
```

### Testing Your Implementation

Use the provided validation script:

```bash
python validate_security_fix.py
```

This will test:
- ❌ Object-based auth (should fail)
- ✅ Proper JWT auth (should pass)  
- ❌ Invalid JWT format (should fail)
- ❌ Missing required claims (should fail)

## Timeline

- **2025-09-22**: Vulnerability identified during protocol enhancement review
- **2025-09-22**: Fix implemented and tested
- **2025-09-22**: Security advisory created
- **TBD**: Security patch released

## References

- [AP2 PaymentMandate Specification](../src/ap2/types/mandate.py)
- [Enhanced Validation Implementation](../src/ap2/validation/enhanced_validation.py)
- [Security Test Suite](../tests/test_enhanced_validation.py)
- [Validation Script](../validate_security_fix.py)

## Contact

For security-related questions about this fix:
- Protocol Team: [protocol-security@example.com]
- Security Team: [security@example.com]

---

**This advisory will be updated as the security patch is rolled out to production systems.**