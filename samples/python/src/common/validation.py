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

"""Validation logic for PaymentMandate.

This module provides backward compatibility for existing validation functions
while leveraging the enhanced validation system for improved error handling.
"""

import logging
from typing import Optional

from ap2.types.mandate import PaymentMandate

# Import enhanced validation if available, fall back to simple validation
try:
    from ap2.validation.enhanced_validation import EnhancedValidator, ValidationResult
    _enhanced_validator = EnhancedValidator()
    _ENHANCED_VALIDATION_AVAILABLE = True
except ImportError:
    _ENHANCED_VALIDATION_AVAILABLE = False
    _enhanced_validator = None


def validate_payment_mandate_signature(
    payment_mandate: PaymentMandate,
    return_detailed_result: bool = False
) -> Optional[ValidationResult]:
  """Validates the PaymentMandate signature.

  Args:
    payment_mandate: The PaymentMandate to be validated.
    return_detailed_result: If True and enhanced validation is available,
        returns detailed ValidationResult instead of raising exceptions.

  Returns:
    ValidationResult if return_detailed_result=True and enhanced validation
    is available, otherwise None.

  Raises:
    ValueError: If the PaymentMandate signature is not valid and
        return_detailed_result=False.
  """
  if _ENHANCED_VALIDATION_AVAILABLE and return_detailed_result:
    # Use enhanced validation with detailed error information
    return _enhanced_validator.validate_payment_mandate_signature(payment_mandate)
  
  elif _ENHANCED_VALIDATION_AVAILABLE:
    # Use enhanced validation but maintain backward compatibility
    result = _enhanced_validator.validate_payment_mandate_signature(payment_mandate)
    if not result.is_valid:
      # Raise the first error for backward compatibility
      first_error = result.errors[0]
      raise ValueError(first_error['message'])
    
    logging.info("Valid PaymentMandate found with enhanced validation.")
    return None
  
  else:
    # Fallback to original simple validation
    if payment_mandate.user_authorization is None:
      raise ValueError("User authorization not found in PaymentMandate.")

    logging.info("Valid PaymentMandate found.")
    return None
