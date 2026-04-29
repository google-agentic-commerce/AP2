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

"""Tools for the merchant payment processor agent.

Each agent uses individual tools to handle distinct tasks throughout the
shopping and purchasing process.
"""

import logging
import os
import uuid

from datetime import UTC, datetime
from typing import Any

from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import DataPart, Part, Task, TaskState, TextPart
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.payment_receipt import PaymentReceipt
from ap2.sdk.mandate import MandateClient
from ap2.sdk.utils import compute_sha256_b64url
from common import artifact_utils, message_utils
from common.a2a_extension_utils import EXTENSION_URI
from common.a2a_message_builder import A2aMessageBuilder
from common.constants import (
  PAYMENT_MANDATE_SD_JWT_KEY,
  PAYMENT_RECEIPT_DATA_KEY,
)
from common.payment_remote_a2a_client import PaymentRemoteA2aClient
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from jwcrypto.jwk import JWK


_AGENT_PROVIDER_PUB_KEY_PATH = os.environ.get(
    "AGENT_PROVIDER_PUBLIC_KEY_PATH", ""
)
_CREDENTIALS_PROVIDER_URL = "http://localhost:8002/a2a/credentials_provider"


async def initiate_payment(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
    debug_mode: bool = False,
) -> None:
  """Handles the initiation of a payment using a PaymentMandate SD-JWT."""
  payment_mandate_sdjwt = message_utils.find_data_part(
      PAYMENT_MANDATE_SD_JWT_KEY, data_parts
  )
  if not payment_mandate_sdjwt:
    error_message = _create_text_parts("Missing PaymentMandate SD-JWT.")
    await updater.failed(message=updater.new_agent_message(parts=error_message))
    return

  checkout_jwt_hash = message_utils.find_data_part(
      "checkout_jwt_hash", data_parts
  )
  _verify_payment_mandate(
      payment_mandate_sdjwt, nonce=checkout_jwt_hash, aud="credential-provider"
  )

  challenge_response = (
      message_utils.find_data_part("challenge_response", data_parts) or ""
  )
  await _handle_payment_mandate(
      payment_mandate_sdjwt,
      challenge_response,
      updater,
      current_task,
      checkout_jwt_hash=checkout_jwt_hash,
      debug_mode=debug_mode,
  )


async def _handle_payment_mandate(
    payment_mandate_sdjwt: str,
    challenge_response: str,
    updater: TaskUpdater,
    current_task: Task | None,
    checkout_jwt_hash: str | None = None,
    debug_mode: bool = False,
) -> None:
  """Handles a verified payment mandate.

  If no task is present, it initiates a transaction challenge. If a task
  requires input, it verifies the challenge response and completes the payment.

  Args:
    payment_mandate_sdjwt: The PaymentMandate SD-JWT string.
    challenge_response: The response to a potential challenge.
    updater: The task updater.
    current_task: The current task, or None if this is the first call.
    checkout_jwt_hash: Optional checkout JWT hash for KB verification.
    debug_mode: Whether debug mode is enabled.
  """
  if current_task is None:
    await _raise_challenge(updater)
    return

  if current_task.status.state == TaskState.input_required:
    await _check_challenge_response_and_complete_payment(
        payment_mandate_sdjwt,
        challenge_response,
        updater,
        checkout_jwt_hash=checkout_jwt_hash,
        debug_mode=debug_mode,
    )
    return


async def _raise_challenge(
    updater: TaskUpdater,
) -> None:
  """Raises a transaction challenge.

  This challenge would normally be raised by the issuer, but we don't
  have an issuer in the demo, so we raise the challenge here. For concreteness,
  we are using an OTP challenge in this sample.

  Args:
    updater: The task updater.
  """
  challenge_data = {
      "type": "otp",
      "display_text": (
          "The payment method issuer sent a verification code to the phone "
          "number on file, please enter it below. It will be shared with the "
          "issuer so they can authorize the transaction."
          "(Demo only hint: the code is 123)"
      ),
  }
  text_part = TextPart(
      text="Please provide the challenge response to complete the payment."
  )
  data_part = DataPart(data={"challenge": challenge_data})
  message = updater.new_agent_message(
      parts=[Part(root=text_part), Part(root=data_part)]
  )
  await updater.requires_input(message=message)


async def _check_challenge_response_and_complete_payment(
    payment_mandate_sdjwt: str,
    challenge_response: str,
    updater: TaskUpdater,
    checkout_jwt_hash: str | None = None,
    debug_mode: bool = False,
) -> None:
  """Checks the challenge response and completes the payment."""
  if _challenge_response_is_valid(challenge_response=challenge_response):
    await _complete_payment(
        payment_mandate_sdjwt, updater, checkout_jwt_hash, debug_mode
    )
    return

  message = updater.new_agent_message(
      _create_text_parts("Challenge response incorrect.")
  )
  await updater.requires_input(message=message)


