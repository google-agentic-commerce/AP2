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


import json
import logging
from typing import Any

import httpx

from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import DataPart
from a2a.types import Part
from a2a.types import Task
from a2a.types import TaskState
from a2a.types import TextPart

from ap2.types.mandate import PAYMENT_MANDATE_DATA_KEY
from ap2.types.mandate import PaymentMandate
from common import artifact_utils
from common import message_utils
from common.a2a_extension_utils import EXTENSION_URI
from common.a2a_message_builder import A2aMessageBuilder
from common.payment_remote_a2a_client import PaymentRemoteA2aClient


_FALLBACK_FACILITATOR_URL = "https://x402.org/facilitator"
_DEFAULT_CASHU_NETWORK = "bitcoin-testnet"
_DEFAULT_CASHU_PAY_TO = "cashu:merchant"
_DEFAULT_CASHU_UNIT = "sat"
_DEFAULT_CASHU_TIMEOUT = 600
_DEFAULT_CASHU_ASSET = "SAT"


async def initiate_payment(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
    debug_mode: bool = False,
) -> None:
  """Handles the initiation of a payment."""
  payment_mandate = message_utils.find_data_part(
      PAYMENT_MANDATE_DATA_KEY, data_parts
  )
  if not payment_mandate:
    error_message = _create_text_parts("Missing payment_mandate.")
    await updater.failed(message=updater.new_agent_message(parts=error_message))
    return

  challenge_response = (
      message_utils.find_data_part("challenge_response", data_parts) or ""
  )
  await _handle_payment_mandate(
      PaymentMandate.model_validate(payment_mandate),
      challenge_response,
      updater,
      current_task,
      debug_mode,
  )


async def _handle_payment_mandate(
    payment_mandate: PaymentMandate,
    challenge_response: str,
    updater: TaskUpdater,
    current_task: Task | None,
    debug_mode: bool = False,
) -> None:
  """Handles a payment mandate.

  If no task is present, it initiates a transaction challenge. If a task
  requires input, it verifies the challenge response and completes the payment.

  Args:
    payment_mandate: The payment mandate containing payment details.
    challenge_response: The response to a transaction challenge, if any.
    updater: The task updater for managing task state.
    current_task: The current task, or None if it's a new payment.
    debug_mode: Whether the agent is in debug mode.
  """
  if current_task is None:
    await _raise_challenge(updater)
    return

  if current_task.status.state == TaskState.input_required:
    await _check_challenge_response_and_complete_payment(
        payment_mandate,
        challenge_response,
        updater,
        debug_mode,
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
    payment_mandate: PaymentMandate,
    challenge_response: str,
    updater: TaskUpdater,
    debug_mode: bool = False,
) -> None:
  """Checks the challenge response and completes the payment process.

  Checking the challenge response would be done by the issuer, but we don't
  have an issuer in the demo, so we do it here.

  Args:
    payment_mandate: The payment mandate.
    challenge_response: The challenge response.
    updater: The task updater.
    debug_mode: Whether the agent is in debug mode.
  """
  if _challenge_response_is_valid(challenge_response=challenge_response):
    await _complete_payment(payment_mandate, updater, debug_mode)
    return

  message = updater.new_agent_message(
      _create_text_parts("Challenge response incorrect.")
  )
  await updater.requires_input(message=message)


