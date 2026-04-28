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

"""Tools used by the Shopping Agent.

Each agent uses individual tools to handle distinct tasks throughout the
shopping and purchasing process. Mandates are created as SD-JWTs using the
AP2 SDK (CheckoutMandate + PaymentMandate).
"""

import json
import logging
import os
import time

from typing import Any

from ap2.sdk.generated.checkout_mandate import CheckoutMandate
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.payment_receipt import PaymentReceipt
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.mandate import MandateClient
from common import artifact_utils
from common.a2a_message_builder import A2aMessageBuilder
from common.constants import (
  AGENT_PROVIDER_KEY_PATH,
  AGENT_PROVIDER_PUB_PATH,
  CHECKOUT_MANDATE_SD_JWT_KEY,
  DEFAULT_MANDATE_TTL_SECONDS,
  PAYMENT_MANDATE_SD_JWT_KEY,
  PAYMENT_RECEIPT_DATA_KEY,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from google.adk.tools.tool_context import ToolContext
from jwcrypto.jwk import JWK

from .remote_agents import credentials_provider_client, merchant_agent_client


_logger = logging.getLogger("shopping_agent")

DEMO_MERCHANT = Merchant(
    id="merchant_1",
    name="Generic Merchant",
    website="https://demo-merchant.example",
)

DEMO_PAYMENT_INSTRUMENT = PaymentInstrument(
    type="card", id="stub", description="Card •••4242"
)


def _get_user_signing_key(
    key_id: str = "user-key-1",
) -> JWK:
  """Load or generate the user signing key."""
  pem = os.environ.get("AGENT_PROVIDER_SIGNING_KEY_PEM")
  if pem:
    raw_key = serialization.load_pem_private_key(pem.encode(), password=None)
  elif AGENT_PROVIDER_KEY_PATH.exists():
    raw_key = serialization.load_pem_private_key(
        AGENT_PROVIDER_KEY_PATH.read_bytes(), password=None
    )
  else:
    raw_key = ec.generate_private_key(ec.SECP256R1())
    AGENT_PROVIDER_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    AGENT_PROVIDER_KEY_PATH.write_bytes(
        raw_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    AGENT_PROVIDER_PUB_PATH.write_bytes(
        raw_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

  jwk_key = JWK.from_pyca(raw_key)
  jwk_dict = json.loads(jwk_key.export())
  jwk_dict["kid"] = key_id
  return JWK.from_json(json.dumps(jwk_dict))


async def create_checkout(
    tool_context: ToolContext,
    debug_mode: bool = False,
) -> str:
  """Asks merchant to create a checkout JWT for the selected cart.

  Stores the checkout data (checkout_jwt, checkout_hash, amount, etc.) in state.

  Args:
    tool_context: The context for the tool execution.
    debug_mode: Whether to run in debug mode.

  Returns:
    The checkout data as a JSON string. The agent MUST KEEP this returned string
    internal and NEVER display it to the user.

  Raises:
    RuntimeError: If no chosen cart ID is found in the tool context state.
  """
  chosen_cart_id = tool_context.state["chosen_cart_id"]
  if not chosen_cart_id:
    raise RuntimeError("No chosen cart found in tool context state.")

  message = (
      A2aMessageBuilder()
      .set_context_id(tool_context.state["shopping_context_id"])
      .add_text("Create a checkout for the selected cart.")
      .add_data("cart_id", chosen_cart_id)
      .add_data("shopping_agent_id", "trusted_shopping_agent")
      .add_data("debug_mode", debug_mode)
      .build()
  )
  task = await merchant_agent_client.send_a2a_message(message)

  checkout_data = _extract_first_data(task.artifacts, "ap2.checkout")
  if not checkout_data:
    raise RuntimeError("Merchant did not return checkout data.")

  tool_context.state["checkout_data"] = checkout_data
  return checkout_data


def create_checkout_mandate(tool_context: ToolContext) -> str:
  """Creates a CheckoutMandate SD-JWT signed by the user.

  Reads checkout_jwt and checkout_hash from state (set by create_checkout).

  Args:
    tool_context: The context for the tool execution.

  Returns:
    The created CheckoutMandate as an SD-JWT string. The agent MUST KEEP this
    returned string internal and NEVER display it to the user.

  Raises:
    RuntimeError: If `checkout_data` is not found in the tool context state.
  """
  checkout_data = tool_context.state.get("checkout_data")
  if not checkout_data:
    raise RuntimeError("No checkout_data in state. Call create_checkout first.")

  checkout_jwt = checkout_data["checkout_jwt"]
  checkout_hash = checkout_data["checkout_hash"]

  now = int(time.time())
  payload = CheckoutMandate(
      checkout_jwt=checkout_jwt,
      checkout_hash=checkout_hash,
      iat=now,
      exp=now + DEFAULT_MANDATE_TTL_SECONDS,
  )
  user_key = _get_user_signing_key()
  sd_jwt = MandateClient().create(
      payloads=[payload],
      issuer_key=user_key,
  )
  tool_context.state["checkout_mandate_sdjwt"] = sd_jwt
  tool_context.state["checkout_hash"] = checkout_hash
  return sd_jwt


def create_payment_mandate(tool_context: ToolContext) -> str:
  """Creates a PaymentMandate SD-JWT signed by the user.

  Reads cart_data from state for amount and checkout_hash for transaction_id.

  Args:
    tool_context: The context for the tool execution.

  Returns:
    The created PaymentMandate as an SD-JWT string. The agent MUST KEEP this
    returned string internal and NEVER display it to the user.

  Raises:
    RuntimeError: If `checkout_data` is not found in the tool context state.
  """
  checkout_data = tool_context.state.get("checkout_data")
  if not checkout_data:
    raise RuntimeError("No checkout_data in state. Call create_checkout first.")

  checkout_hash = checkout_data["checkout_hash"]
  amount_cents = checkout_data.get(
      "amount_cents", int(checkout_data["amount"] * 100)
  )
  currency = checkout_data.get("currency", "USD")

  now = int(time.time())
  payload = PaymentMandate(
      transaction_id=checkout_hash,
      payee=DEMO_MERCHANT,
      payment_amount=Amount(amount=amount_cents, currency=currency),
      payment_instrument=DEMO_PAYMENT_INSTRUMENT,
      iat=now,
      exp=now + DEFAULT_MANDATE_TTL_SECONDS,
  )
  user_key = _get_user_signing_key()
  sd_jwt = MandateClient().create(
      payloads=[payload],
      issuer_key=user_key,
  )
  tool_context.state["payment_mandate_sdjwt"] = sd_jwt
  return sd_jwt


async def send_signed_mandates_to_credentials_provider(
    tool_context: ToolContext,
    debug_mode: bool = False,
) -> str:
  """Sends the signed payment mandate SD-JWT to the credentials provider."""
  payment_mandate_sdjwt = tool_context.state.get("payment_mandate_sdjwt")
  if not payment_mandate_sdjwt:
    raise RuntimeError("No payment mandate SD-JWT in state.")
  if not tool_context.state.get("payment_credential_token"):
    raise RuntimeError(
        "Payment method not selected. Delegate to `payment_method_collector`"
        " to have the user pick an eligible payment method (which calls"
        " `get_payment_methods` and then `get_payment_credential_token`)"
        " BEFORE sending signed mandates to the credentials provider."
    )
  risk_data = tool_context.state.get("risk_data", "")

  message = (
      A2aMessageBuilder()
      .set_context_id(tool_context.state["shopping_context_id"])
      .add_text("This is the signed payment mandate")
      .add_data(PAYMENT_MANDATE_SD_JWT_KEY, payment_mandate_sdjwt)
      .add_data("risk_data", risk_data)
      .add_data("debug_mode", debug_mode)
      .build()
  )
  await credentials_provider_client.send_a2a_message(message)
  return "Successfully sent mandates to the credentials provider."


async def initiate_payment(tool_context: ToolContext, debug_mode: bool = False):
  """Initiates payment by sending mandate SD-JWTs to the merchant."""
  payment_mandate_sdjwt = tool_context.state.get("payment_mandate_sdjwt")
  if not payment_mandate_sdjwt:
    raise RuntimeError("No payment mandate SD-JWT in state.")
  checkout_mandate_sdjwt = tool_context.state.get("checkout_mandate_sdjwt")
  risk_data = tool_context.state.get("risk_data", "")

  builder = (
      A2aMessageBuilder()
      .set_context_id(tool_context.state["shopping_context_id"])
      .add_text("Initiate a payment")
      .add_data(PAYMENT_MANDATE_SD_JWT_KEY, payment_mandate_sdjwt)
      .add_data("risk_data", risk_data)
      .add_data("shopping_agent_id", "trusted_shopping_agent")
      .add_data("debug_mode", debug_mode)
  )
  if checkout_mandate_sdjwt:
    builder.add_data(CHECKOUT_MANDATE_SD_JWT_KEY, checkout_mandate_sdjwt)

  task = await merchant_agent_client.send_a2a_message(builder.build())
  _store_receipt_if_present(task, tool_context)
  tool_context.state["initiate_payment_task_id"] = task.id
  if task.status.state == "challenge" and task.status.challenge:
    return f"Verification required: {task.status.challenge.display_text}"
  return f"Status: {task.status.state}"


async def initiate_payment_with_otp(
    challenge_response: str, tool_context: ToolContext, debug_mode: bool = False
):
  """Retries payment with an OTP challenge response."""
  payment_mandate_sdjwt = tool_context.state.get("payment_mandate_sdjwt")
  if not payment_mandate_sdjwt:
    raise RuntimeError("No payment mandate SD-JWT in state.")
  checkout_mandate_sdjwt = tool_context.state.get("checkout_mandate_sdjwt")
  risk_data = tool_context.state.get("risk_data", "")

  builder = (
      A2aMessageBuilder()
      .set_context_id(tool_context.state["shopping_context_id"])
      .set_task_id(tool_context.state["initiate_payment_task_id"])
      .add_text("Initiate a payment. Include the challenge response.")
      .add_data(PAYMENT_MANDATE_SD_JWT_KEY, payment_mandate_sdjwt)
      .add_data("shopping_agent_id", "trusted_shopping_agent")
      .add_data("challenge_response", challenge_response)
      .add_data("risk_data", risk_data)
      .add_data("debug_mode", debug_mode)
  )
  if checkout_mandate_sdjwt:
    builder.add_data(CHECKOUT_MANDATE_SD_JWT_KEY, checkout_mandate_sdjwt)

  task = await merchant_agent_client.send_a2a_message(builder.build())
  _store_receipt_if_present(task, tool_context)
  if task.status.state == "challenge" and task.status.challenge:
    return f"Verification required: {task.status.challenge.display_text}"
  return f"Status: {task.status.state}"


def _extract_first_data(artifacts, data_key: str) -> dict[str, Any] | None:
  """Extract the first dict with the given key from A2A artifacts."""
  if not artifacts:
    return None
  for artifact in artifacts:
    for part in artifact.parts:
      if hasattr(part.root, "data") and data_key in part.root.data:
        return part.root.data[data_key]
  return None


def _store_receipt_if_present(task, tool_context: ToolContext) -> None:
  payment_receipts = artifact_utils.find_canonical_objects(
      task.artifacts, PAYMENT_RECEIPT_DATA_KEY, PaymentReceipt
  )
  if payment_receipts:
    tool_context.state["payment_receipt"] = artifact_utils.only(
        payment_receipts
    ).model_dump(mode="json")
