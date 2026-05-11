"""Payment mandate chain processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ap2.sdk.constraints import MandateContext, check_payment_constraints
from ap2.sdk.generated.open_payment_mandate import OpenPaymentMandate
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.mandate import _log_event


# Typed payment chain is always (open_mandate, closed_mandate).
_PAYMENT_CHAIN_LEN = 2


@dataclass
class PaymentMandateChain:
    """Parsed payment mandate delegation chain (open + closed)."""

    open_mandate: OpenPaymentMandate
    closed_mandate: PaymentMandate

    @classmethod
    def parse(cls, payloads: list[dict[str, Any]]) -> PaymentMandateChain:
        """Parse two verified payloads into a typed payment chain."""
        if len(payloads) != _PAYMENT_CHAIN_LEN:
            raise ValueError(
                'Payment mandate chain requires exactly 2 payloads, '
                f'got {len(payloads)}'
            )
        return cls(
            open_mandate=OpenPaymentMandate.model_validate(payloads[0]),
            closed_mandate=PaymentMandate.model_validate(payloads[1]),
        )

    def verify(
        self,
        expected_transaction_id: str | None = None,
        expected_open_checkout_hash: str | None = None,
        mandate_context: MandateContext | None = None,
    ) -> list[str]:
        """Verifies the constraints of the payment mandate chain.

        Args:
          expected_transaction_id: Optional transaction ID to check against the
            closed mandate's transaction_id.
          expected_open_checkout_hash: Optional checkout hash to check against
            the open mandate's checkout_reference.
          mandate_context: Aggregated usage context for the mandate.

        Returns:
          A list of strings describing any violations found.
        """
        _log_event(
            'payment_mandate_chain.verify',
            'before',
            {
                'has_expected_transaction_id': expected_transaction_id
                is not None,
                'has_expected_open_checkout_hash': (
                    expected_open_checkout_hash is not None
                ),
                'has_mandate_context': mandate_context is not None,
            },
        )

        violations = check_payment_constraints(
            self.open_mandate,
            self.closed_mandate,
            open_checkout_hash=expected_open_checkout_hash,
            mandate_context=mandate_context,
        )
        if (
            expected_transaction_id is not None
            and expected_transaction_id != self.closed_mandate.transaction_id
        ):
            violations.append(
                'Payment transaction_id mismatch: expected'
                f' {expected_transaction_id}, got'
                f' {self.closed_mandate.transaction_id}'
            )

        _log_event(
            'payment_mandate_chain.verify',
            'after',
            {
                'success': len(violations) == 0,
                'violations': violations,
            },
        )
        return violations
