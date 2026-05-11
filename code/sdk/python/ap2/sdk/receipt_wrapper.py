import datetime
import logging
import uuid

from collections.abc import Callable, Mapping
from typing import Any

from ap2.sdk.generated.checkout_receipt import CheckoutReceipt
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.payment_receipt import PaymentReceipt
from ap2.sdk.jwt_helper import verify_jwt
from cryptography.hazmat.primitives.asymmetric import ec


_logger = logging.getLogger(__name__)


class ReceiptClient:
    """A client for creating and verifying AP2 receipts."""

    def _create_base_receipt(
        self,
        status: str,
        issuer: str,
        reference: str,
    ) -> dict[str, Any]:
        """Creates a base receipt dictionary with common fields.

        Args:
          status: The status of the receipt (e.g., 'Success').
          issuer: The issuer of the receipt (e.g., merchant website).
          reference: The hash of the closed mandate this receipt is binding to.

        Returns:
          A dictionary containing the base receipt fields.
        """
        return {
            'status': status,
            'iss': issuer,
            'iat': int(datetime.datetime.now(datetime.UTC).timestamp()),
            'reference': reference,
        }

    def create_payment_receipt(
        self,
        payment_mandate_content: PaymentMandate,
        reference: str,
    ) -> PaymentReceipt:
        """Creates a PaymentReceipt model instance.

        Args:
          payment_mandate_content: The closed payment mandate whose PISP this
            receipt inherits as its issuer (when present).
          reference: The payment mandate reference this receipt binds to.

        Returns:
          A PaymentReceipt model instance.
        """
        payment_id = str(uuid.uuid4())
        issuer = (
            payment_mandate_content.pisp.domain_name
            if payment_mandate_content.pisp is not None
            else ''
        )
        base = self._create_base_receipt(
            status='Success',
            issuer=issuer,
            reference=reference,
        )
        return PaymentReceipt(
            **base,
            payment_id=payment_id,
            psp_confirmation_id=payment_id,
            network_confirmation_id=payment_id,
        )

    def create_checkout_receipt(
        self,
        merchant: str,
        reference: str,
        order_id: str,
    ) -> CheckoutReceipt:
        """Creates a CheckoutReceipt model instance.

        Args:
          merchant: The merchant completing the checkout.
          reference: The checkout mandate reference this receipt binds to.
          order_id: The unique identifier for the order.

        Returns:
          A CheckoutReceipt model instance.
        """
        base = self._create_base_receipt(
            status='Success',
            issuer=merchant,
            reference=reference,
        )
        return CheckoutReceipt(**base, order_id=order_id)

    def verify_receipt(
        self,
        receipt_jwt: str,
        receipt_issuer_public_key: ec.EllipticCurvePublicKey,
        has_reference_in_store_cb: Callable[[str], bool] | None = None,
        is_payment_receipt: bool = True,
    ) -> Mapping[str, Any]:
        """Verifies an AP2 receipt (payment or checkout).

        Verification includes:
        1) Verifying the ES256 signature of the receipt JWT using the
           receipt issuer's public key.
        2) Verifying the hash of the closed mandate in the receipt (reference)
           matches the hash of the closed mandate in the provided mandate chain.

        Args:
          receipt_jwt: The receipt JWT string to verify.
          receipt_issuer_public_key: The public key to verify the JWT signature.
          has_reference_in_store_cb: Optional callback to check if the receipt
            reference exists in the store.
          is_payment_receipt: Whether this is a payment or checkout receipt.

        Returns:
          A dictionary with the verification result (e.g., {"verified": True} or
          {"error": "..."}).
        """
        _logger.info(
            'verify_receipt called: is_payment_receipt=%s', is_payment_receipt
        )

        # 1. Verify signature
        try:
            payload = verify_jwt(receipt_jwt, receipt_issuer_public_key)
            if is_payment_receipt:
                receipt = PaymentReceipt.model_validate(payload)
            else:
                receipt = CheckoutReceipt.model_validate(payload)
        except Exception as e:
            _logger.warning('receipt verification failed: %s', e)
            return {
                'error': 'verification_failed',
                'message': f'JWT verification failed: {e}',
            }

        # 2. Verify receipt reference exists in the issuer's store
        receipt_reference = getattr(receipt.root, 'reference', None)
        if not has_reference_in_store_cb(receipt_reference):
            _logger.warning(
                'Receipt reference not found in store: %s',
                receipt_reference,
            )
            return {
                'error': 'receipt_reference_not_found_in_store',
                'message': (
                    'Receipt reference does not match any known closed '
                    'mandate for'
                    + (' payment' if is_payment_receipt else ' checkout')
                ),
            }

        _logger.info('Receipt verified successfully')
        return {'verified': True}
