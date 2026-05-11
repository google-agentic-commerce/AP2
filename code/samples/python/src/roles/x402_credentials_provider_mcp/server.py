"""x402 Credential Provider MCP Server.

Implements Web3 native x402 authorization signing via EIP-3009.
"""

import json
import logging
import os
import time
import uuid

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ap2.sdk.mandate import MandateClient
from ap2.sdk.payment_mandate_chain import PaymentMandateChain
from common.constants import AGENT_PROVIDER_PUB_PATH, TEMP_DB
from common.x402_constants import (
  DEFAULT_MERCHANT_ADDRESS,
  DEFAULT_USDC_CONTRACT,
  DEFAULT_USER_PRIVATE_KEY,
)
from eth_account import Account
from fastmcp import FastMCP
from fastmcp.server.middleware.logging import LoggingMiddleware
from jwcrypto.jwk import JWK
from web3 import Web3


mcp = FastMCP("x402 Credential Provider MCP Server")

_SCRIPT_DIR = Path(__file__).resolve().parent
_LOG_DIR = Path(os.environ.get("LOGS_DIR", _SCRIPT_DIR.parent / ".logs"))
_LOG_FILE = _LOG_DIR / "x402-cp-mcp.log"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_logger = logging.getLogger("x402-cp-mcp")
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

_TOKEN_EXPIRY_SECONDS = 300


def _load_token_store() -> dict[str, Any]:
  try:
    with open(_TOKEN_STORE_PATH) as f:
      return json.load(f)
  except FileNotFoundError:
    return {}
  except (json.JSONDecodeError, OSError):
    return {}


def _save_token_store(store: dict[str, Any]) -> None:
  try:
    _TOKEN_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_TOKEN_STORE_PATH, "w") as f:
      json.dump(store, f, indent=2)
  except OSError:
    _logger.exception("token_store save failed")


def _get_agent_provider_public_key() -> JWK | None:
  if not AGENT_PROVIDER_PUB_PATH.exists():
    return None
  try:
    return JWK.from_json(AGENT_PROVIDER_PUB_PATH.read_text(encoding="utf-8"))
  except (OSError, ValueError, json.JSONDecodeError) as e:
    _logger.warning("could not load agent-provider public key: %s", e)
    return None


def _load_persisted_mandate(filename: str) -> str | None:
  path = TEMP_DB / filename
  try:
    return path.read_text(encoding="ascii").strip()
  except OSError:
    return None


