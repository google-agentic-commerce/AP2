#!/usr/bin/env python3
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

"""Test script to validate the generated JSON schemas."""

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError as e:
    print(f"Error importing jsonschema: {e}")
    print("\nPlease install jsonschema:")
    print("  pip install jsonschema --break-system-packages --user")
    print("  or: uv pip install jsonschema")
    sys.exit(1)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ap2.types.mandate import IntentMandate, CartMandate, PaymentMandate


def test_schema(schema_path: Path, example_instance: dict, name: str):
    """Test that a schema validates an example instance."""
    print(f"\nTesting {name}...")

    # Load schema
    with open(schema_path) as f:
        schema = json.load(f)

    # Validate the instance
    try:
        jsonschema.validate(instance=example_instance, schema=schema)
        print(f"  ✓ Schema is valid")
        print(f"  ✓ Example instance validates successfully")
        return True
    except jsonschema.exceptions.ValidationError as e:
        print(f"  ✗ Validation error: {e.message}")
        return False
    except jsonschema.exceptions.SchemaError as e:
        print(f"  ✗ Schema error: {e.message}")
        return False


def main():
    schemas_dir = Path(__file__).parent.parent / "schemas"

    print("=" * 60)
    print("AP2 JSON Schema Validation Test")
    print("=" * 60)

    # Test IntentMandate
    intent_example = {
        "natural_language_description": "High top, old school, red basketball shoes",
        "intent_expiry": "2025-12-31T23:59:59Z",
        "user_cart_confirmation_required": True,
        "merchants": ["example-merchant.com"],
        "requires_refundability": True
    }

    intent_result = test_schema(
        schemas_dir / "intent-mandate.schema.json",
        intent_example,
        "IntentMandate"
    )

    # Test CartMandate
    cart_example = {
        "contents": {
            "id": "cart-123",
            "user_cart_confirmation_required": True,
            "payment_request": {
                "method_data": [
                    {
                        "supported_methods": "https://example.com/pay",
                        "data": {}
                    }
                ],
                "details": {
                    "id": "payment-req-123",
                    "total": {
                        "label": "Total",
                        "amount": {
                            "currency": "USD",
                            "value": 99.99
                        }
                    },
                    "display_items": []
                }
            },
            "cart_expiry": "2025-12-20T23:59:59Z",
            "merchant_name": "Example Merchant"
        },
        "merchant_authorization": None
    }

    cart_result = test_schema(
        schemas_dir / "cart-mandate.schema.json",
        cart_example,
        "CartMandate"
    )

    # Test PaymentMandate
    payment_example = {
        "payment_mandate_contents": {
            "payment_mandate_id": "pm-123",
            "payment_details_id": "pd-123",
            "payment_details_total": {
                "label": "Total",
                "amount": {
                    "currency": "USD",
                    "value": 99.99
                }
            },
            "payment_response": {
                "request_id": "payment-req-123",
                "method_name": "https://example.com/pay",
                "details": {}
            },
            "merchant_agent": "merchant-agent-123",
            "timestamp": "2025-12-18T10:00:00Z"
        },
        "user_authorization": None
    }

    payment_result = test_schema(
        schemas_dir / "payment-mandate.schema.json",
        payment_example,
        "PaymentMandate"
    )

    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    print(f"  IntentMandate:  {'✓ PASS' if intent_result else '✗ FAIL'}")
    print(f"  CartMandate:    {'✓ PASS' if cart_result else '✗ FAIL'}")
    print(f"  PaymentMandate: {'✓ PASS' if payment_result else '✗ FAIL'}")
    print("=" * 60)

    if all([intent_result, cart_result, payment_result]):
        print("\n✓ All schemas validated successfully!")
        return 0
    else:
        print("\n✗ Some schemas failed validation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
