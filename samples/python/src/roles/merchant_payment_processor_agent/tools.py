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
from typing import Any

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

  logging.info(
      "Calling issuer to complete payment for %s with payment credential %s...",
      payment_mandate_id,
      payment_credential,
  )
  # Call issuer to complete the payment
  success_message = updater.new_agent_message(
      parts=_create_text_parts("{'status': 'success'}")
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
