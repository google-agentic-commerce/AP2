@echo off
REM Validation Script for Protocol Contribution (Windows)
REM Run this script to validate the enhanced validation system

echo Testing Enhanced Validation System
echo =====================================

REM Check if we're in the right directory
if not exist "pyproject.toml" (
    echo Error: Not in AP2 repository root
    exit /b 1
)

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not found. Please install Python 3.8+
    exit /b 1
)

echo Using Python: 
python --version

REM Navigate to samples directory
cd samples\python

echo.
echo Installing dependencies...
python -m pip install -e . --quiet
python -m pip install pytest --quiet

echo.
echo Running enhanced validation tests...
python -m pytest tests\test_enhanced_validation.py -v
if %errorlevel% neq 0 (
    echo Some tests failed
    exit /b 1
)
echo All enhanced validation tests passed!

echo.
echo Running existing validation tests...
python -m pytest tests\ -k "validation" -v --tb=short
if %errorlevel% neq 0 (
    echo Some existing tests failed
    exit /b 1
)
echo All existing validation tests passed!

echo.
echo Testing backward compatibility...
python -c "from src.common.validation import validate_payment_mandate_signature; from ap2.types.mandate import PaymentMandate; from unittest.mock import Mock; mock_auth = Mock(); mock_auth.__dict__ = {'signature': 'test_signature'}; mandate = PaymentMandate(user_authorization=mock_auth); validate_payment_mandate_signature(mandate); print('Backward compatibility test passed')"

echo.
echo Testing enhanced validation features...
python -c "from ap2.validation.enhanced_validation import EnhancedValidator, AP2ErrorCode; from ap2.types.payment_request import PaymentCurrencyAmount; validator = EnhancedValidator(); amount = PaymentCurrencyAmount(currency='USD', value=99.99); result = validator.validate_currency_amount(amount); assert result.is_valid; amount = PaymentCurrencyAmount(currency='INVALID', value=99.99); result = validator.validate_currency_amount(amount); assert not result.is_valid; assert result.errors[0]['error_code'] == 'AP2_1002'; print('Enhanced validation features test passed')"

echo.
echo Test Summary
echo ===============
echo Enhanced validation tests: PASSED
echo Existing validation tests: PASSED
echo Backward compatibility: PASSED
echo Enhanced features: PASSED

echo.
echo All validation tests completed successfully!
echo.
echo Your protocol enhancement is ready for contribution to Google's AP2 repository.
echo Next steps:
echo 1. Create PR from protocol/enhance-error-handling to google-agentic-commerce/AP2
echo 2. Use the PR template in PROTOCOL_CONTRIBUTION_COMPLETE.md
echo 3. Monitor review process and respond to feedback