"""Validation of payment constraint payloads before generated model parsing."""

from collections.abc import Iterable, Mapping

from pydantic import ValidationInfo


def require_payment_constraint_types(
    value: object, _info: ValidationInfo
) -> object:
    """Require explicit types before defaults hide unrecognized constraints."""
    if not isinstance(value, Iterable) or isinstance(
        value, (str, bytes, bytearray, Mapping)
    ):
        return value

    constraints = list(value)
    for constraint in constraints:
        if isinstance(constraint, Mapping) and 'type' not in constraint:
            raise ValueError(
                'Payment constraint objects must declare their type.'
            )
    return constraints
