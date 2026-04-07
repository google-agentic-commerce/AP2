import os
import sys
import types as _types
import unittest


ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
SAMPLES_SRC = os.path.join(ROOT, "samples", "python", "src")
AP2_SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SAMPLES_SRC)
sys.path.insert(0, AP2_SRC)


if "x402_a2a" not in sys.modules:
  _x402 = _types.ModuleType("x402_a2a")
  _x402_types = _types.ModuleType("x402_a2a.types")
  _x402_types.EIP3009Authorization = type("EIP3009Authorization", (), {})
  _x402_types.ExactPaymentPayload = type("ExactPaymentPayload", (), {})
  _x402_types.PaymentPayload = type("PaymentPayload", (), {})
  _x402.types = _x402_types
  sys.modules["x402_a2a"] = _x402
  sys.modules["x402_a2a.types"] = _x402_types


from ap2.types.mandate import PAYMENT_MANDATE_DATA_KEY
from ap2.types.mandate import PaymentMandate
from ap2.types.mandate import PaymentMandateContents
from ap2.types.payment_request import PaymentCurrencyAmount
from ap2.types.payment_request import PaymentItem
from ap2.types.payment_request import PaymentResponse
from roles.credentials_provider_agent import account_manager
from roles.credentials_provider_agent import tools


class _FakeUpdater:

  def __init__(self):
    self.artifacts = []
    self.completed = False

  async def add_artifact(self, parts):
    self.artifacts.append(parts)

  async def complete(self, message=None):
    self.completed = True


def _build_payment_mandate(token: str, payer_email: str) -> PaymentMandate:
  return PaymentMandate(
      payment_mandate_contents=PaymentMandateContents(
          payment_mandate_id="test-payment-mandate",
          payment_details_id="order-1",
          payment_details_total=PaymentItem(
              label="Total",
              amount=PaymentCurrencyAmount(currency="USD", value=1.0),
          ),
          payment_response=PaymentResponse(
              request_id="order-1",
              method_name="CARD",
              details={
                  "token": {
                      "value": token,
                      "url": "http://localhost:8002/a2a/credentials_provider",
                  }
              },
              payer_email=payer_email,
          ),
          merchant_agent="Generic Merchant",
      ),
      user_authorization="fake_cart_mandate_hash_cart_1_fake_payment_mandate_hash_test-payment-mandate",
  )


class CredentialsProviderSecurityTest(unittest.IsolatedAsyncioTestCase):

  async def asyncSetUp(self):
    account_manager._token.clear()

  async def test_processor_details_are_sanitized(self):
    token = account_manager.create_token(
        "bugsbunny@gmail.com", "American Express ending in 4444"
    )
    mandate = _build_payment_mandate(token, "bugsbunny@gmail.com")

    bind_updater = _FakeUpdater()
    await tools.handle_signed_payment_mandate(
        [{PAYMENT_MANDATE_DATA_KEY: mandate.model_dump()}],
        bind_updater,
        None,
    )

    raw_updater = _FakeUpdater()
    await tools.handle_get_payment_method_raw_credentials(
        [{PAYMENT_MANDATE_DATA_KEY: mandate.model_dump()}],
        raw_updater,
        None,
    )
    returned_data = raw_updater.artifacts[0][0].root.data

    self.assertEqual(returned_data["type"], "CARD")
    self.assertEqual(
        returned_data["alias"], "American Express ending in 4444"
    )
    self.assertEqual(
        returned_data["credential_reference"]["payment_credential_token"], token
    )
    self.assertNotIn("token", returned_data)
    self.assertNotIn("cryptogram", returned_data)
    self.assertNotIn("card_holder_name", returned_data)
    self.assertNotIn("card_expiration", returned_data)
    self.assertNotIn("card_billing_address", returned_data)

  async def test_signed_mandate_rejects_wrong_payer_email(self):
    token = account_manager.create_token(
        "bugsbunny@gmail.com", "American Express ending in 4444"
    )
    mandate = _build_payment_mandate(token, "daffyduck@gmail.com")

    with self.assertRaisesRegex(ValueError, "Invalid token"):
      await tools.handle_signed_payment_mandate(
          [{PAYMENT_MANDATE_DATA_KEY: mandate.model_dump()}],
          _FakeUpdater(),
          None,
      )


if __name__ == "__main__":
  unittest.main()
