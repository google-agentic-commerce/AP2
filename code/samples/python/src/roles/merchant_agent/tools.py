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

"""Tools used by the merchant agent.

Each agent uses individual tools to handle distinct tasks throughout the
shopping and purchasing process.
"""

import base64
import hashlib
import json
import logging
import os
import time
import uuid

from typing import Any

from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import DataPart, Part, Task, TextPart
from ap2.sdk.generated.checkout_mandate import CheckoutMandate
from ap2.sdk.generated.payment_receipt import PaymentReceipt
from ap2.sdk.generated.types.checkout import Checkout, Status
from ap2.sdk.generated.types.item import Item
from ap2.sdk.generated.types.line_item import LineItem
from ap2.sdk.generated.types.link import Link
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.total import Total
from ap2.sdk.mandate import MandateClient
from ap2.sdk.sdjwt.chain import X5cOrKidPublicKeyProvider
from common import artifact_utils, message_utils
from common.a2a_extension_utils import EXTENSION_URI
from common.a2a_message_builder import A2aMessageBuilder
from common.constants import (
  CHECKOUT_MANDATE_SD_JWT_KEY,
  PAYMENT_MANDATE_SD_JWT_KEY,
  PAYMENT_RECEIPT_DATA_KEY,
)
from common.payment_remote_a2a_client import PaymentRemoteA2aClient
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.serialization import (
  Encoding,
  NoEncryption,
  PrivateFormat,
  load_pem_private_key,
  load_pem_public_key,
)
from jwcrypto.jwk import JWK
from pydantic import ValidationError

from . import storage


_PAYMENT_PROCESSOR_URL = (
    "http://localhost:8003/a2a/merchant_payment_processor_agent"
)

_MERCHANT_NAME = "Generic Merchant"
_MERCHANT_ID = "merchant_1"
_MERCHANT_WEBSITE = "https://demo-merchant.example"
_MERCHANT_AUD = "https://merchant.com"
_MERCHANT_NONCE = "merchant-nonce-xyz"
_MERCHANT_KEY_PATH = os.environ.get("MERCHANT_SIGNING_KEY_PATH", "")
_AGENT_PROVIDER_PUB_KEY_PATH = os.environ.get(
    "AGENT_PROVIDER_PUBLIC_KEY_PATH", ""
)


def _b64url_encode(data: bytes) -> str:
  return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _compute_sha256_b64url(data: str) -> str:
  return _b64url_encode(hashlib.sha256(data.encode()).digest())


def _get_merchant_signing_key() -> ec.EllipticCurvePrivateKey:
  """Gets or generates the merchant's ECC signing key.

  Loads the key from a PEM file if it exists, otherwise generates a new
  SECP256R1 private key.

  Returns:
    The merchant's ECC private signing key.
  """
  if _MERCHANT_KEY_PATH and os.path.exists(_MERCHANT_KEY_PATH):
    try:
      return load_pem_private_key(
          open(_MERCHANT_KEY_PATH, "rb").read(), password=None
      )
    except (OSError, ValueError, TypeError):
      logging.warning(
          "Failed to load merchant signing key from %s", _MERCHANT_KEY_PATH
      )
  key = ec.generate_private_key(ec.SECP256R1())
  if _MERCHANT_KEY_PATH:
    os.makedirs(os.path.dirname(_MERCHANT_KEY_PATH) or ".", exist_ok=True)
    with open(_MERCHANT_KEY_PATH, "wb") as f:
      f.write(
          key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
      )
  return key


def _create_jwt(
    header: dict[str, Any],
    payload: dict[str, Any],
    private_key: ec.EllipticCurvePrivateKey,
) -> str:
  h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
  p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
  signing_input = f"{h}.{p}".encode("ascii")
  der_sig = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
  r, s = decode_dss_signature(der_sig)
  sig_bytes = r.to_bytes(32, "big") + s.to_bytes(32, "big")
  return f"{h}.{p}.{_b64url_encode(sig_bytes)}"