async def _complete_payment(
    payment_mandate: PaymentMandate,
    updater: TaskUpdater,
    debug_mode: bool = False,
) -> None:
  """Completes the payment process.

  Args:
    payment_mandate: The payment mandate.
    updater: The task updater.
    debug_mode: Whether the agent is in debug mode.
  """
  payment_mandate_id = (
      payment_mandate.payment_mandate_contents.payment_mandate_id
  )
  payment_credential = await _request_payment_credential(
      payment_mandate, updater, debug_mode
  )

  method_name = (
      payment_mandate.payment_mandate_contents.payment_response.method_name
  )

  settle_receipt: dict[str, Any] | None = None

  try:
    if method_name == "x402:cashu-token":
      settle_receipt = await _handle_cashu_payment(
          payment_mandate, payment_credential
      )
    else:
      logging.info(
          "Calling issuer to complete payment for %s with payment credential %s...",
          payment_mandate_id,
          payment_credential,
      )
      # Call issuer to complete the payment
  except ValueError as exc:
    logging.exception("Cashu settlement failed for %s", payment_mandate_id)
    failure_payload = {"status": "failed", "reason": str(exc)}
    failure_message = updater.new_agent_message(
        _create_text_parts(json.dumps(failure_payload))
    )
    await updater.failed(message=failure_message)
    return
  except httpx.HTTPError as exc:
    logging.exception("Facilitator request failed for %s", payment_mandate_id)
    failure_payload = {
        "status": "failed",
        "reason": f"Facilitator request error: {exc}",
    }
    failure_message = updater.new_agent_message(
        _create_text_parts(json.dumps(failure_payload))
    )
    await updater.failed(message=failure_message)
    return
  except Exception as exc:  # pylint: disable=broad-except
    logging.exception("Unexpected error completing payment for %s", payment_mandate_id)
    failure_payload = {"status": "failed", "reason": str(exc)}
    failure_message = updater.new_agent_message(
        _create_text_parts(json.dumps(failure_payload))
    )
    await updater.failed(message=failure_message)
    return

  logging.info(
      "Payment for %s completed with method %s",
      payment_mandate_id,
      method_name,
  )
  success_payload = {"status": "success"}
  if settle_receipt and settle_receipt.get("transaction"):
    success_payload["transaction"] = settle_receipt["transaction"]

  success_message = updater.new_agent_message(
      parts=_create_text_parts(json.dumps(success_payload))
  )
  await updater.complete(message=success_message)


def _challenge_response_is_valid(challenge_response: str) -> bool:
  """Validates the challenge response."""

  return challenge_response == "123"


async def _request_payment_credential(
    payment_mandate: PaymentMandate,
    updater: TaskUpdater,
    debug_mode: bool = False,
) -> str:
  """Sends a request to the Credentials Provider for payment credentials.

  Args:
    payment_mandate: The PaymentMandate containing payment details.
    updater: The task updater.
    debug_mode: Whether the agent is in debug mode.

  Returns:
    payment_credential: The payment credential details.
  """
  token_object = (
      payment_mandate.payment_mandate_contents.payment_response.details.get(
          "token"
      )
  )
  credentials_provider_url = token_object.get("url")

  credentials_provider = PaymentRemoteA2aClient(
      name="credentials_provider",
      base_url=credentials_provider_url,
      required_extensions={EXTENSION_URI},
  )

  message_builder = (
      A2aMessageBuilder()
      .set_context_id(updater.context_id)
      .add_text("Give me the payment method credentials for the given token.")
      .add_data(PAYMENT_MANDATE_DATA_KEY, payment_mandate.model_dump())
      .add_data("debug_mode", debug_mode)
  )
  task = await credentials_provider.send_a2a_message(message_builder.build())

  if not task.artifacts:
    raise ValueError("Failed to find the payment method data.")
  payment_credential = artifact_utils.get_first_data_part(task.artifacts)

  return payment_credential


def _create_text_parts(*texts: str) -> list[Part]:
  """Helper to create text parts."""
  return [Part(root=TextPart(text=text)) for text in texts]


