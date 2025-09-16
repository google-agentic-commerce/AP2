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
shopping and purchasing process, such as updating a cart or initiating payment.
"""

from datetime import datetime
from datetime import timezone
import uuid

from a2a.types import Artifact
from google.adk.tools.tool_context import ToolContext

from .remote_agents import credentials_provider_client
from .remote_agents import merchant_agent_client
from ap2.types.contact_picker import ContactAddress
from ap2.types.mandate import CART_MANDATE_DATA_KEY
from ap2.types.mandate import CartMandate
from ap2.types.mandate import PAYMENT_MANDATE_DATA_KEY
from ap2.types.mandate import PaymentMandate
from ap2.types.mandate import PaymentMandateContents
from ap2.types.payment_request import PaymentResponse
from common import artifact_utils
from common.a2a_message_builder import A2aMessageBuilder


async def update_cart(
    shipping_address: ContactAddress,
    tool_context: ToolContext,
    debug_mode: bool = False,
) -> str:
  """Notifies the merchant agent of a shipping address selection for a cart.

  Args:
    shipping_address: The user's selected shipping address.
    tool_context: The ADK supplied tool context.
    debug_mode: Whether the agent is in debug mode.

  Returns:
    The updated CartMandate.
  """
  chosen_cart_id = tool_context.state["chosen_cart_id"]
  if not chosen_cart_id:
    raise RuntimeError("No chosen cart mandate found in tool context state.")

  message = (
      A2aMessageBuilder()
      .set_context_id(tool_context.state["shopping_context_id"])
      .add_text("Update the cart with the user's shipping address.")
      .add_data("cart_id", chosen_cart_id)
      .add_data("shipping_address", shipping_address)
      .add_data("shopping_agent_id", "trusted_shopping_agent")
      .add_data("debug_mode", debug_mode)
      .build()
  )
  task = await merchant_agent_client.send_a2a_message(message)

  updated_cart_mandate = artifact_utils.only(
      _parse_cart_mandates(task.artifacts)
  )

  tool_context.state["cart_mandate"] = updated_cart_mandate
  tool_context.state["shipping_address"] = shipping_address

  return updated_cart_mandate


async def initiate_payment(tool_context: ToolContext, debug_mode: bool = False):
  """Initiates a payment using the payment mandate from state.

  Args:
    tool_context: The ADK supplied tool context.
    debug_mode: Whether the agent is in debug mode.

  Returns:
    The status of the payment initiation.
  """
  payment_mandate = tool_context.state["signed_payment_mandate"]
  if not payment_mandate:
    raise RuntimeError("No signed payment mandate found in tool context state.")
  risk_data = tool_context.state["risk_data"]
  if not risk_data:
    raise RuntimeError("No risk data found in tool context state.")

  outgoing_message_builder = (
      A2aMessageBuilder()
      .set_context_id(tool_context.state["shopping_context_id"])
      .add_text("Initiate a payment")
      .add_data(PAYMENT_MANDATE_DATA_KEY, payment_mandate)
      .add_data("risk_data", risk_data)
      .add_data("shopping_agent_id", "trusted_shopping_agent")
      .add_data("debug_mode", debug_mode)
      .build()
  )
  task = await merchant_agent_client.send_a2a_message(outgoing_message_builder)
  tool_context.state["initiate_payment_task_id"] = task.id
  return task.status


async def initiate_payment_with_otp(
    challenge_response: str, tool_context: ToolContext, debug_mode: bool = False
):
  """Initiates a payment using the payment mandate from state and a

    challenge response. In our sample, the challenge response is a one-time
    password (OTP) sent to the user.

  Args:
    challenge_response: The challenge response.
    tool_context: The ADK supplied tool context.
    debug_mode: Whether the agent is in debug mode.

  Returns:
    The status of the payment initiation.
  """
  payment_mandate = tool_context.state["signed_payment_mandate"]
  if not payment_mandate:
    raise RuntimeError("No signed payment mandate found in tool context state.")
  risk_data = tool_context.state["risk_data"]
  if not risk_data:
    raise RuntimeError("No risk data found in tool context state.")

  outgoing_message_builder = (
      A2aMessageBuilder()
      .set_context_id(tool_context.state["shopping_context_id"])
      .set_task_id(tool_context.state["initiate_payment_task_id"])
      .add_text("Initiate a payment. Include the challenge response.")
      .add_data(PAYMENT_MANDATE_DATA_KEY, payment_mandate)
      .add_data("shopping_agent_id", "trusted_shopping_agent")
      .add_data("challenge_response", challenge_response)
      .add_data("risk_data", risk_data)
      .add_data("debug_mode", debug_mode)
      .build()
  )

  task = await merchant_agent_client.send_a2a_message(outgoing_message_builder)
  return task.status


def create_payment_mandate(
    payment_method_alias: str,
    user_email: str,
    tool_context: ToolContext,
) -> str:
  """Creates a payment mandate and stores it in state.

  Args:
    payment_method_alias: The payment method alias.
    user_email: The user's email address.
    tool_context: The ADK supplied tool context.

  Returns:
    The payment mandate.
  """
  cart_mandate = tool_context.state["cart_mandate"]

  payment_request = cart_mandate.contents.payment_request
  shipping_address = tool_context.state["shipping_address"]
  payment_response = PaymentResponse(
      request_id=payment_request.details.id,
      method_name="CARD",
      details={
          "token": tool_context.state["payment_credential_token"],
      },
      shipping_address=shipping_address,
      payer_email=user_email,
  )

  payment_mandate = PaymentMandate(
      payment_mandate_contents=PaymentMandateContents(
          payment_mandate_id=uuid.uuid4().hex,
          timestamp=datetime.now(timezone.utc).isoformat(),
          payment_details_id=payment_request.details.id,
          payment_details_total=payment_request.details.total,
          payment_response=payment_response,
          merchant_agent=cart_mandate.contents.merchant_name,
      ),
  )

  tool_context.state["payment_mandate"] = payment_mandate
  return payment_mandate


def sign_mandates_on_user_device(tool_context: ToolContext) -> str:
  """Simulates signing the transaction details on a user's secure device.

  This function represents the step where the final transaction details,
  including hashes of the cart and payment mandates, would be sent to a
  secure hardware element on the user's device (e.g., Secure Enclave) to be
  cryptographically signed with the user's private key.

  Note: This is a placeholder implementation. It does not perform any actual
  cryptographic operations. It simulates the creation of a signature by
  concatenating the mandate hashes.

  Args:
      tool_context: The context object used for state management. It is expected
        to contain the `payment_mandate` and `cart_mandate`.

  Returns:
      A string representing the simulated user authorization signature (JWT).
  """
  payment_mandate: PaymentMandate = tool_context.state["payment_mandate"]
  cart_mandate: CartMandate = tool_context.state["cart_mandate"]
  cart_mandate_hash = _generate_cart_mandate_hash(cart_mandate)
  payment_mandate_hash = _generate_payment_mandate_hash(
      payment_mandate.payment_mandate_contents
  )
  # A JWT containing the user's digital signature to authorize the transaction.
  # The payload uses hashes to bind the signature to the specific cart and
  # payment details, and includes a nonce to prevent replay attacks.
  payment_mandate.user_authorization = (
      cart_mandate_hash + "_" + payment_mandate_hash
  )
  tool_context.state["signed_payment_mandate"] = payment_mandate
  return payment_mandate.user_authorization


async def send_signed_payment_mandate_to_credentials_provider(
    tool_context: ToolContext,
    debug_mode: bool = False,
) -> str:
  """Sends the signed payment mandate to the credentials provider.

  Args:
    tool_context: The ADK supplied tool context.
    debug_mode: Whether the agent is in debug mode.
  """
  payment_mandate = tool_context.state["signed_payment_mandate"]
  if not payment_mandate:
    raise RuntimeError("No signed payment mandate found in tool context state.")
  risk_data = tool_context.state["risk_data"]
  if not risk_data:
    raise RuntimeError("No risk data found in tool context state.")
  message = (
      A2aMessageBuilder()
      .set_context_id(tool_context.state["shopping_context_id"])
      .add_text("This is the signed payment mandate")
      .add_data(PAYMENT_MANDATE_DATA_KEY, payment_mandate)
      .add_data("risk_data", risk_data)
      .add_data("debug_mode", debug_mode)
      .build()
  )
  return await credentials_provider_client.send_a2a_message(message)


def _generate_cart_mandate_hash(cart_mandate: CartMandate) -> str:
  """Generates a cryptographic hash of the CartMandate.

  This hash serves as a tamper-proof reference to the specific merchant-signed
  cart offer that the user has approved.

  Note: This is a placeholder implementation for development. A real
  implementation must use a secure hashing algorithm (e.g., SHA-256) on the
  canonical representation of the CartMandate object.

  Args:
      cart_mandate: The complete CartMandate object, including the merchant's
        authorization.

  Returns:
      A string representing the hash of the cart mandate.
  """
  return "fake_cart_mandate_hash_" + cart_mandate.contents.id


def _generate_payment_mandate_hash(
    payment_mandate_contents: PaymentMandateContents,
) -> str:
  """Generates a cryptographic hash of the PaymentMandateContents.

  This hash creates a tamper-proof reference to the specific payment details
  the user is about to authorize.

  Note: This is a placeholder implementation for development. A real
  implementation must use a secure hashing algorithm (e.g., SHA-256) on the
  canonical representation of the PaymentMandateContents object.

  Args:
      payment_mandate_contents: The payment mandate contents to hash.

  Returns:
      A string representing the hash of the payment mandate contents.
  """
  return (
      "fake_payment_mandate_hash_" + payment_mandate_contents.payment_mandate_id
  )


def _parse_cart_mandates(artifacts: list[Artifact]) -> list[CartMandate]:
  """Parses a list of artifacts into a list of CartMandate objects."""
  return artifact_utils.find_canonical_objects(
      artifacts, CART_MANDATE_DATA_KEY, CartMandate
  )
