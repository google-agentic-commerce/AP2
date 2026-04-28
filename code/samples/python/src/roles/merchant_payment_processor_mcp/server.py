"""Merchant MCP Server — inventory, cart, checkout, and PSP settlement tools.

Exposes six MCP tools consumed by the ADK shopping agent over stdio:
  search_inventory, check_product, assemble_cart,
  create_checkout, complete_checkout, initiate_payment.

Mandate verification uses the AP2 SDK (MandateClient / chain verifier)
instead of ad-hoc ECDSA + canonical-JSON checking.
Checkout JWTs are properly ES256-signed instead of using stubs.
"""

import json
import logging
import os

from pathlib import Path
from typing import Any

import httpx

from ap2.sdk.jwt_helper import create_jwt
from ap2.sdk.mandate import MandateClient
from ap2.sdk.payment_mandate_chain import PaymentMandateChain
from ap2.sdk.receipt_wrapper import ReceiptClient
from ap2.sdk.utils import compute_sha256_b64url
from common.constants import (
  AGENT_PROVIDER_PUB_PATH,
  CREDENTIALS_PROVIDER_PAYMENT_RECEIPT_URL,
  MERCHANT_PAYMENT_PROCESSOR_KEY_PATH,
  MERCHANT_PAYMENT_PROCESSOR_PUB_PATH,
  TEMP_DB,
)
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ec
from fastmcp import FastMCP
from fastmcp.server.middleware.logging import LoggingMiddleware
from jwcrypto.jwk import JWK
from pydantic import ValidationError


mcp = FastMCP("Merchant Payment Processor MCP Server")

_SCRIPT_DIR = Path(__file__).resolve().parent
_LOG_DIR = Path(os.environ.get("LOGS_DIR", _SCRIPT_DIR.parent / ".logs"))
_LOG_FILE = _LOG_DIR / "merchant-payment-processor-mcp.log"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_logger = logging.getLogger("merchant-payment-processor-mcp")
_logger.setLevel(logging.INFO)
_handler = logging.FileHandler(_LOG_FILE, mode="w", encoding="utf-8")
_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
_logger.addHandler(_handler)

mcp.add_middleware(
    LoggingMiddleware(
        logger=_logger,
        include_payloads=True,
        include_payload_length=True,
        max_payload_length=8000,
    )
)

_TOKEN_STORE_PATH = Path(
    os.environ.get(
        "AP2_TOKEN_STORE_PATH",
        str(TEMP_DB / "ap2_token_store.json"),
    )
)


# ── Key loading ─────────────────────────────────────────────────────────


def _get_agent_provider_public_key() -> JWK | None:
  """Loads the Agent Provider's public JWK from a file."""
  if not AGENT_PROVIDER_PUB_PATH.exists():
    return None
  try:
    return JWK.from_json(AGENT_PROVIDER_PUB_PATH.read_text(encoding="utf-8"))
  except (ValueError, json.JSONDecodeError, OSError) as e:
    _logger.warning("could not load agent-provider public key: %s", e)
    return None


def _get_merchant_payment_processor_signing_key(
    key_id: str = "merchant-payment-processor-key-1",
) -> JWK:
  """Load or generate the merchant payment processor's ES256 signing key as a JWK."""
  pem = os.environ.get("MERCHANT_PAYMENT_PROCESSOR_SIGNING_KEY_PEM")
  if pem:
    return JWK.from_json(pem)
  if MERCHANT_PAYMENT_PROCESSOR_KEY_PATH.exists():
    return JWK.from_json(
        MERCHANT_PAYMENT_PROCESSOR_KEY_PATH.read_text(encoding="utf-8")
    )

  raw_key = ec.generate_private_key(ec.SECP256R1())
  key = JWK.from_pyca(raw_key)
  jwk_dict = json.loads(key.export())
  jwk_dict["kid"] = key_id
  key = JWK.from_json(json.dumps(jwk_dict))

  MERCHANT_PAYMENT_PROCESSOR_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
  MERCHANT_PAYMENT_PROCESSOR_KEY_PATH.write_text(key.export(), encoding="utf-8")
  MERCHANT_PAYMENT_PROCESSOR_PUB_PATH.write_text(
      key.export_public(), encoding="utf-8"
  )
  return key


# ── Store helpers ───────────────────────────────────────────────────────


def _load_token_store() -> dict[str, Any]:
  try:
    if _TOKEN_STORE_PATH.exists():
      with open(_TOKEN_STORE_PATH) as f:
        return json.load(f)
  except (json.JSONDecodeError, OSError) as e:
    _logger.warning("token_store load failed: %s", e)
  return {}


def _save_token_store(store: dict[str, Any]) -> None:
  try:
    _TOKEN_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_TOKEN_STORE_PATH, "w") as f:
      json.dump(store, f, indent=2)
  except OSError as e:
    _logger.warning("token_store save failed: %s", e)