async def create_checkout(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
    debug_mode: bool = False,
) -> None:
  """Create a checkout.

  Use this tool when the request says 'create a checkout' or 'create checkout'.
  Creates a merchant-signed checkout JWT for a selected cart.

  Args:
    data_parts: A list of data part contents from the request.
    updater: The TaskUpdater instance to add artifacts and complete the task.
    current_task: The current task object.
    debug_mode: Whether to run in debug mode. Defaults to False.
  """
  cart_id = message_utils.find_data_part("cart_id", data_parts)
  if not cart_id:
    await _fail_task(updater, "Missing cart_id.")
    return

  cart_data = storage.get_cart_data(cart_id)
  if not cart_data:
    await _fail_task(updater, f"Cart not found for cart_id: {cart_id}")
    return

  merchant_key = _get_merchant_signing_key()
  now = int(time.time())
  amount_cents = int(round(cart_data["amount"] * 100))

  merchant = Merchant(
      id=_MERCHANT_ID,
      name=_MERCHANT_NAME,
      website=_MERCHANT_WEBSITE,
  )

  line_items = [
      LineItem(
          id=f"li_{uuid.uuid4().hex}",
          item=Item(
              id=cart_id,
              title=cart_data.get("item_label", ""),
              price=amount_cents,
          ),
          quantity=1,
          totals=[
              Total(type="subtotal", amount=amount_cents),
              Total(type="total", amount=amount_cents),
          ],
      )
  ]

  checkout = Checkout(
      id=cart_id,
      merchant=merchant,
      line_items=line_items,
      status=Status.incomplete,
      currency=cart_data.get("currency", "USD"),
      totals=[
          Total(type="subtotal", amount=amount_cents),
          Total(type="total", amount=amount_cents),
      ],
      links=[
          Link(type="privacy_policy", url=f"{_MERCHANT_WEBSITE}/privacy"),
      ],
  )

  checkout_payload = checkout.model_dump(mode="json", exclude_none=True)
  checkout_payload["iat"] = now
  checkout_payload["exp"] = now + 3600
  header = {"alg": "ES256", "typ": "JWT", "kid": "merchant-key-1"}
  checkout_jwt = _create_jwt(header, checkout_payload, merchant_key)
  checkout_hash = _compute_sha256_b64url(checkout_jwt)

  risk_data = storage.get_risk_data(updater.context_id)

  await updater.add_artifact([
      Part(
          root=DataPart(
              data={
                  "ap2.checkout": {
                      "cart_id": cart_id,
                      "checkout_jwt": checkout_jwt,
                      "checkout_hash": checkout_hash,
                      "item_label": cart_data.get("item_label", ""),
                      "amount": cart_data["amount"],
                      "amount_cents": amount_cents,
                      "currency": cart_data.get("currency", "USD"),
                  }
              }
          )
      ),
      Part(root=DataPart(data={"risk_data": risk_data or ""})),
  ])
  await updater.complete()


async def initiate_payment(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
    debug_mode: bool = False,
) -> None:
  """Initiate a payment.

  Use this tool when the request says 'initiate_payment' or 'initiate a
  payment'. Forwards payment mandate SD-JWTs to the payment processor.

  Args:
    data_parts: A list of data part contents from the request.
    updater: The TaskUpdater instance to add artifacts and complete the task.
    current_task: The current task object.
    debug_mode: Whether to run in debug mode. Defaults to False.
  """
  payment_mandate_sdjwt = message_utils.find_data_part(
      PAYMENT_MANDATE_SD_JWT_KEY, data_parts
  )
  if not payment_mandate_sdjwt:
    await _fail_task(updater, "Missing PaymentMandate SD-JWT.")
    return

  checkout_mandate_sdjwt = message_utils.find_data_part(
      CHECKOUT_MANDATE_SD_JWT_KEY, data_parts
  )
  if checkout_mandate_sdjwt:
    try:
      _verify_checkout_mandate(checkout_mandate_sdjwt)
    except ValueError as e:
      await _fail_task(updater, f"CheckoutMandate verification failed: {e}")
      return

  risk_data = message_utils.find_data_part("risk_data", data_parts)
  if not risk_data:
    await _fail_task(updater, "Missing risk_data.")
    return

  payment_processor_agent = PaymentRemoteA2aClient(
      name="payment_processor_agent",
      base_url=_PAYMENT_PROCESSOR_URL,
      required_extensions={EXTENSION_URI},
  )

  message_builder = (
      A2aMessageBuilder()
      .set_context_id(updater.context_id)
      .add_text("initiate_payment")
      .add_data(PAYMENT_MANDATE_SD_JWT_KEY, payment_mandate_sdjwt)
      .add_data("risk_data", risk_data)
      .add_data("debug_mode", debug_mode)
  )
  if checkout_mandate_sdjwt:
    message_builder.add_data(
        CHECKOUT_MANDATE_SD_JWT_KEY, checkout_mandate_sdjwt
    )

  challenge_response = (
      message_utils.find_data_part("challenge_response", data_parts) or ""
  )
  if challenge_response:
    message_builder.add_data("challenge_response", challenge_response)

  payment_processor_task_id = _get_payment_processor_task_id(current_task)
  if payment_processor_task_id:
    message_builder.set_task_id(payment_processor_task_id)

  task = await payment_processor_agent.send_a2a_message(message_builder.build())

  payment_receipts = artifact_utils.find_canonical_objects(
      task.artifacts, PAYMENT_RECEIPT_DATA_KEY, PaymentReceipt
  )
  if payment_receipts:
    payment_receipt = artifact_utils.only(payment_receipts)
    await updater.add_artifact([
        Part(
            root=DataPart(
                data={PAYMENT_RECEIPT_DATA_KEY: payment_receipt.model_dump()}
            )
        )
    ])

  await updater.update_status(
      state=task.status.state,
      message=task.status.message,
  )


