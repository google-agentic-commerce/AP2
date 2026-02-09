#!/bin/bash

# Validation Script for Protocol Contribution
# Run this script to validate the enhanced validation system

set -e

echo "🧪 Testing Enhanced Validation System"
echo "====================================="

# Check if we're in the right directory
if [[ ! -f "pyproject.toml" ]]; then
    echo "❌ Error: Not in AP2 repository root"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "❌ Error: Python not found. Please install Python 3.8+"
    exit 1
fi

# Use python3 if available, otherwise python
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

echo "✅ Using Python: $($PYTHON_CMD --version)"

# Navigate to samples directory
cd samples/python

echo ""
echo "🔧 Installing dependencies..."
$PYTHON_CMD -m pip install -e . --quiet || true
$PYTHON_CMD -m pip install pytest --quiet || true

echo ""
echo "🧪 Running enhanced validation tests..."
if $PYTHON_CMD -m pytest tests/test_enhanced_validation.py -v; then
    echo "✅ All enhanced validation tests passed!"
else
    echo "❌ Some tests failed"
    exit 1
fi

echo ""
echo "🧪 Running existing validation tests..."
if $PYTHON_CMD -m pytest tests/ -k "validation" -v --tb=short; then
    echo "✅ All existing validation tests passed!"
else
    echo "❌ Some existing tests failed"
    exit 1
fi

echo ""
echo "🧪 Testing backward compatibility..."
$PYTHON_CMD -c "
from src.common.validation import validate_payment_mandate_signature
from ap2.types.mandate import PaymentMandate
from unittest.mock import Mock

# Test backward compatibility
mock_auth = Mock()
mock_auth.__dict__ = {'signature': 'test_signature'}
mandate = PaymentMandate(user_authorization=mock_auth)

try:
    validate_payment_mandate_signature(mandate)
    print('✅ Backward compatibility test passed')
except Exception as e:
    print(f'❌ Backward compatibility test failed: {e}')
    exit(1)
"

echo ""
echo "🧪 Testing enhanced validation features..."
$PYTHON_CMD -c "
try:
    from ap2.validation.enhanced_validation import EnhancedValidator, AP2ErrorCode
    from ap2.types.payment_request import PaymentCurrencyAmount
    
    validator = EnhancedValidator()
    
    # Test valid currency
    amount = PaymentCurrencyAmount(currency='USD', value=99.99)
    result = validator.validate_currency_amount(amount)
    assert result.is_valid, 'Valid currency test failed'
    
    # Test invalid currency
    amount = PaymentCurrencyAmount(currency='INVALID', value=99.99)
    result = validator.validate_currency_amount(amount)
    assert not result.is_valid, 'Invalid currency test failed'
    assert result.errors[0]['error_code'] == 'AP2_1002', 'Error code test failed'
    
    print('✅ Enhanced validation features test passed')
    
except ImportError as e:
    print(f'❌ Enhanced validation import failed: {e}')
    exit(1)
except Exception as e:
    print(f'❌ Enhanced validation test failed: {e}')
    exit(1)
"

echo ""
echo "📊 Test Summary"
echo "==============="
echo "✅ Enhanced validation tests: PASSED"
echo "✅ Existing validation tests: PASSED" 
echo "✅ Backward compatibility: PASSED"
echo "✅ Enhanced features: PASSED"

echo ""
echo "🎉 All validation tests completed successfully!"
echo ""
echo "Your protocol enhancement is ready for contribution to Google's AP2 repository."
echo "Next steps:"
echo "1. Create PR from protocol/enhance-error-handling to google-agentic-commerce/AP2"
echo "2. Use the PR template in PROTOCOL_CONTRIBUTION_COMPLETE.md"
echo "3. Monitor review process and respond to feedback"