def _load_trigger_state() -> dict[str, Any]:
  """Loads the trigger state from the file system.

  Returns:
    A dictionary containing the trigger state, or an empty dictionary if the
    file does not exist or loading fails.
  """
  try:
    if _TRIGGER_STATE_PATH.exists():
      with open(_TRIGGER_STATE_PATH) as f:
        state = json.load(f)
      _logger.debug(
          "trigger_state loaded from %s: %s", _TRIGGER_STATE_PATH, state
      )
      return state
    _logger.debug("trigger_state file not found: %s", _TRIGGER_STATE_PATH)
  except (json.JSONDecodeError, OSError) as e:
    _logger.warning("trigger_state load failed: %s", e)
  return {}


async def _send_payment_receipt_to_credentials_provider(
    receipt: str,
) -> None:
  """Sends the payment receipt to the credentials provider."""
  async with httpx.AsyncClient(timeout=10.0) as client:
    try:
      response = await client.post(
          CREDENTIALS_PROVIDER_PAYMENT_RECEIPT_URL,
          json={"payment_receipt": receipt},
      )
      response.raise_for_status()
      _logger.info("Successfully sent payment receipt to credentials provider.")
    except httpx.HTTPStatusError as exc:
      _logger.warning("Failed to send payment receipt: %s", exc.response.text)
    except Exception as e:
      _logger.warning("Error sending payment receipt: %s", e)


@mcp.tool()
async def initiate_payment(
    payment_token: str,
    checkout_jwt_hash: str,
    open_checkout_hash: str,
) -> dict[str, Any]:
  """Initiates a payment for a human not present flow.

  The payment mandate is verified and a payment receipt is sent to the
  credentials provider.

  Amount, currency, and order_id are read from the token data and
  the verified closed payment mandate — not passed by the caller.

  Args:
    payment_token: The token received from the payment provider. Used to
      look up the bound payment_mandate_chain in the credentials-provider
      token store — no separate mandate id is needed.
    checkout_jwt_hash: The hash of the checkout JWT.
    open_checkout_hash: The hash of the open checkout mandate.
  """
  _logger.info(
      "initiate_payment called: payment_token=%s...",
      payment_token[:12] if payment_token else "None",
  )
  if not payment_token or not checkout_jwt_hash or not open_checkout_hash:
    return {
        "error": "missing_fields",
        "message": (
            "payment_token, checkout_jwt_hash, and open_checkout_hash are"
            " required"
        ),
    }

  token_store = _load_token_store()
  token_data = token_store.get(payment_token)
  if not token_data:
    return {"error": "token_not_found", "message": "payment_token not found"}
  if not token_data.get("used"):
    return {
        "error": "token_not_used",
        "message": "payment_token must be used (call complete_checkout first)",
    }

  payment_mandate_chain = token_data.get("payment_mandate_chain")
  if not payment_mandate_chain:
    return {
        "error": "missing_mandate",
        "message": "payment_token has no payment_mandate_chain",
    }
  payment_nonce = token_data.get("payment_nonce")
  if not payment_nonce:
    return {
        "error": "missing_payment_nonce",
        "message": "payment_token has no payment_nonce",
    }

  order_id = token_data.get("order_id", "")
  if not order_id:
    return {
        "error": "missing_order",
        "message": (
            "payment_token has no order_id (complete_checkout not called?)"
        ),
    }

  agent_provider_pub = _get_agent_provider_public_key()
  if not agent_provider_pub:
    return {
        "error": "agent_provider_key_missing",
        "message": (
            "Agent-provider public key not found — cannot verify payment"
            " mandate"
        ),
    }

  try:
    payloads = MandateClient().verify(
        token=payment_mandate_chain,
        key_or_provider=lambda _token: agent_provider_pub,
        expected_aud="credential-provider",
        expected_nonce=payment_nonce,
    )
    chain = PaymentMandateChain.parse(payloads)
    violations = chain.verify(
        expected_transaction_id=checkout_jwt_hash,
        expected_open_checkout_hash=open_checkout_hash,
    )
  except (
      ValueError,
      json.JSONDecodeError,
      InvalidSignature,
      ValidationError,
  ) as exc:
    return {
        "error": "chain_verification_exception",
        "message": str(exc),
    }
  if violations:
    return {
        "error": "chain_verification_failed",
        "message": "; ".join(violations),
    }

  _logger.info(
      "Creating payment receipt with order_id=%s",
      order_id,
  )
  payment_receipt_content = ReceiptClient().create_payment_receipt(
      payment_mandate_content=chain.closed_mandate,
      reference=compute_sha256_b64url(
          MandateClient().get_closed_mandate_jwt(payment_mandate_chain)
      ),
  )
  jwk_key = _get_merchant_payment_processor_signing_key(
      key_id="merchant-payment-processor-key-1"
  )
  payment_receipt = create_jwt(
      header={"alg": "ES256", "typ": "JWT", "kid": jwk_key.kid},
      payload=payment_receipt_content.model_dump(),
      private_key=jwk_key,
  )

  await _send_payment_receipt_to_credentials_provider(payment_receipt)
  _logger.info(
      "initiate_payment result: payment_id=%s, receipt=%s",
      payment_receipt_content.root.payment_id,
      payment_receipt_content.model_dump_json(),
  )
  return {"status": "success", "payment_receipt": payment_receipt}


if __name__ == "__main__":
  mcp.run()
