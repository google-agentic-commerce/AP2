"""Tests for ReceiptClient in receipt_wrapper.py."""

from unittest import mock

from ap2.sdk.generated.checkout_receipt import CheckoutReceipt
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.payment_receipt import PaymentReceipt
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.generated.types.pisp import PISP
from ap2.sdk.jwt_helper import create_jwt
from ap2.sdk.receipt_wrapper import ReceiptClient
from cryptography.hazmat.primitives.asymmetric import ec
from jwcrypto.jwk import JWK


def _payment_mandate(pisp: PISP | None = None) -> PaymentMandate:
    """Build a minimal PaymentMandate with an optional PISP."""
    return PaymentMandate(
        transaction_id='tx_receipt',
        payee=Merchant(id='m-1', name='Shop'),
        payment_amount=Amount(amount=100, currency='USD'),
        payment_instrument=PaymentInstrument(id='pi-1', type='credit'),
        pisp=pisp,
    )


def test_create_payment_receipt(issuer_key):
    """Test creation of a PaymentReceipt when the mandate carries a PISP."""
    client = ReceiptClient()
    reference = 'test_reference'
    payment_mandate_content = _payment_mandate(
        pisp=PISP(
            legal_name='Example PISP Ltd.',
            brand_name='ExamplePay',
            domain_name='example.com',
        )
    )

    receipt = client.create_payment_receipt(payment_mandate_content, reference)

    assert isinstance(receipt, PaymentReceipt)
    assert receipt.root.iss == 'example.com'
    assert receipt.root.reference == reference
    assert receipt.root.status == 'Success'
    assert receipt.root.payment_id is not None
    assert receipt.root.psp_confirmation_id == receipt.root.payment_id


def test_create_payment_receipt_no_pisp(issuer_key):
    """Test creation of a PaymentReceipt when the mandate has no PISP."""
    client = ReceiptClient()
    reference = 'test_reference'
    payment_mandate_content = _payment_mandate(pisp=None)

    receipt = client.create_payment_receipt(payment_mandate_content, reference)

    assert receipt.root.iss == ''


def test_create_checkout_receipt():
    """Test creation of a CheckoutReceipt."""
    client = ReceiptClient()
    merchant = 'merchant_id'
    reference = 'test_reference'
    order_id = 'order_123'

    receipt = client.create_checkout_receipt(merchant, reference, order_id)

    assert isinstance(receipt, CheckoutReceipt)
    assert receipt.root.iss == merchant
    assert receipt.root.reference == reference
    assert receipt.root.order_id == order_id
    assert receipt.root.status == 'Success'


def test_verify_payment_receipt_success(issuer_key, issuer_public_key):
    """Test successful verification of a payment receipt."""
    client = ReceiptClient()
    reference = 'ref_123'
    # Create a real PaymentReceipt
    base_receipt = client._create_base_receipt(
        'Success', 'issuer.com', reference
    )
    payment_receipt = PaymentReceipt(
        **base_receipt,
        payment_id='pid_123',
        psp_confirmation_id='pid_123',
        network_confirmation_id='pid_123',
    )
    # Sign it into a JWT
    receipt_jwt = create_jwt(
        {'alg': 'ES256'}, payment_receipt.model_dump(), issuer_key
    )
    # Callback to simulate match in store
    has_ref_cb = mock.Mock(return_value=True)

    result = client.verify_receipt(
        receipt_jwt=receipt_jwt,
        receipt_issuer_public_key=issuer_public_key,
        has_reference_in_store_cb=has_ref_cb,
        is_payment_receipt=True,
    )

    assert result == {'verified': True}
    has_ref_cb.assert_called_once_with(reference)


def test_verify_checkout_receipt_success(issuer_key, issuer_public_key):
    """Test successful verification of a checkout receipt."""
    client = ReceiptClient()
    reference = 'ref_456'
    # Create a real CheckoutReceipt
    base_receipt = client._create_base_receipt(
        'Success', 'merchant.com', reference
    )
    checkout_receipt = CheckoutReceipt(**base_receipt, order_id='order_456')
    # Sign it into a JWT
    receipt_jwt = create_jwt(
        {'alg': 'ES256'}, checkout_receipt.model_dump(), issuer_key
    )
    has_ref_cb = mock.Mock(return_value=True)

    result = client.verify_receipt(
        receipt_jwt=receipt_jwt,
        receipt_issuer_public_key=issuer_public_key,
        has_reference_in_store_cb=has_ref_cb,
        is_payment_receipt=False,
    )

    assert result == {'verified': True}
    has_ref_cb.assert_called_once_with(reference)


def test_verify_receipt_invalid_signature(issuer_public_key):
    """Test verification failure with an invalid signature."""
    client = ReceiptClient()
    # Sign with a different key
    other_key_raw = ec.generate_private_key(ec.SECP256R1())
    other_key = JWK.from_pyca(other_key_raw)
    receipt_jwt = create_jwt({'alg': 'ES256'}, {'status': 'Success'}, other_key)

    result = client.verify_receipt(
        receipt_jwt=receipt_jwt,
        receipt_issuer_public_key=issuer_public_key,
        has_reference_in_store_cb=mock.Mock(),
    )

    assert 'error' in result
    assert result['error'] == 'verification_failed'
    assert 'JWT verification failed' in result['message']


def test_verify_receipt_not_found_in_store(issuer_key, issuer_public_key):
    """Test failure when receipt reference is not found in store."""
    client = ReceiptClient()
    reference = 'unknown_ref'
    base_receipt = client._create_base_receipt(
        'Success', 'issuer.com', reference
    )
    payment_receipt = PaymentReceipt(
        **base_receipt,
        payment_id='pid_123',
        psp_confirmation_id='pid_123',
        network_confirmation_id='pid_123',
    )
    receipt_jwt = create_jwt(
        {'alg': 'ES256'}, payment_receipt.model_dump(), issuer_key
    )
    # Callback returns False
    has_ref_cb = mock.Mock(return_value=False)

    result = client.verify_receipt(
        receipt_jwt=receipt_jwt,
        receipt_issuer_public_key=issuer_public_key,
        has_reference_in_store_cb=has_ref_cb,
        is_payment_receipt=True,
    )

    assert result['error'] == 'receipt_reference_not_found_in_store'
    has_ref_cb.assert_called_once_with(reference)


def test_verify_receipt_malformed_jwt(issuer_public_key):
    """Test failure with a malformed JWT."""
    client = ReceiptClient()

    result = client.verify_receipt(
        receipt_jwt='not.a.jwt',
        receipt_issuer_public_key=issuer_public_key,
        has_reference_in_store_cb=mock.Mock(),
    )

    assert result['error'] == 'verification_failed'