@mcp.tool()
def issue_payment_credential(
    payment_mandate_chain_id: str,
    open_checkout_hash: str,
    checkout_jwt_hash: str,
    payment_nonce: str,
) -> Mapping[str, Any]:
  """Verify mandate chain, generate EIP-3009 signature, return bundled token."""
  _logger.info("x402 issue_payment_credential called")

  mandate_chain = None
  if payment_mandate_chain_id:
    mandate_chain = _load_persisted_mandate(f"{payment_mandate_chain_id}.sdjwt")
  if not mandate_chain:
    return {
        "error": "mandate_not_found",
        "message": (
            "Could not load payment_mandate from"
            f" {payment_mandate_chain_id}.sdjwt"
        ),
    }
  if not payment_nonce:
    return {"error": "missing_fields", "message": "payment_nonce is required"}

  agent_provider_pub = _get_agent_provider_public_key()
  if not agent_provider_pub:
    return {"error": "agent_provider_key_not_found"}

  try:
    payloads = MandateClient().verify(
        token=mandate_chain,
        key_or_provider=lambda _token: agent_provider_pub,
        expected_aud="credential-provider",
        expected_nonce=payment_nonce,
    )
    chain = PaymentMandateChain.parse(payloads)
    violations = chain.verify(
        expected_open_checkout_hash=open_checkout_hash,
        expected_transaction_id=checkout_jwt_hash,
    )
  except ValueError as e:
    _logger.exception("x402 mandate verification failed")
    return {"error": "verification_failed", "message": str(e)}

  if violations:
    return {"error": "verification_failed", "message": "; ".join(violations)}

  # Extract 'to' address and value from the verified mandate chain
  try:
    payee_address = chain.closed_mandate.payment_instrument.payee_address
    amount_cents = chain.closed_mandate.payment_amount.amount
    if not payee_address:
      payee_address = (
          os.environ.get("MERCHANT_WALLET_ADDRESS") or DEFAULT_MERCHANT_ADDRESS
      )
  except AttributeError:
    payee_address = (
        os.environ.get("MERCHANT_WALLET_ADDRESS") or DEFAULT_MERCHANT_ADDRESS
    )
    amount_cents = 1250

  # x402 Binding Check: Hash mandate to create exactly 32-byte EIP-3009 Nonce
  nonce = Web3.keccak(text=mandate_chain)
  private_key = (
      os.environ.get("X402_USER_PRIVATE_KEY") or DEFAULT_USER_PRIVATE_KEY
  )
  account = Account.from_key(private_key)

  # Convert cents to 6-decimal USDC units (cents * 10,000)
  usdc_value = amount_cents * 10000

  # EIP-712 Domain and Types for TransferWithAuthorization
  domain = {
      "name": "USD Coin",
      "version": "2",
      "chainId": 84532,
      "verifyingContract": DEFAULT_USDC_CONTRACT,
  }

  types = {
      "TransferWithAuthorization": [
          {"name": "from", "type": "address"},
          {"name": "to", "type": "address"},
          {"name": "value", "type": "uint256"},
          {"name": "validAfter", "type": "uint256"},
          {"name": "validBefore", "type": "uint256"},
          {"name": "nonce", "type": "bytes32"},
      ]
  }

  message = {
      "from": account.address,
      "to": payee_address,
      "value": usdc_value,
      "validAfter": 0,
      "validBefore": int(time.time()) + 3600,
      "nonce": nonce,
  }

  # Generate the cryptographic EIP-712 signature
  signed_message = Account.sign_typed_data(
      private_key, domain_data=domain, message_types=types, message_data=message
  )

  bundled = {
      "payment_mandate_chain": mandate_chain,
      "payment_nonce": payment_nonce,
      "eip_3009_payload": {
          "signature": signed_message.signature.hex(),
          "authorization": {
              "from": account.address,
              "to": payee_address,
              "value": str(usdc_value),
              "validAfter": "0",
              "validBefore": str(message["validBefore"]),
              "nonce": nonce.hex(),
          },
      },
  }

  token_id = "x402_tok_" + str(uuid.uuid4()).replace("-", "")
  expires_at = int(time.time()) + _TOKEN_EXPIRY_SECONDS

  # Store token so revoke can clear it
  store = _load_token_store()
  store[token_id] = {
      "checkout_jwt_hash": checkout_jwt_hash,
      "payment_nonce": payment_nonce,
      "bundled_payload": bundled,
      "used": False,
      "expires_at": expires_at,
  }
  _save_token_store(store)

  return {
      "payment_token": token_id,
      "expires_at": expires_at,
      "bundled_token": json.dumps(bundled),
  }


@mcp.tool()
def revoke_payment_credential(payment_token: str) -> Mapping[str, Any]:
  """Revoke a previously issued payment token."""
  store = _load_token_store()
  if payment_token in store:
    del store[payment_token]
    _save_token_store(store)
    return {"revoked": True}
  return {"revoked": False, "error": "token_not_found"}


@mcp.tool()
def list_x402_wallets() -> Mapping[str, Any]:
  """Return user's x402 wallet info."""
  private_key = (
      os.environ.get("X402_USER_PRIVATE_KEY") or DEFAULT_USER_PRIVATE_KEY
  )
  account = Account.from_key(private_key)
  return {
      "wallets": [{
          "address": account.address,
          "balance": "100.0 USDC",
          "network": "base-sepolia",
      }]
  }


if __name__ == "__main__":
  mcp.run()