async def _complete_payment(
    payment_mandate_sdjwt: str,
    updater: TaskUpdater,
    checkout_jwt_hash: str | None = None,
    debug_mode: bool = False,
) -> None:
  """Completes the payment process using the SDK PaymentMandate."""
  payment_mandate = _verify_payment_mandate(
      payment_mandate_sdjwt, nonce=checkout_jwt_hash, aud="credential-provider"
  )
  transaction_id = payment_mandate.transaction_id

  credentials_provider = PaymentRemoteA2aClient(
      name="credentials_provider",
      base_url=_CREDENTIALS_PROVIDER_URL,
      required_extensions={EXTENSION_URI},
  )
  payment_credential = await _request_payment_credential(
      payment_mandate_sdjwt,
      credentials_provider,
      updater,
      debug_mode,
  )

  logging.info(
      "Completing payment for transaction %s with credential %s...",
      transaction_id,
      payment_credential,
  )
  payment_receipt = _create_payment_receipt(
      payment_mandate, payment_mandate_sdjwt
  )
  await _send_payment_receipt_to_credentials_provider(
      payment_receipt,
      credentials_provider,
      updater,
      debug_mode,
  )
  await updater.add_artifact([
      Part(
          root=DataPart(
              data={PAYMENT_RECEIPT_DATA_KEY: payment_receipt.model_dump()}
          )
      )
  ])
  success_message = updater.new_agent_message(
      parts=_create_text_parts("{'status': 'success'}")
  )
  await updater.complete(message=success_message)


def _challenge_response_is_valid(challenge_response: str) -> bool:
  """Validates the challenge response."""
  return challenge_response == "123"


async def _request_payment_credential(
    payment_mandate_sdjwt: str,
    credentials_provider: PaymentRemoteA2aClient,
    updater: TaskUpdater,
    debug_mode: bool = False,
) -> str:
  """Sends the PaymentMandate SD-JWT to the CP to get credentials."""
  message_builder = (
      A2aMessageBuilder()
      .set_context_id(updater.context_id)
      .add_text("Give me the payment method credentials for this mandate.")
      .add_data(PAYMENT_MANDATE_SD_JWT_KEY, payment_mandate_sdjwt)
      .add_data("debug_mode", debug_mode)
  )
  task = await credentials_provider.send_a2a_message(message_builder.build())
  _raise_if_task_failed(task, "credentials_provider", "payment credential")
  if not task.artifacts:
    raise ValueError(
      "credentials_provider returned no payment method data"
      " (task completed with empty artifacts)"
    )
  return artifact_utils.get_first_data_part(task.artifacts)


def _create_payment_receipt(
    payment_mandate: PaymentMandate, payment_mandate_sdjwt: str
) -> PaymentReceipt:
  """Creates a payment receipt from the SDK PaymentMandate."""
  payment_id = uuid.uuid4().hex
  return PaymentReceipt(
      status='Success',
      iss=(
          payment_mandate.pisp.domain_name
          if payment_mandate.pisp
          else ""
      ),
      iat=int(datetime.now(UTC).timestamp()),
      reference=compute_sha256_b64url(
          MandateClient().get_closed_mandate_jwt(payment_mandate_sdjwt)
      ),
      payment_id=payment_id,
      psp_confirmation_id=payment_id,
      network_confirmation_id=payment_id,
  )


async def _send_payment_receipt_to_credentials_provider(
    payment_receipt: PaymentReceipt,
    credentials_provider: PaymentRemoteA2aClient,
    updater: TaskUpdater,
    debug_mode: bool = False,
) -> None:
  """Sends the payment receipt to the Credentials Provider."""
  message_builder = (
      A2aMessageBuilder()
      .set_context_id(updater.context_id)
      .add_text("Here is the payment receipt. No action is required.")
      .add_data(PAYMENT_RECEIPT_DATA_KEY, payment_receipt.model_dump())
      .add_data("debug_mode", debug_mode)
  )
  task = await credentials_provider.send_a2a_message(message_builder.build())
  _raise_if_task_failed(task, "credentials_provider", "payment receipt delivery")


def _extract_task_error_text(task: Task) -> str:
  """Pulls a human-readable error string out of a failed A2A task."""
  status = getattr(task, "status", None)
  if status is None:
    return ""
  message = getattr(status, "message", None)
  if message is None:
    return ""
  parts = getattr(message, "parts", []) or []
  texts: list[str] = []
  for part in parts:
    root = getattr(part, "root", part)
    text = getattr(root, "text", None)
    if text:
      texts.append(text)
  return " | ".join(texts)


def _raise_if_task_failed(task: Task, peer: str, operation: str) -> None:
  """Surface the remote agent's error text instead of masking it downstream.

  If the remote task did not complete successfully, raise with the remote's
  own error message so callers (and the retry/LLM layer above) see the true
  cause rather than a generic "no artifacts" ValueError several steps later.
  """
  state = getattr(getattr(task, "status", None), "state", None)
  if state is None or state == TaskState.completed:
    return
  error_text = _extract_task_error_text(task) or "<no message>"
  raise ValueError(
    f"{peer} {operation} failed (state={state}): {error_text}"
  )


def _verify_payment_mandate(
    sdjwt: str, nonce: str | None = None, aud: str | None = None
) -> PaymentMandate:
  """Verify a PaymentMandate SD-JWT and return the parsed model."""
  if _AGENT_PROVIDER_PUB_KEY_PATH and os.path.exists(
      _AGENT_PROVIDER_PUB_KEY_PATH
  ):
    pub_key = load_pem_public_key(
        open(_AGENT_PROVIDER_PUB_KEY_PATH, "rb").read()
    )
    verified = MandateClient().verify(
        token=sdjwt,
        key_or_provider=JWK.from_pyca(pub_key),
        payload_type=PaymentMandate,
        expected_nonce=nonce,
        expected_aud=aud,
    )
    return verified.mandate_payload
  raise ValueError("Agent-provider public key not found")


def _create_text_parts(*texts: str) -> list[Part]:
  """Helper to create text parts."""
  return [Part(root=TextPart(text=text)) for text in texts]