async def _handle_cashu_payment(
    payment_mandate: PaymentMandate,
    payment_credential: dict[str, Any],
) -> dict[str, Any]:
  """Verifies and settles a Cashu payment using an x402 facilitator."""

  facilitator_url = payment_credential.get("facilitator_url")
  if facilitator_url is None:
    facilitator_url = _FALLBACK_FACILITATOR_URL
  facilitator_url = facilitator_url.rstrip("/")

  network = payment_credential.get("network") or _DEFAULT_CASHU_NETWORK
  pay_to = payment_credential.get("pay_to") or _DEFAULT_CASHU_PAY_TO
  unit = payment_credential.get("unit") or _DEFAULT_CASHU_UNIT
  max_timeout_value = payment_credential.get("max_timeout_seconds")
  if max_timeout_value is None:
    max_timeout_value = _DEFAULT_CASHU_TIMEOUT
  max_timeout = int(max_timeout_value)

  raw_tokens = payment_credential.get("tokens")
  if raw_tokens is None:
    proofs = payment_credential.get("proofs", [])
    mint_url = payment_credential.get("mint_url")
    if not mint_url:
      raise ValueError("Cashu payment credential missing mint_url")
    if not proofs:
      raise ValueError("No proofs supplied for cashu-token payment")
    raw_tokens = [
        {
            "mint": mint_url,
            "proofs": proofs,
        }
    ]

  encoded_tokens = payment_credential.get("encoded")
  if encoded_tokens is None:
    encoded_tokens = payment_credential.get("encoded_tokens")
  if not encoded_tokens:
    raise ValueError("Cashu payment credential missing encoded token values")

  normalized_tokens: list[dict[str, Any]] = []
  total_amount = 0
  for token in raw_tokens:
    mint_url = token.get("mint")
    if not mint_url:
      raise ValueError("Cashu token entry missing mint URL")
    proofs = token.get("proofs", [])
    if not proofs:
      raise ValueError("Cashu token entry must include proofs")

    normalized_proofs: list[dict[str, Any]] = []
    for proof in proofs:
      amount = int(proof.get("amount", 0))
      if amount <= 0:
        raise ValueError("Cashu proof amount must be positive")
      proof_data = {
          "amount": amount,
          "secret": proof.get("secret"),
          "C": proof.get("C"),
          "id": proof.get("id"),
      }
      if dleq := proof.get("dleq"):
        proof_data["dleq"] = dleq
      if witness := proof.get("witness"):
        proof_data["witness"] = witness
      normalized_proofs.append(proof_data)
      total_amount += amount

    normalized_tokens.append(
        {
            "mint": mint_url,
            "proofs": normalized_proofs,
            **({"memo": token.get("memo")} if token.get("memo") else {}),
            **({"unit": token.get("unit") or unit}),
        }
    )

  if len(encoded_tokens) != len(normalized_tokens):
    raise ValueError("Encoded tokens must align with provided token entries")

  payment_payload = {
      "x402Version": 1,
      "scheme": "cashu-token",
      "network": network,
      "payload": {
          "tokens": normalized_tokens,
          "encoded": encoded_tokens,
          **({"memo": payment_credential.get("memo")} if payment_credential.get("memo") else {}),
          **({"unit": unit} if unit else {}),
          **({"locks": payment_credential.get("locks")} if payment_credential.get("locks") else {}),
      },
  }

  requirement_resource = (
      f"urn:ap2:payment:{payment_mandate.payment_mandate_contents.payment_details_id}"
  )
  requirement_description = (
      payment_mandate.payment_mandate_contents.payment_details_total.label
      if payment_mandate.payment_mandate_contents.payment_details_total
      else "ap2-cashu-payment"
  )

  accepted_mints = payment_credential.get("mints")
  if not accepted_mints:
    accepted_mints = [token["mint"] for token in normalized_tokens]

  extra: dict[str, Any] = {
      "mints": accepted_mints,
      "unit": unit,
  }
  if facilitator_url:
    extra["facilitatorUrl"] = facilitator_url
  if payment_credential.get("keyset_ids"):
    extra["keysetIds"] = payment_credential["keyset_ids"]
  if payment_credential.get("locks"):
    extra["nut10"] = payment_credential["locks"]

  payment_requirements = {
      "scheme": "cashu-token",
      "network": network,
      "maxAmountRequired": str(total_amount),
      "resource": requirement_resource,
      "description": requirement_description,
      "mimeType": "application/json",
      "payTo": pay_to,
      "maxTimeoutSeconds": max_timeout,
      "asset": payment_credential.get("asset") or _DEFAULT_CASHU_ASSET,
      "extra": extra,
  }

  request_body = {
      "x402Version": 1,
      "paymentPayload": payment_payload,
      "paymentRequirements": payment_requirements,
  }

  async with httpx.AsyncClient(timeout=30.0) as client:
    verify_response = await client.post(
        f"{facilitator_url}/verify", json=request_body, follow_redirects=True
    )
    verify_response.raise_for_status()
    verify_body = verify_response.json()
    if not verify_body.get("isValid", False):
      raise ValueError(
          f"Facilitator rejected Cashu payment: {verify_body.get('invalidReason')}"
      )

    settle_response = await client.post(
        f"{facilitator_url}/settle", json=request_body, follow_redirects=True
    )
    settle_response.raise_for_status()
    settle_body = settle_response.json()
    if not settle_body.get("success", False):
      raise ValueError(
          f"Facilitator could not settle Cashu payment: {settle_body.get('errorReason')}"
      )

  logging.info(
      "[cashu-token] Facilitator settled mandate %s with transaction %s",
      payment_mandate.payment_mandate_contents.payment_mandate_id,
      settle_body.get("transaction"),
  )
  return settle_body
