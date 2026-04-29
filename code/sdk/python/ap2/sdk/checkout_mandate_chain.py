"""Checkout mandate chain processing."""

from __future__ import annotations

import binascii
import json

from dataclasses import dataclass
from typing import Any

from ap2.sdk.constraints import check_checkout_constraints
from ap2.sdk.generated.checkout_mandate import CheckoutMandate
from ap2.sdk.generated.open_checkout_mandate import OpenCheckoutMandate
from ap2.sdk.generated.types.checkout import Checkout
from ap2.sdk.mandate import _log_event
from ap2.sdk.utils import b64url_decode
from pydantic import ValidationError


_CHECKOUT_CHAIN_LEN = 2
_JWT_COMPACT_PARTS = 3


@dataclass
class CheckoutMandateChain:
    """Parsed checkout mandate delegation chain (open + closed)."""

    open_mandate: OpenCheckoutMandate
    closed_mandate: CheckoutMandate

    @classmethod
    def parse(cls, payloads: list[dict[str, Any]]) -> CheckoutMandateChain:
        """Parse two verified payloads into a typed checkout chain."""
        if len(payloads) != _CHECKOUT_CHAIN_LEN:
            raise ValueError(
                'Checkout mandate chain requires exactly 2 payloads, '
                f'got {len(payloads)}'
            )
        return cls(
            open_mandate=OpenCheckoutMandate.model_validate(payloads[0]),
            closed_mandate=CheckoutMandate.model_validate(payloads[1]),
        )

    def verify(
        self,
        expected_checkout_hash: str | None = None,
        checkout_jwt: str | None = None,
    ) -> list[str]:
        """Verifies the constraints of the checkout mandate chain.

        Args:
          expected_checkout_hash: An optional hash to check against the closed
            mandate's checkout_hash.
          checkout_jwt: The JWT containing the checkout details, required for
            verifying open mandate constraints.

        Returns:
          A list of strings describing any violations found.
        """
        _log_event(
            'checkout_mandate_chain.verify',
            'before',
            {
                'has_expected_checkout_hash': expected_checkout_hash
                is not None,
                'has_checkout_jwt': checkout_jwt is not None,
            },
        )

        violations = []

        if not checkout_jwt:
            violations.append(
                'checkout_jwt is required to verify checkout constraints.'
            )
            return violations

        # Safely extract and validate the JWT
        try:
            checkout = self.extract_parsed_checkout_object(checkout_jwt)
        except ValueError as e:
            violations.append(str(e))
            return violations

        violations.extend(
            check_checkout_constraints(
                self.open_mandate,
                checkout,
            )
        )

        if (
            expected_checkout_hash is not None
            and expected_checkout_hash != self.closed_mandate.checkout_hash
        ):
            violations.append(
                'Checkout checkout_hash mismatch: expected'
                f' {expected_checkout_hash}, got'
                f' {self.closed_mandate.checkout_hash}'
            )

        _log_event(
            'checkout_mandate_chain.verify',
            'after',
            {
                'success': len(violations) == 0,
                'violations': violations,
            },
        )
        return violations

    def extract_parsed_checkout_object(self, checkout_jwt: str) -> Checkout:
        """Extracts Checkout object from the checkout_jwt payload."""
        parts = checkout_jwt.split('.')
        if len(parts) != _JWT_COMPACT_PARTS:
            raise ValueError(
                'Malformed checkout_jwt: expected header.payload.signature'
            )

        payload_b64 = parts[1]

        try:
            decoded_bytes = b64url_decode(payload_b64)
            jwt_payload = json.loads(decoded_bytes)
            return Checkout.model_validate(jwt_payload)
        except binascii.Error as e:
            raise ValueError(
                f'Base64 decoding failed for checkout_jwt: {e}'
            ) from e
        except json.JSONDecodeError as e:
            raise ValueError(
                f'Invalid JSON in checkout_jwt payload: {e}'
            ) from e
        except ValidationError as e:
            raise ValueError(
                f'checkout_jwt payload failed schema validation: {e}'
            ) from e
