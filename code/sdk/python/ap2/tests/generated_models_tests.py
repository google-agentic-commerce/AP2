"""Tests for generated model metadata."""

import json

from pathlib import Path

import pytest

from ap2.sdk.generated.checkout_mandate import CheckoutMandate
from ap2.sdk.generated.open_checkout_mandate import OpenCheckoutMandate
from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate
from ap2.sdk.generated.payment_mandate import PaymentMandate


@pytest.mark.parametrize(
    'schema_name, model, expected_vct',
    [
        ('payment_mandate.json', PaymentMandate, 'mandate.payment.1'),
        (
            'open_payment_mandate.json',
            OpenPaymentMandate,
            'mandate.payment.open.1',
        ),
        ('checkout_mandate.json', CheckoutMandate, 'mandate.checkout.1'),
        (
            'open_checkout_mandate.json',
            OpenCheckoutMandate,
            'mandate.checkout.open.1',
        ),
    ],
)
def test_vct_descriptions_include_exact_versioned_value(
    schema_name,
    model,
    expected_vct,
):
    """Schema and generated model descriptions include the exact VCT value."""
    schema_path = (
        Path(__file__).resolve().parents[3] / 'schemas' / 'ap2' / schema_name
    )
    schema = json.loads(schema_path.read_text())
    schema_vct = schema['properties']['vct']
    model_vct = model.model_fields['vct']
    expected_reference = f"'{expected_vct}'"

    assert schema_vct['const'] == expected_vct
    assert expected_reference in schema_vct['description']
    assert model_vct.default == expected_vct
    assert expected_reference in model_vct.description
