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

"""Tools for the credentials provider agent.

Each agent uses individual tools to handle distinct tasks throughout the
shopping and purchasing process.
"""

import logging
import os

from typing import Any

from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import DataPart, Part, Task
from ap2.models.contact_picker import CONTACT_ADDRESS_DATA_KEY
from ap2.models.payment_request import (
  PAYMENT_METHOD_DATA_DATA_KEY,
  PaymentMethodData,
)
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.mandate import MandateClient
from ap2.sdk.sdjwt.chain import X5cOrKidPublicKeyProvider
from common import message_utils
from common.constants import PAYMENT_MANDATE_SD_JWT_KEY
from cryptography import x509
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from jwcrypto.jwk import JWK
from pydantic import ValidationError

from . import account_manager


_AGENT_PROVIDER_PUB_KEY_PATH = os.environ.get(
    "AGENT_PROVIDER_PUBLIC_KEY_PATH", ""
)


async def handle_get_shipping_address(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Handles a request to get the user's shipping address.

  Updates a task with the user's shipping address if found.

  Args:
    data_parts: DataPart contents. Should contain a single user_email.
    updater: The TaskUpdater instance for updating the task state.
    current_task: The current task if there is one.
  """
  user_email = message_utils.find_data_part("user_email", data_parts)
  if not user_email:
    raise ValueError("user_email is required for get_shipping_address")
  shipping_address = account_manager.get_account_shipping_address(user_email)
  await updater.add_artifact(
      [Part(root=DataPart(data={CONTACT_ADDRESS_DATA_KEY: shipping_address}))]
  )
  await updater.complete()


async def handle_search_payment_methods(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Returns the user's payment methods that match what the merchant accepts.

  The merchant's accepted payment methods are provided in the data_parts as a
  list of PaymentMethodData objects.  The user's account is identified by the
  user_email provided in the data_parts.

  This tool finds and returns all the payment methods associated with the user's
  account that match the merchant's accepted payment methods.

  Args:
    data_parts: DataPart contents. Should contain a single user_email and a
      list of PaymentMethodData objects.
    updater: The TaskUpdater instance for updating the task state.
    current_task: The current task if there is one.
  """
  user_email = message_utils.find_data_part("user_email", data_parts)
  method_data = message_utils.find_data_parts(
      PAYMENT_METHOD_DATA_DATA_KEY, data_parts
  )
  if not user_email:
    raise ValueError(
        "user_email is required for search_payment_methods"
    )
  if not method_data:
    raise ValueError("method_data is required for search_payment_methods")

  merchant_method_data_list = [
      PaymentMethodData.model_validate(data) for data in method_data
  ]
  eligible_aliases = _get_eligible_payment_method_aliases(
      user_email, merchant_method_data_list
  )
  await updater.add_artifact([Part(root=DataPart(data=eligible_aliases))])
  await updater.complete()


async def handle_get_payment_method_raw_credentials(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Exchanges a payment mandate SD-JWT for payment credentials.

  Verifies the mandate and returns the raw payment method credentials.

  Args:
    data_parts: DataPart contents with ``ap2.mandates.PaymentMandateSdJwt``.
    updater: The TaskUpdater instance for updating the task state.
    current_task: The current task if there is one.
  """
  payment_mandate_sdjwt = message_utils.find_data_part(
      PAYMENT_MANDATE_SD_JWT_KEY, data_parts
  )
  if not payment_mandate_sdjwt:
    raise ValueError("Missing PaymentMandate SD-JWT")

  checkout_jwt_hash = message_utils.find_data_part(
      "checkout_jwt_hash", data_parts
  )
  mandate = _verify_payment_mandate(
      payment_mandate_sdjwt,
      expected_aud="credential-provider",
      expected_nonce=checkout_jwt_hash,
  )
  transaction_id = mandate.transaction_id

  payment_method = account_manager.get_credentials_by_transaction_id(
      transaction_id
  )
  if not payment_method:
    raise ValueError(
        f"Payment method not found for transaction: {transaction_id}"
    )
  await updater.add_artifact([Part(root=DataPart(data=payment_method))])
  await updater.complete()


async def handle_create_payment_credential_token(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Handles a request to get a payment credential token.

  Updates a task with the payment credential token.

  Args:
    data_parts: DataPart contents. Should contain the user_email and
      payment_method_alias.
    updater: The TaskUpdater instance for updating the task state.
    current_task: The current task if there is one.
  """
  user_email = message_utils.find_data_part("user_email", data_parts)
  payment_method_alias = message_utils.find_data_part(
      "payment_method_alias", data_parts
  )
  if not user_email or not payment_method_alias:
    raise ValueError(
        "user_email and payment_method_alias are required for"
        " create_payment_credential_token"
    )

  tokenized_payment_method = account_manager.create_token(
      user_email, payment_method_alias
  )

  await updater.add_artifact(
      [Part(root=DataPart(data={"token": tokenized_payment_method}))]
  )
  await updater.complete()


async def handle_signed_payment_mandate(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Handles a signed payment mandate SD-JWT.

  Verifies the SD-JWT, extracts the transaction_id, and binds it to the
  user's payment token in storage.

  Args:
    data_parts: DataPart contents with ``ap2.mandates.PaymentMandateSdJwt``.
    updater: The TaskUpdater instance for updating the task state.
    current_task: The current task if there is one.
  """
  payment_mandate_sdjwt = message_utils.find_data_part(
      PAYMENT_MANDATE_SD_JWT_KEY, data_parts
  )
  if not payment_mandate_sdjwt:
    raise ValueError("Missing PaymentMandate SD-JWT")

  mandate = _verify_payment_mandate(payment_mandate_sdjwt)
  account_manager.update_token_by_transaction_id(mandate.transaction_id)
  await updater.complete()


def _verify_payment_mandate(
    sdjwt: str,
    expected_aud: str | None = None,
    expected_nonce: str | None = None,
) -> PaymentMandate:
  """Verify a PaymentMandate SD-JWT and return the parsed model.

  Supports two modes:
    - **Chain (DPC immediate):**
    ``DPC_sdjwt~~KB-SD-JWT~mandate_disc~agent_KB-JWT``
      — three-level delegation: DPC → wallet → KB-SD-JWT → agent → KB-JWT.
    - **Single token (HNP / standard):** Verified as a standalone SD-JWT.

  Args:
    sdjwt: The serialized SD-JWT string.

  Returns:
    The parsed PaymentMandate model.
  """
  pub_key = _load_agent_provider_public_key()
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
      raise ValueError(
          f"Expected at least 2 tokens in chain, got {len(tokens)}"
      )

    payloads = MandateClient().verify(
        token=sdjwt,
        key_or_provider=X5cOrKidPublicKeyProvider(
            lambda _kid: JWK.from_pyca(pub_key),
            trusted_roots=trusted_roots,
        ),
        expected_aud=expected_aud,
        expected_nonce=expected_nonce,
    )
    try:
      return PaymentMandate.model_validate(payloads[-1])
    except ValidationError as e:
      logging.warning(
          "Failed to validate payloads[-1] as PaymentMandate,"
          " returning raw dict: %s",
          e,
      )
      return payloads[-1]

  verified = MandateClient().verify(
      token=sdjwt,
      key_or_provider=JWK.from_pyca(pub_key),
      payload_type=PaymentMandate,
      expected_aud=expected_aud,
      expected_nonce=expected_nonce,
  )
  return verified.mandate_payload


def _load_agent_provider_public_key():
  if _AGENT_PROVIDER_PUB_KEY_PATH and os.path.exists(
      _AGENT_PROVIDER_PUB_KEY_PATH
  ):
    return load_pem_public_key(open(_AGENT_PROVIDER_PUB_KEY_PATH, "rb").read())
  raise ValueError("Agent-provider public key not found")


async def handle_payment_receipt(
    data_parts: list[dict[str, Any]],
    updater: TaskUpdater,
    current_task: Task | None,
) -> None:
  """Handles a payment receipt.

  Does nothing and then completes the task. This is a placeholder for now.

  Args:
    data_parts: DataPart contents. Should contain a single PaymentMandate.
    updater: The TaskUpdater instance for updating the task state.
    current_task: The current task if there is one.
  """
  await updater.complete()


def _get_payment_method_aliases(
    payment_methods: list[dict[str, Any]],
) -> list[str | None]:
  """Gets the payment method aliases from a list of payment methods."""
  return [payment_method.get("alias") for payment_method in payment_methods]


def _get_eligible_payment_method_aliases(
    user_email: str, merchant_accepted_payment_methods: list[PaymentMethodData]
) -> dict[str, list[str | None]]:
  """Gets the payment_methods eligible according to given PaymentMethodData.

  Args:
    user_email: The email address of the user's account.
    merchant_accepted_payment_methods: A list of eligible payment method
      criteria.

  Returns:
    A list of the user's eligible payment_methods.
  """
  payment_methods = account_manager.get_account_payment_methods(user_email)

  if os.environ.get("PAYMENT_METHOD") == "x402":
    payment_methods = [
        method for method in payment_methods if method.get("brand") == "x402"
    ]
  else:
    payment_methods = [
        method for method in payment_methods if method.get("brand") != "x402"
    ]

  eligible_payment_methods = []

  for payment_method in payment_methods:
    for criteria in merchant_accepted_payment_methods:
      if _payment_method_is_eligible(payment_method, criteria):
        eligible_payment_methods.append(payment_method)
        break
  return {
      "payment_method_aliases": _get_payment_method_aliases(
          eligible_payment_methods
      )
  }


def _payment_method_is_eligible(
    payment_method: dict[str, Any], merchant_criteria: PaymentMethodData
) -> bool:
  """Checks if a payment method is eligible based on a PaymentMethodData.

  Args:
    payment_method: A dictionary representing the payment method.
    merchant_criteria: A PaymentMethodData object containing the eligibility
      criteria.

  Returns:
    True if the payment_method is eligible according to the payment method,
    False otherwise.
  """
  if merchant_criteria.supported_methods == "https://www.x402.org/":
    return payment_method.get("brand") == "x402"
  if payment_method.get("type", "") != merchant_criteria.supported_methods:
    return False

  merchant_supported_networks = [
      network.casefold()
      for network in merchant_criteria.data.get("network", [])
  ]
  if not merchant_supported_networks:
    return False

  payment_card_networks = payment_method.get("network", [])
  for network_info in payment_card_networks:
    for supported_network in merchant_supported_networks:
      if network_info.get("name", "").casefold() == supported_network:
        return True
  return False