async def dpc_finish(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Receives and validates a DPC response to finalize payment.

  Use this tool when the request says 'Finish the DPC flow' or 'complete the
  purchase' or contains a 'checkout_mandate'.

  This tool receives the Digital Payment Credential (DPC) response, in the form
  of an OpenID4VP JSON, validates it, and simulates payment finalization.

  Args:
    data_parts: A list of data part contents from the request.
    updater: The TaskUpdater instance to add artifacts and complete the task.
    current_task: The current task, not used in this function.
  """
  checkout_mandate_str = message_utils.find_data_part(
      "checkout_mandate", data_parts
  )
  if not checkout_mandate_str:
    await _fail_task(updater, "Missing checkout_mandate.")
    return
  logging.info("Received Checkout Mandate for finalization.")

  try:
    mandate = _verify_checkout_mandate(checkout_mandate_str)
    logging.info("Checkout Mandate verified: %s", mandate)
  except ValueError as e:
    logging.exception("Checkout Mandate verification failed")
    await _fail_task(updater, f"Checkout Mandate verification failed: {e}")
    return
  await updater.add_artifact([
      Part(root=DataPart(data={
          "payment_status": "SUCCESS",
          "transaction_id": "txn_1234567890",
      }))
  ])
  await updater.complete()


def _verify_checkout_mandate(sdjwt: str) -> CheckoutMandate:
  """Verify a CheckoutMandate SD-JWT using the agent-provider public key.

  Supports two modes:
    - **Chain (DPC immediate):**
    ``DPC_sdjwt~~KB-SD-JWT~mandate_disc~agent_KB-JWT``
      — three-level delegation: DPC ``cnf`` → wallet key → KB-SD-JWT ``cnf``
      → agent key → agent KB-JWT.  The agent KB-JWT carries pre-shared
      audience and nonce.
    - **Single token (HNP / standard):** Verified as a standalone SD-JWT with
      pre-shared audience and nonce.

  Args:
    sdjwt: The CheckoutMandate SD-JWT string, potentially in a chain format.

  Returns:
    The verified CheckoutMandate object.

  Raises:
    ValueError: If the agent-provider public key is not found or if the SD-JWT
      chain is malformed.
    Exception: If the CheckoutMandate verification or validation fails.
  """
  if not _AGENT_PROVIDER_PUB_KEY_PATH or not os.path.exists(
      _AGENT_PROVIDER_PUB_KEY_PATH
  ):
    raise ValueError("Agent-provider public key not found")
  pub_key = load_pem_public_key(open(_AGENT_PROVIDER_PUB_KEY_PATH, "rb").read())

  tools_dir = os.path.dirname(os.path.abspath(__file__))
  samples_root = os.path.abspath(
      os.path.join(tools_dir, "..", "..", "..", "..")
  )
  certs_dir = os.path.join(samples_root, "certs")
  trusted_root_path = os.path.join(certs_dir, "issuer_cert_sdjwt.pem")

  trusted_roots = []
  if os.path.exists(trusted_root_path):
    with open(trusted_root_path, "rb") as f:
      trusted_root = x509.load_pem_x509_certificate(f.read())
      trusted_roots.append(trusted_root)
      logging.info("Loaded trusted root cert: %s", trusted_root_path)
  else:
    logging.error("Trusted root cert not found at %s", trusted_root_path)

  if "~~" in sdjwt:
    tokens = sdjwt.split("~~")
    if len(tokens) < 2:
      raise ValueError(f"Expected at least 2 tokens in chain, got {len(tokens)}")

    # DPC immediate mode: token[0] is the DPC credential, token[1] is
    # the KB-SD-JWT (mandate disclosures).
    payloads = MandateClient().verify(
        token=sdjwt,
        key_or_provider=X5cOrKidPublicKeyProvider(
            lambda _kid: JWK.from_pyca(pub_key),
            trusted_roots=trusted_roots,
        ),
        expected_aud=_MERCHANT_AUD,
        expected_nonce=_MERCHANT_NONCE,
    )

    logging.info(
        "CheckoutMandate chain verified: payloads=%s",
        payloads,
    )
    # payloads[0] is DPC payload, payloads[1] is the closed mandate
    try:
      return CheckoutMandate.model_validate(payloads[1])
    except ValidationError as e:
      logging.warning(
          "Failed to validate payloads[1] as CheckoutMandate,"
          " returning raw dict: %s",
          e,
      )
      return payloads[1]
  else:
    verified = MandateClient().verify(
        token=sdjwt,
        key_or_provider=JWK.from_pyca(pub_key),
        payload_type=CheckoutMandate,
    )
    logging.info(
        "CheckoutMandate verified: checkout_hash=%s",
        verified.mandate_payload.checkout_hash,
    )
    return verified.mandate_payload


def _get_payment_processor_task_id(task: Task | None) -> str | None:
  """Returns the task ID of the payment processor task, if it exists.

  Identified by assuming the first message with a task ID that is not the
  merchant's task ID is a payment processor message.

  Args:
    task: The current task object.

  Returns:
    The task ID of the payment processor task, or None if not found.
  """
  if task is None:
    return None
  for message in task.history:
    if message.task_id != task.id:
      return message.task_id
  return None


async def _fail_task(updater: TaskUpdater, error_text: str) -> None:
  """A helper function to fail a task with a given error message."""
  error_message = updater.new_agent_message(
      parts=[Part(root=TextPart(text=error_text))]
  )
  await updater.failed(message=error_message)
