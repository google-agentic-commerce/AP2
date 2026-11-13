"""Regression tests for parsing payment constraints from untrusted payloads."""

import json

import pytest

from ap2.sdk.generated.open_payment_mandate import (
    AgentRecurrence,
    AllowedPayees,
    AllowedPaymentInstruments,
    AllowedPisps,
    AmountRange,
    Budget,
    ExecutionDate,
    OpenPaymentMandate,
    PaymentReference,
)
from pydantic import ValidationError


_CONSTRAINT_CASES = [
    pytest.param(
        AgentRecurrence,
        {'type': 'payment.agent_recurrence', 'frequency': 'MONTHLY'},
        id='agent_recurrence',
    ),
    pytest.param(
        AllowedPayees,
        {
            'type': 'payment.allowed_payees',
            'allowed': [{'id': 'merchant-1', 'name': 'Shop'}],
        },
        id='allowed_payees',
    ),
    pytest.param(
        AllowedPaymentInstruments,
        {
            'type': 'payment.allowed_payment_instruments',
            'allowed': [{'id': 'instrument-1', 'type': 'credit'}],
        },
        id='allowed_payment_instruments',
    ),
    pytest.param(
        AllowedPisps,
        {
            'type': 'payment.allowed_pisps',
            'allowed': [
                {
                    'legal_name': 'Example PISP',
                    'brand_name': 'Example',
                    'domain_name': 'pisp.example',
                }
            ],
        },
        id='allowed_pisps',
    ),
    pytest.param(
        AmountRange,
        {'type': 'payment.amount_range', 'currency': 'BRL', 'max': 5000},
        id='amount_range',
    ),
    pytest.param(
        Budget,
        {'type': 'payment.budget', 'currency': 'BRL', 'max': 50.0},
        id='budget',
    ),
    pytest.param(
        ExecutionDate,
        {'type': 'payment.execution_date'},
        id='execution_date_without_bounds',
    ),
    pytest.param(
        PaymentReference,
        {
            'type': 'payment.reference',
            'conditional_transaction_id': 'checkout-digest',
        },
        id='payment_reference',
    ),
]


def _payload(constraint):
    """Include a valid checkout reference alongside the constraint under test."""
    return {
        'vct': 'mandate.payment.open.1',
        'cnf': {},
        'constraints': [
            {
                'type': 'payment.reference',
                'conditional_transaction_id': 'checkout-digest',
            },
            constraint,
        ],
    }


def _parse(payload, input_format):
    if input_format == 'json':
        return OpenPaymentMandate.model_validate_json(json.dumps(payload))
    return OpenPaymentMandate.model_validate(payload)


@pytest.mark.parametrize('input_format', ['python', 'json'])
@pytest.mark.parametrize(
    'constraint',
    [
        pytest.param({}, id='empty_object'),
        pytest.param({'foo': 'bar'}, id='unrecognized_fields'),
        pytest.param({'type': 'payment.unknown'}, id='unknown_type'),
        pytest.param({'type': None}, id='null_type'),
        pytest.param({'type': 123}, id='non_string_type'),
        pytest.param('payment.execution_date', id='non_object'),
    ],
)
def test_rejects_unrecognized_payment_constraint(constraint, input_format):
    """Unknown constraints must not become an unconstrained ExecutionDate."""
    with pytest.raises(ValidationError):
        _parse(_payload(constraint), input_format)


@pytest.mark.parametrize('input_format', ['python', 'json'])
@pytest.mark.parametrize('constraint_type,payload', _CONSTRAINT_CASES)
def test_requires_payment_constraint_type(
    constraint_type, payload, input_format
):
    """Every wire constraint must explicitly declare its type discriminator."""
    without_type = {
        key: value for key, value in payload.items() if key != 'type'
    }
    with pytest.raises(ValidationError):
        _parse(_payload(without_type), input_format)


@pytest.mark.parametrize('input_format', ['python', 'json'])
@pytest.mark.parametrize('constraint_type,payload', _CONSTRAINT_CASES)
def test_valid_payment_constraint_round_trip(
    constraint_type, payload, input_format
):
    """Known wire constraints retain their type and values after serialization."""
    mandate = _parse(_payload(payload), input_format)
    assert isinstance(mandate.constraints[1], constraint_type)
    assert (
        mandate.constraints[1].model_dump(mode='json', exclude_none=True)
        == payload
    )
    restored = OpenPaymentMandate.model_validate_json(mandate.model_dump_json())
    assert isinstance(restored.constraints[1], constraint_type)
    assert restored == mandate


@pytest.mark.parametrize('constraint_type,payload', _CONSTRAINT_CASES)
def test_typed_payment_constraint_keeps_default_type(constraint_type, payload):
    """SDK callers can still construct a typed constraint without repeating type."""
    without_type = {
        key: value for key, value in payload.items() if key != 'type'
    }
    constraint = constraint_type(**without_type)
    mandate = OpenPaymentMandate.model_validate(_payload(constraint))
    assert mandate.constraints[1] is constraint


@pytest.mark.parametrize('container', [tuple, iter], ids=['tuple', 'iterator'])
def test_iterable_payment_constraints_require_types(container):
    """Other supported iterable inputs must not bypass type validation."""
    payload = _payload({'foo': 'bar'})
    payload['constraints'] = container(payload['constraints'])
    with pytest.raises(ValidationError):
        OpenPaymentMandate.model_validate(payload)


@pytest.mark.parametrize('constraints', [None, 123, {'foo': 'bar'}])
def test_invalid_constraint_container_raises_validation_error(constraints):
    """Malformed containers still produce a Pydantic validation error."""
    payload = _payload({})
    payload['constraints'] = constraints
    with pytest.raises(ValidationError):
        OpenPaymentMandate.model_validate(payload)
