"""x402 PSP MCP Server.

Performs Web3 settlement: SD-JWT mandate verification, binding, ecrecover,
routing, and on-chain broadcast.
"""

import json
import logging
import os
import time

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ap2.sdk.mandate import MandateClient
from ap2.sdk.payment_mandate_chain import PaymentMandateChain
from common.constants import AGENT_PROVIDER_PUB_PATH
from common.x402_constants import (
  DEFAULT_MERCHANT_ADDRESS,
  DEFAULT_RPC_URL,
  DEFAULT_USDC_CONTRACT,
)
from fastmcp import FastMCP
from fastmcp.server.middleware.logging import LoggingMiddleware
from jwcrypto.jwk import JWK
from web3 import Web3


mcp = FastMCP("x402 PSP MCP")

_SCRIPT_DIR = Path(__file__).resolve().parent
_LOG_DIR = Path(os.environ.get("LOGS_DIR", _SCRIPT_DIR.parent / ".logs"))
_LOG_FILE = _LOG_DIR / "x402-psp-mcp.log"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_logger = logging.getLogger("x402-psp-mcp")
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


@mcp.tool()
def settle_payment(
    payment_token: str,
    checkout_jwt_hash: str = None,
    open_checkout_hash: str = None,
) -> Mapping[str, Any]:
  """Settle a payment token via Web3 Facilitator."""
  _logger.info("x402 settle_payment called")

  # Load the bundled token payload
  try:
    bundled = (
        json.loads(payment_token)
        if isinstance(payment_token, str) and "{" in payment_token
        else {"error": "Invalid token format"}
    )
  except Exception:
    return {
        "error": "invalid_json",
        "message": "Failed to parse bundled payload",
    }

  if "error" in bundled:
    return {
        "error": "settlement_failed",
        "message": "Provided payload is not a valid x402 bundle",
    }

  payment_mandate_id = bundled.get("payment_mandate_id", "")
  payment_nonce = bundled.get("payment_nonce", "")
  eip_payload = bundled.get("eip_3009_payload", {})

  if payment_mandate_id:
    loaded = _load_persisted_mandate(f"{payment_mandate_id}.sdjwt")
    if not loaded:
      return {
          "error": "mandate_not_found",
          "message": f"Payment mandate {payment_mandate_id} not found",
      }
    mandate_chain_str = loaded
  else:
    mandate_chain_str = bundled.get("payment_mandate_chain", "")

  if not mandate_chain_str or not eip_payload:
    return {
        "error": "missing_fields",
        "message": "Bundle must contain mandate chain and EIP-3009 payload",
    }
  if not payment_nonce:
    return {
        "error": "missing_fields",
        "message": "Bundle must contain payment_nonce",
    }

  # 0. Verify AI Mandate: check SD-JWT signatures, constraints, dates
  _logger.info("Step 0: Starting SD-JWT mandate chain verification")
  agent_provider_pub = None
  if AGENT_PROVIDER_PUB_PATH.exists():
    try:
      agent_provider_pub = JWK.from_json(
          AGENT_PROVIDER_PUB_PATH.read_text(encoding="utf-8")
      )
    except (OSError, ValueError, json.JSONDecodeError):
      _logger.warning(
          "Agent-provider public key not found — skipping SD-JWT verification"
      )
  else:
    _logger.warning(
        "Agent-provider public key not found — skipping SD-JWT verification"
    )

  if agent_provider_pub:
    try:
      payloads = MandateClient().verify(
          token=mandate_chain_str,
          key_or_provider=lambda _token: agent_provider_pub,
          expected_aud="credential-provider",
          expected_nonce=payment_nonce,
      )
      parsed_chain = PaymentMandateChain.parse(payloads)
      violations = parsed_chain.verify(
          expected_open_checkout_hash=open_checkout_hash
      )
      if violations:
        return {
            "error": "mandate_verification_failed",
            "message": "; ".join(violations),
        }
      _logger.info("SD-JWT mandate chain verified successfully")
    except Exception as e:
      _logger.exception("SD-JWT mandate verification failed")
      return {"error": "mandate_verification_failed", "message": str(e)}

  # 1. Verify Binding: Hash(Mandate) == Nonce
  _logger.info("Step 1: Verifying Binding")
  expected_nonce = Web3.keccak(text=mandate_chain_str)
  auth_nonce_hex = eip_payload.get("authorization", {}).get("nonce", "")

  if auth_nonce_hex != expected_nonce.hex():
    return {
        "error": "binding_failed",
        "message": (
            f"Mandate hash {expected_nonce.hex()} does not match signature"
            f" nonce {auth_nonce_hex}"
        ),
    }

  # 2. Recover Signer via EIP-712 ecrecover
  _logger.info("Step 2: Recovering signer via ecrecover")
  from eth_account import Account
  from eth_account.messages import encode_typed_data

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

  auth = eip_payload.get("authorization", {})
  signature = eip_payload.get("signature", "")

  message = {
      "from": auth.get("from"),
      "to": auth.get("to"),
      "value": int(auth.get("value", 0)),
      "validAfter": int(auth.get("validAfter", 0)),
      "validBefore": int(auth.get("validBefore", 0)),
      "nonce": expected_nonce,
  }

  try:
    structured_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": types["TransferWithAuthorization"],
        },
        "primaryType": "TransferWithAuthorization",
        "domain": domain,
        "message": message,
    }
    signable_message = encode_typed_data(full_message=structured_data)
    recovered_signer = Account.recover_message(
        signable_message, signature=signature
    )
  except Exception as e:
    return {"error": "invalid_signature", "message": f"ecrecover failed: {e}"}

  if recovered_signer.lower() != auth.get("from", "").lower():
    return {
        "error": "signer_mismatch",
        "message": (
            f"Recovered signer {recovered_signer} != authorization.from"
            f" {auth.get('from')}"
        ),
    }

  # 3. Routing and Value Checks
  expected_payee = (
      os.environ.get("MERCHANT_WALLET_ADDRESS") or DEFAULT_MERCHANT_ADDRESS
  )
  if auth.get("to", "").lower() != expected_payee.lower():
    return {
        "error": "routing_mismatch",
        "message": f"Destination {auth.get('to')} != expected {expected_payee}",
    }

  # 4. Live On-Chain Broadcast (Toggleable)
  if os.environ.get("BROADCAST_ON_CHAIN", "false").lower() == "true":
    try:
      rpc_url = os.environ.get("BASE_SEPOLIA_RPC", DEFAULT_RPC_URL)
      w3 = Web3(Web3.HTTPProvider(rpc_url))

      facilitator_key = (
          os.environ.get("FACILITATOR_PRIVATE_KEY")
          or DEFAULT_FACILITATOR_ADDRESS
      )
      if not facilitator_key:
        return {
            "error": "missing_facilitator_key",
            "message": "FACILITATOR_PRIVATE_KEY is required for live broadcast",
        }

      facilitator_account = Account.from_key(facilitator_key)
      usdc_contract_address = DEFAULT_USDC_CONTRACT

      # Minimal ABI for TransferWithAuthorization
      abi = [{
          "inputs": [
              {"internalType": "address", "name": "from", "type": "address"},
              {"internalType": "address", "name": "to", "type": "address"},
              {"internalType": "uint256", "name": "value", "type": "uint256"},
              {
                  "internalType": "uint256",
                  "name": "validAfter",
                  "type": "uint256",
              },
              {
                  "internalType": "uint256",
                  "name": "validBefore",
                  "type": "uint256",
              },
              {"internalType": "bytes32", "name": "nonce", "type": "bytes32"},
              {"internalType": "uint8", "name": "v", "type": "uint8"},
              {"internalType": "bytes32", "name": "r", "type": "bytes32"},
              {"internalType": "bytes32", "name": "s", "type": "bytes32"},
          ],
          "name": "transferWithAuthorization",
          "outputs": [],
          "stateMutability": "nonpayable",
          "type": "function",
      }]

      contract = w3.eth.contract(address=usdc_contract_address, abi=abi)

      # Extract r, s, v from signature
      sig_bytes = bytes.fromhex(
          signature[2:] if signature.startswith("0x") else signature
      )
      r = sig_bytes[:32]
      s = sig_bytes[32:64]
      v = int.from_bytes(sig_bytes[64:65], byteorder="big")
      if v < 27:
        v += 27

      # Build transaction
      tx = contract.functions.transferWithAuthorization(
          Web3.to_checksum_address(auth.get("from")),
          Web3.to_checksum_address(auth.get("to")),
          int(auth.get("value", 0)),
          int(auth.get("validAfter", 0)),
          int(auth.get("validBefore", 0)),
          expected_nonce,
          v,
          r,
          s,
      ).build_transaction({
          "from": facilitator_account.address,
          "nonce": w3.eth.get_transaction_count(facilitator_account.address),
          "maxFeePerGas": w3.eth.gas_price * 2,
          "maxPriorityFeePerGas": w3.to_wei(1, "gwei"),
      })

      # Sign and send
      signed_tx = w3.eth.account.sign_transaction(tx, facilitator_key)
      tx_hash_bytes = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
      tx_hash = tx_hash_bytes.hex()

      _logger.info("x402 real on-chain broadcast complete! tx_hash=%s", tx_hash)

    except Exception as e:
      return {
          "error": "broadcast_failed",
          "message": f"Live on-chain transaction failed: {e}",
      }
  else:
    tx_hash = "0x" + Web3.keccak(text=str(time.time())).hex()
    _logger.info(
        "x402 full verification passed! Mocking broadcast, tx_hash=%s", tx_hash
    )

  return {
      "status": "success",
      "tx_hash": tx_hash,
      "receipt": {
          "transaction_id": tx_hash,
          "status": "SETTLED",
          "settled_at": int(time.time()),
      },
  }


if __name__ == "__main__":
  mcp.run()
