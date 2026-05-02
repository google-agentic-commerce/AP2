# Copyright 2026 Tenzro Network.
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

"""Thin Tenzro JSON-RPC client used by the AP2 DID-settlement sample.

This module hides the Tenzro-specific RPC shape behind a small,
DID-agnostic API so that ``main.py`` reads as a clean AP2 mandate
flow. Other DID-based identity layers can implement the same surface
against their own chain.

All methods are blocking ``requests`` calls. Errors raise
``TenzroRpcError`` with the JSON-RPC error code preserved for tests.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any

import requests


DEFAULT_RPC_URL = "https://rpc.tenzro.network"
DEFAULT_TIMEOUT_SECS = 30.0


class TenzroRpcError(RuntimeError):
    """Raised when the Tenzro RPC returns a JSON-RPC error envelope."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.data = data


@dataclass(frozen=True)
class ResolvedIdentity:
    """A minimal projection of Tenzro's TDIP identity record.

    Only the fields the sample actually consumes are surfaced here. The
    full record is preserved under ``raw`` for debugging.
    """

    did: str
    identity_type: str  # "Human" | "Machine"
    kyc_tier: str | None
    controller_did: str | None
    raw: dict[str, Any]


class TenzroClient:
    """Tenzro JSON-RPC client.

    The ``rpc_url`` argument defaults to ``$TENZRO_RPC_URL`` or, failing
    that, the live testnet at ``https://rpc.tenzro.network``.
    """

    def __init__(
        self,
        rpc_url: str | None = None,
        *,
        timeout_secs: float = DEFAULT_TIMEOUT_SECS,
        session: requests.Session | None = None,
    ) -> None:
        self.rpc_url = rpc_url or os.environ.get(
            "TENZRO_RPC_URL", DEFAULT_RPC_URL
        )
        self.timeout_secs = timeout_secs
        self._session = session or requests.Session()
        self._next_id = 1
        # Guards ``_next_id`` so the same client can be shared across
        # threads without two concurrent calls picking the same RPC id.
        self._id_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Low-level JSON-RPC helper
    # ------------------------------------------------------------------

    def _call(self, method: str, params: Any) -> Any:
        """Issue a single JSON-RPC 2.0 call and return the ``result`` field.

        Tenzro's RPC accepts both ``params: {...}`` (object) and
        ``params: [{...}]`` (array-wrapped) and unwraps the leading
        array element. We use the array form, matching the EVM-compat
        convention.
        """
        with self._id_lock:
            rpc_id = self._next_id
            self._next_id += 1
        body = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": method,
            "params": [params] if params is not None else [],
        }
        resp = self._session.post(
            self.rpc_url,
            json=body,
            timeout=self.timeout_secs,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        envelope = resp.json()
        if "error" in envelope and envelope["error"] is not None:
            err = envelope["error"]
            raise TenzroRpcError(
                code=int(err.get("code", -32603)),
                message=str(err.get("message", "unknown RPC error")),
                data=err.get("data"),
            )
        return envelope.get("result")

    # ------------------------------------------------------------------
    # Identity (TDIP) — read-only, no signing required
    # ------------------------------------------------------------------

    def resolve_did(self, did: str) -> ResolvedIdentity:
        """Resolve a ``did:tenzro:*`` (or ``did:pdis:*``) DID."""
        result = self._call("tenzro_resolveIdentity", {"did": did})
        if not isinstance(result, dict):
            raise TenzroRpcError(
                -32603,
                f"resolveIdentity returned non-dict: {type(result).__name__}",
            )
        return ResolvedIdentity(
            did=did,
            identity_type=str(result.get("identity_type", "Unknown")),
            kyc_tier=result.get("kyc_tier"),
            controller_did=result.get("controller_did"),
            raw=result,
        )

    # ------------------------------------------------------------------
    # AP2 — mandate validation
    # ------------------------------------------------------------------

    def validate_mandate_pair(
        self,
        intent_vdc: dict[str, Any],
        cart_vdc: dict[str, Any],
        *,
        enforce_delegation: bool = True,
    ) -> dict[str, Any]:
        """Cross-validate a CartMandate against its parent IntentMandate.

        With ``enforce_delegation=True`` the node also exercises the
        TDIP ``DelegationScope`` of the agent and (if an ``AgentRuntime``
        is wired into the node) the runtime ``SpendingPolicy``.

        Returns the raw ``{"valid": bool, ...}`` envelope. The caller
        decides whether to treat ``valid=false`` as fatal.
        """
        return self._call(
            "tenzro_ap2ValidateMandatePair",
            {
                "intent_vdc": intent_vdc,
                "cart_vdc": cart_vdc,
                "enforce_delegation": enforce_delegation,
            },
        )

    # ------------------------------------------------------------------
    # ZK — Plonky3 STARK over KoalaBear
    # ------------------------------------------------------------------

    def create_zk_proof_settlement(
        self,
        *,
        payer_balance: int,
        service_proof: int,
        nonce: int,
        prev_nonce: int,
        amount: int,
    ) -> dict[str, Any]:
        """Generate a Plonky3 STARK over the ``settlement`` AIR.

        The five witness fields are KoalaBear field elements
        (``2^31 - 2^24 + 1``); pass them as plain ``int`` values. The
        RPC handles field-element conversion. Returns
        ``{"circuit_id", "proof", "public_inputs", "proof_size_bytes",
        "created_at"}``.
        """
        return self._call(
            "tenzro_createZkProof",
            {
                "circuit_id": "settlement",
                "payer_balance": payer_balance,
                "service_proof": service_proof,
                "nonce": nonce,
                "prev_nonce": prev_nonce,
                "amount": amount,
            },
        )

    def verify_zk_proof(
        self,
        *,
        circuit_id: str,
        proof_hex: str,
        public_inputs_hex: list[str],
    ) -> dict[str, Any]:
        """Verify a Plonky3 STARK envelope. Returns ``{"valid": bool, ...}``."""
        return self._call(
            "tenzro_verifyZkProof",
            {
                "circuit_id": circuit_id,
                "proof": proof_hex,
                "public_inputs": public_inputs_hex,
            },
        )

    # ------------------------------------------------------------------
    # Settlement (simulated in this sample)
    # ------------------------------------------------------------------

    def settle_channel_simulated(
        self,
        *,
        channel_id: str,
        payment_amount: int,
        proof_commitment_hex: str,
    ) -> dict[str, Any]:
        """Build a simulated settlement-channel receipt.

        Note: production settlement requires a funded payer key and a
        previously-opened channel. The sample skips both because the
        public testnet RPC will not accept channel updates from
        unauthenticated clients. The structure of the returned receipt
        matches the shape ``tenzro_updatePaymentChannel`` returns.
        """
        return {
            "channel_id": channel_id,
            "payment_amount": payment_amount,
            "proof_commitment": proof_commitment_hex,
            "status": "simulated",
            "note": (
                "This is a structural placeholder. Run "
                "`tenzro escrow open-channel ...` with a funded payer "
                "key to drive the live updatePaymentChannel RPC."
            ),
        }
