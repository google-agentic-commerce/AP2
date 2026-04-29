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

"""Tests for AP2 mandate models."""

import json

from ap2.models.mandate import IntentMandate
from ap2.models.payment_request import PaymentCurrencyAmount


def test_intent_mandate_budget_is_optional():
    """IntentMandate can be created without a budget."""
    mandate = IntentMandate(
        natural_language_description='Red basketball shoes',
        intent_expiry='2026-12-31T00:00:00Z',
    )
    assert mandate.budget is None


def test_intent_mandate_budget_can_be_set():
    """IntentMandate accepts a PaymentCurrencyAmount budget."""
    budget = PaymentCurrencyAmount(currency='USD', value=150.00)
    mandate = IntentMandate(
        natural_language_description='Red basketball shoes',
        intent_expiry='2026-12-31T00:00:00Z',
        budget=budget,
    )
    assert mandate.budget is not None
    assert mandate.budget.currency == 'USD'
    assert mandate.budget.value == 150.00


def test_intent_mandate_budget_serializes_to_json():
    """Budget field serializes correctly in JSON output."""
    budget = PaymentCurrencyAmount(currency='EUR', value=200.00)
    mandate = IntentMandate(
        natural_language_description='Concert tickets',
        intent_expiry='2026-06-01T00:00:00Z',
        budget=budget,
    )
    data = json.loads(mandate.model_dump_json())
    assert data['budget'] == {'currency': 'EUR', 'value': 200.00}


def test_intent_mandate_budget_absent_omitted_from_json():
    """Budget field is absent from JSON when not set."""
    mandate = IntentMandate(
        natural_language_description='Groceries',
        intent_expiry='2026-01-01T00:00:00Z',
    )
    data = json.loads(mandate.model_dump_json(exclude_none=True))
    assert 'budget' not in data


def test_intent_mandate_budget_round_trip():
    """IntentMandate with budget survives a JSON round-trip."""
    budget = PaymentCurrencyAmount(currency='GBP', value=75.50)
    original = IntentMandate(
        natural_language_description='Books',
        intent_expiry='2026-03-01T00:00:00Z',
        budget=budget,
    )
    serialized = original.model_dump_json()
    restored = IntentMandate.model_validate_json(serialized)
    assert restored.budget is not None
    assert restored.budget.currency == 'GBP'
    assert restored.budget.value == 75.50


def test_intent_mandate_budget_zero_value_allowed():
    """Budget of zero is a valid (if unusual) value."""
    budget = PaymentCurrencyAmount(currency='USD', value=0.0)
    mandate = IntentMandate(
        natural_language_description='Free items only',
        intent_expiry='2026-12-31T00:00:00Z',
        budget=budget,
    )
    assert mandate.budget is not None
    assert mandate.budget.value == 0.0
