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
        """Verifies the constraints and checkout binding of a payment chain.

        A closed Payment Mandate binds itself to the Checkout it authorizes via
        its ``transaction_id`` (the base64url hash of the Checkout JWT); the
        Security & Privacy model requires a verifier to confirm that binding
        against the checkout it is actually processing (see ``docs/ap2/
        security_and_privacy_considerations.md`` "Manipulated Checkout":
        "The Payment Mandate MUST contain a reference to its associated
        Checkout ... via ``transaction_id`` for closed Payment Mandates").

        This method therefore **fails closed**: a settlement verifier must pass
        ``expected_transaction_id``, and if it is absent or blank the closed
        binding cannot be confirmed and a violation is reported rather than the
        check being silently skipped. ``expected_transaction_id`` MUST be
        computed from the Checkout JWT the verifier is fulfilling; it MUST NOT
        be read back out of the chain (doing so makes the comparison a
        tautology and binds nothing).

        A caller that deliberately performs a **constraints-only** check that is
        not a settlement decision (for example offline policy analysis of an
        archived chain, where no checkout is being processed) has a bounded,
        honest exit: call :func:`ap2.sdk.constraints.check_payment_constraints`
        directly. That is a distinct, self-describing entry point, so it can
        never be mistaken for a full ``verify()`` in a call graph.

        Args:
          expected_transaction_id: The Checkout JWT hash the verifier is
            processing, checked against the closed mandate's ``transaction_id``.
            Required (non-empty) to confirm the closed checkout binding.
          expected_open_checkout_hash: Optional checkout hash to check against
            the open mandate's ``payment.reference`` constraint.
          mandate_context: Aggregated usage context for the mandate.

        Returns:
          A list of strings describing any violations found.
        """
        _log_event(
            'payment_mandate_chain.verify',
            'before',
            {
                'has_expected_transaction_id': bool(
                    expected_transaction_id and expected_transaction_id.strip()
                ),
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
        # Fail closed: an absent OR blank expected value binds nothing. Mirror
        # the falsy check the open-side PaymentReference evaluator already uses.
        if expected_transaction_id and expected_transaction_id.strip():
            if expected_transaction_id != self.closed_mandate.transaction_id:
                violations.append(
                    'Payment transaction_id mismatch: expected'
                    f' {expected_transaction_id}, got'
                    f' {self.closed_mandate.transaction_id}'
                )
        else:
            violations.append(
                'Closed Payment Mandate checkout binding not verified: a '
                'non-empty expected_transaction_id (the hash of the Checkout '
                'JWT being processed) is required to bind the closed mandate '
                'to its checkout. For a constraints-only check that is not a '
                'settlement decision, call check_payment_constraints() '
                'directly.'
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
